from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(default="Guest", min_length=1, max_length=80)


class UserRead(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudySessionCreate(BaseModel):
    user_id: int = 1
    subject: str = Field(min_length=1, max_length=120)


class StudySessionRead(BaseModel):
    id: int
    user_id: int
    subject: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class FeaturePredictionRequest(BaseModel):
    session_id: int | None = None
    ear: float = Field(ge=0, le=1)
    eye_closed_duration_ms: int = Field(ge=0)
    face_pitch: float = 0
    face_yaw: float = 0
    face_roll: float = 0


class FramePredictionRequest(BaseModel):
    session_id: int | None = None
    image_base64: str
    eye_closed_duration_ms: int = Field(default=0, ge=0)


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class PredictionRead(BaseModel):
    label: str
    is_drowsy: bool
    probability: float
    ear: float | None = None
    eye_closed_duration_ms: int | None = None
    face_pitch: float | None = None
    face_yaw: float | None = None
    face_roll: float | None = None
    face_box: BoundingBox | None = None
    eye_boxes: list[BoundingBox] = Field(default_factory=list)
    log_id: int | None = None


class DrowsinessLogRead(BaseModel):
    id: int
    session_id: int
    detected_at: datetime
    is_drowsy: bool
    probability: float
    ear: float | None
    eye_closed_duration_ms: int | None
    face_pitch: float | None
    face_yaw: float | None
    face_roll: float | None

    model_config = {"from_attributes": True}


class SessionStatsRead(BaseModel):
    session_id: int
    subject: str
    duration_seconds: int
    total_logs: int
    drowsy_count: int
    drowsy_ratio: float
