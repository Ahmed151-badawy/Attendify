"""
app/models/user.py
──────────────────
SQLAlchemy modern declarative model for users (students, lecturers, admins).
"""
import enum
from typing import Optional, List
from sqlalchemy import String, ForeignKey, Enum, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from passlib.context import CryptContext

from app.core.database import Base

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False
)


class RoleEnum(enum.Enum):
    student = "student"
    lecturer = "lecturer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False, index=True)
    faculty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("faculties.id"), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # ── Relationships ──────────────────────────────────────────────────────────
    courses_taught: Mapped[List["Course"]] = relationship("Course", back_populates="lecturer", lazy="select")
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates="student", lazy="select")
    attendance_history: Mapped[List["Attendance"]] = relationship(
        "Attendance", 
        back_populates="student", 
        cascade="all, delete-orphan",
        lazy="select"
    )
    faculty: Mapped[Optional["Faculties"]] = relationship("Faculties", back_populates="users", lazy="select")

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email}, role={self.role})"
    
    def set_password(self, raw_password: str):
        self.password = pwd_context.hash(raw_password)
        
    def verify_password(self, raw_password: str) -> bool:
        return pwd_context.verify(raw_password, self.password)