"""
app/models/attendance_log.py
─────────────────────────────
Session tracking partitions, active Projector dynamic QR tokens, and live Attendance entries.
"""
import enum
import datetime
from typing import Optional, List
from sqlalchemy import String, ForeignKey, Enum, DateTime, Boolean, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CheckInEnum(enum.Enum):
    ble = "ble"
    qr = "qr"
    manual = "manual"


class Session(Base):
    __tablename__ = "sessions"
    
    session_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    major: Mapped[int] = mapped_column(nullable=False)
    minor: Mapped[int] = mapped_column(nullable=False)
    qr_secret_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # ── Relationships ──────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship("Course", back_populates="sessions", lazy="select")
    lecturer: Mapped["User"] = relationship("User", lazy="select")
    attendance_logs: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="session", cascade="all, delete-orphan", lazy="select"
    )
    projector_tokens: Mapped[List["ProjectorToken"]] = relationship("ProjectorToken", back_populates="session", lazy="select")

    def __repr__(self) -> str:
        return f"Session(id={self.session_id}, major={self.major}, minor={self.minor}, is_active={self.is_active})"


class Attendance(Base):
    __tablename__ = "attendance_logs"
    
    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) 
    checkin_method: Mapped[CheckInEnum] = mapped_column(Enum(CheckInEnum), nullable=False)
    scan_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # ── Relationships ──────────────────────────────────────────────────────────
    student: Mapped["User"] = relationship("User", back_populates="attendance_history", lazy="select")
    session: Mapped["Session"] = relationship("Session", back_populates="attendance_logs", lazy="select")
    
    # ── Hardened Anti-Cheat Multi-Layer Constraints ────────────────────────────
    __table_args__ = (
        UniqueConstraint('session_id', 'student_id', name='_unique_student_session'),
        UniqueConstraint('session_id', 'device_id', name='_unique_device_per_session'),
    )

    def __repr__(self) -> str:
        return f"Attendance(log_id={self.log_id}, student={self.student_id}, session={self.session_id}, method={self.checkin_method})"


class ProjectorToken(Base):
    __tablename__ = "projector_tokens"
    
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    session: Mapped["Session"] = relationship("Session", back_populates="projector_tokens", lazy="select")

    def __repr__(self) -> str:
        return f"ProjectorToken(token={self.token[:8]}..., session={self.session_id}, is_used={self.is_used})"


class Faculties(Base):
    __tablename__ = "faculties"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # ── Relationships ──────────────────────────────────────────────────────────
    courses: Mapped[List["Course"]] = relationship("Course", back_populates="faculty", lazy="select")
    users: Mapped[List["User"]] = relationship("User", back_populates="faculty", lazy="select")
    
    def __repr__(self) -> str:
        return f"Faculties(id={self.id}, name={self.name})"