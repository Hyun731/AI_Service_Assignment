from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="Guest")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    study_sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="study_sessions")
    drowsiness_logs: Mapped[list["DrowsinessLog"]] = relationship(
        back_populates="study_session",
        cascade="all, delete-orphan",
    )


class DrowsinessLog(Base):
    __tablename__ = "drowsiness_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("study_sessions.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_drowsy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    ear: Mapped[float | None] = mapped_column(Float, nullable=True)
    eye_closed_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_pitch: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_yaw: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_roll: Mapped[float | None] = mapped_column(Float, nullable=True)

    study_session: Mapped[StudySession] = relationship(back_populates="drowsiness_logs")
