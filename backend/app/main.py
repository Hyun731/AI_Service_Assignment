from datetime import datetime
import sys

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .ml_service import predictor
from .models import DrowsinessLog, StudySession, User
from .schemas import (
    DrowsinessLogRead,
    FeaturePredictionRequest,
    FramePredictionRequest,
    PredictionRead,
    SessionStatsRead,
    StudySessionCreate,
    StudySessionRead,
    UserCreate,
    UserRead,
)
from .vision import decode_base64_image, extract_face_features


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sleep Study Guard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/debug/runtime")
def runtime() -> dict[str, object]:
    import mediapipe as mp

    return {
        "python": sys.version.split()[0],
        "mediapipe": mp.__version__,
        "has_solutions": hasattr(mp, "solutions"),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Sleep Study Guard API",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/default", response_model=UserRead)
def get_default_user(db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.id == 1))
    if user is None:
        user = User(id=1, name="Guest")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@app.post("/study-sessions/start", response_model=StudySessionRead)
def start_study_session(payload: StudySessionCreate, db: Session = Depends(get_db)) -> StudySession:
    user = db.get(User, payload.user_id)
    if user is None:
        user = User(id=payload.user_id, name="Guest")
        db.add(user)
        db.flush()

    session = StudySession(user_id=user.id, subject=payload.subject)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.post("/study-sessions/{session_id}/end", response_model=StudySessionRead)
def end_study_session(session_id: int, db: Session = Depends(get_db)) -> StudySession:
    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session.ended_at is None:
        ended_at = datetime.utcnow()
        session.ended_at = ended_at
        session.duration_seconds = int((ended_at - session.started_at).total_seconds())
        session.is_active = False
        db.commit()
        db.refresh(session)
    return session


@app.get("/study-sessions", response_model=list[StudySessionRead])
def list_study_sessions(db: Session = Depends(get_db)) -> list[StudySession]:
    return list(db.scalars(select(StudySession).order_by(StudySession.started_at.desc())).all())


def save_prediction_log(
    db: Session,
    session_id: int | None,
    is_drowsy: bool,
    probability: float,
    features: dict[str, float],
) -> int | None:
    if session_id is None:
        return None

    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Study session not found")

    log = DrowsinessLog(
        session_id=session_id,
        is_drowsy=is_drowsy,
        probability=probability,
        ear=features.get("ear"),
        eye_closed_duration_ms=int(features.get("eye_closed_duration_ms", 0)),
        face_pitch=features.get("face_pitch"),
        face_yaw=features.get("face_yaw"),
        face_roll=features.get("face_roll"),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log.id


@app.post("/drowsiness/predict", response_model=PredictionRead)
def predict_from_features(payload: FeaturePredictionRequest, db: Session = Depends(get_db)) -> PredictionRead:
    features = payload.model_dump(exclude={"session_id"})
    is_drowsy, probability = predictor.predict(features)
    log_id = save_prediction_log(db, payload.session_id, is_drowsy, probability, features)
    return PredictionRead(
        label="drowsy" if is_drowsy else "awake",
        is_drowsy=is_drowsy,
        probability=probability,
        log_id=log_id,
        **features,
    )


@app.post("/drowsiness/predict-frame", response_model=PredictionRead)
def predict_from_frame(payload: FramePredictionRequest, db: Session = Depends(get_db)) -> PredictionRead:
    try:
        frame = decode_base64_image(payload.image_base64)
        face_features = extract_face_features(frame)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Frame analysis failed: {exc}") from exc

    features = {
        "ear": face_features.ear,
        "eye_closed_duration_ms": float(payload.eye_closed_duration_ms),
        "face_pitch": face_features.face_pitch,
        "face_yaw": face_features.face_yaw,
        "face_roll": face_features.face_roll,
    }
    is_drowsy, probability = predictor.predict(features)
    log_id = save_prediction_log(db, payload.session_id, is_drowsy, probability, features)
    return PredictionRead(
        label="drowsy" if is_drowsy else "awake",
        is_drowsy=is_drowsy,
        probability=probability,
        log_id=log_id,
        face_box=face_features.face_box,
        eye_boxes=face_features.eye_boxes or [],
        **features,
    )


@app.get("/drowsiness/logs", response_model=list[DrowsinessLogRead])
def list_logs(session_id: int | None = None, db: Session = Depends(get_db)) -> list[DrowsinessLog]:
    statement = select(DrowsinessLog).order_by(DrowsinessLog.detected_at.desc())
    if session_id is not None:
        statement = statement.where(DrowsinessLog.session_id == session_id)
    return list(db.scalars(statement).all())


@app.get("/stats/session/{session_id}", response_model=SessionStatsRead)
def get_session_stats(session_id: int, db: Session = Depends(get_db)) -> SessionStatsRead:
    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Study session not found")

    total_logs = db.scalar(
        select(func.count(DrowsinessLog.id)).where(DrowsinessLog.session_id == session_id)
    ) or 0
    drowsy_count = db.scalar(
        select(func.count(DrowsinessLog.id)).where(
            DrowsinessLog.session_id == session_id,
            DrowsinessLog.is_drowsy.is_(True),
        )
    ) or 0
    duration = session.duration_seconds
    if duration is None:
        duration = int((datetime.utcnow() - session.started_at).total_seconds())
    ratio = drowsy_count / total_logs if total_logs else 0.0
    return SessionStatsRead(
        session_id=session.id,
        subject=session.subject,
        duration_seconds=duration,
        total_logs=total_logs,
        drowsy_count=drowsy_count,
        drowsy_ratio=ratio,
    )
