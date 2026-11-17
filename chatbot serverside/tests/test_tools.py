"""
tests/test_tools.py  —  Phase 4: Tool Layer Unit Tests
───────────────────────────────────────────────────────
Validates input parameter parsing and boundaries at the Pydantic type layout definitions.
"""
from datetime import date
import pytest
from pydantic import ValidationError

from app.schemas.tools_input import (
    AttendanceSummaryInput,
    AttendanceOverrideInput,
    ClassAnalyticsInput,
)


class TestAttendanceSummaryInput:
    
    def test_valid_input_passes(self):
        """Student tools only accept the targeted course ID integer configuration context."""
        payload = AttendanceSummaryInput(course_id=15)
        assert payload.course_id == 15

    def test_invalid_course_id_type_rejected(self):
        """Ensures text codes are intercepted at the boundary to protect integer columns."""
        with pytest.raises(ValidationError):
            AttendanceSummaryInput(course_id="CS-402")  # Must be an integer key index

    def test_date_range_validation(self):
        """Validates that text formats map to proper Python datetime calendar signatures."""
        payload = AttendanceSummaryInput(
            course_id=15,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        assert payload.start_date < payload.end_date


class TestClassAnalyticsInput:
    
    def test_valid_integer_payload_passes(self):
        payload = ClassAnalyticsInput(course_id=12)
        assert payload.course_id == 12

    def test_malformed_string_analytics_rejected(self):
        with pytest.raises(ValidationError):
            ClassAnalyticsInput(course_id="Systems-Group-4")


class TestAttendanceOverrideInput:
    
    def test_valid_override_fields_pass(self):
        """Validates structural routing contracts match database operational parameters."""
        payload = AttendanceOverrideInput(
            student_id=101,
            course_id=15,
            session_date=date(2026, 5, 24),
            new_status="PRESENT"
        )
        assert payload.student_id == 101
        assert payload.new_status == "PRESENT"

    def test_invalid_status_value_rejected(self):
        """Ensures status options are bounded strictly to valid system choices."""
        with pytest.raises(ValidationError):
            AttendanceOverrideInput(
                student_id=101,
                course_id=15,
                session_date=date(2026, 5, 24),
                new_status="UNKNOWN_STATUS_VALUE"  # Blocked by validation pattern logic
            )