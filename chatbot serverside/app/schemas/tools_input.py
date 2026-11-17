"""
app/schemas/tools_input.py  —  Phase 1: Deterministic Tooling Schemas
──────────────────────────────────────────────────────────────────────
Strict Pydantic v2 models that define every LLM tool call's input contract.

DESIGN PRINCIPLES
─────────────────
• Every field is explicitly typed — no generic `dict`, `Any`, or broad wrappers.
• `description` strings act as direct compilation prompts for the LLM.
• Zero-Trust IDOR Prevention: Student tools never accept a student_id from
  the LLM. They look up data contextually; user identity is handled by security claims.
• Synchronized Types: Maps perfectly to database integer keys and lowercase enums.
"""
from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# ── STUDENT TOOLS INPUT SCHEMAS ────────────────────────────────==============
# =============================================================================

class AttendanceSummaryInput(BaseModel):
    """Input schema for fetch_student_attendance_percentage."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"course_id": 15},
                {"course_id": 15, "start_date": "2026-01-01", "end_date": "2026-06-30"},
            ]
        }
    }

    course_id: int = Field(
        ...,
        description="The unique integer database ID of the course.",
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Optional filter start range (YYYY-MM-DD). Omit for all-time tracking.",
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Optional filter end range (YYYY-MM-DD). Omit for all-time tracking.",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "AttendanceSummaryInput":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date.")
        return self


class AttendanceHistoryInput(BaseModel):
    """Input schema for get_my_attendance_history."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"course_id": 15},
                {"course_id": 15, "limit": 20},
            ]
        }
    }

    course_id: int = Field(
        ...,
        description="The unique integer database ID of the course.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of chronological records to return. Valid range: 1 to 50.",
    )


# =============================================================================
# ── LECTURER TOOLS INPUT SCHEMAS ────────────────────────────────=============
# =============================================================================

class AttendanceOverrideInput(BaseModel):
    """Input schema for override_attendance. Lecturer and Admin only."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "student_id": 101,
                    "course_id": 15,
                    "session_date": "2026-05-24",
                    "new_status": "PRESENT",
                }
            ]
        }
    }

    student_id: int = Field(
        ...,
        description="The unique integer user ID of the student whose record is being updated.",
    )
    course_id: int = Field(
        ...,
        description="The unique integer database ID of the target course.",
    )
    session_date: date = Field(
        ...,
        description="The calendar date of the specific lecture session to override (YYYY-MM-DD).",
    )
    new_status: Literal["PRESENT", "ABSENT"] = Field(
        ...,
        description="The replacement status constraint. Must be exactly 'PRESENT' or 'ABSENT'.",
    )


class ClassAnalyticsInput(BaseModel):
    """Input schema for get_class_analytics. Lecturer and Admin only."""

    model_config = {
        "json_schema_extra": {
            "examples": [{"course_id": 12}]
        }
    }

    course_id: int = Field(
        ...,
        description="The target integer course database ID to compute analytics for.",
    )


class AbsenteeReportInput(BaseModel):
    """Input schema for get_absentee_report. Lecturer and Admin only."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"course_id": 15, "session_date": "2026-05-24"},
            ]
        }
    }

    course_id: int = Field(
        ...,
        description="The unique integer database ID of the course.",
    )
    session_date: date = Field(
        ...,
        description="The calendar date of the target session to compile the absentee roster for (YYYY-MM-DD).",
    )