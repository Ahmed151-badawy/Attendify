"""
app/models/course.py
────────────────────
Course registry model mapping directly to institutional faculties and lecturers.
"""
from typing import Optional, List
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    faculty_id: Mapped[Optional[int]] = mapped_column(ForeignKey("faculties.id"), nullable=True)
    
    # ── Relationships ──────────────────────────────────────────────────────────
    lecturer: Mapped["User"] = relationship("User", back_populates="courses_taught", lazy="select")
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates="course", lazy="select")
    faculty: Mapped[Optional["Faculties"]] = relationship("Faculties", back_populates="courses", lazy="select")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="course", lazy="select")

    def __repr__(self) -> str:
        return f"Course(id={self.id}, title={self.title}, lecturer_id={self.lecturer_id})"


class Enrollment(Base):
    __tablename__ = "enrollments"
    
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    
    # ── Relationships ──────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship("Course", back_populates="enrollments", lazy="select")
    student: Mapped["User"] = relationship("User", back_populates="enrollments", lazy="select")

    def __repr__(self) -> str:
        return f"Enrollment(course_id={self.course_id}, student_id={self.student_id})"