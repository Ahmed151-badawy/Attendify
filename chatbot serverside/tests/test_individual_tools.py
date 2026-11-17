"""
tests/test_individual_tools.py
──────────────────────────────
Granular standalone unit tests for student and instructor tools.
Bypasses the LangGraph framework entirely to track business logic units.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.tools.student_tools import make_student_tools
from app.tools.instructor_tools import make_instructor_tools

# Extract raw functions out of the LangChain tool containers
# tests/test_individual_tools.py

# ✅ Extract coroutine for async tools, falling back to func for sync tools
student_tools = {t.name: (t.coroutine if t.coroutine else t.func) for t in make_student_tools()}
instructor_tools = {t.name: (t.coroutine if t.coroutine else t.func) for t in make_instructor_tools()}


@pytest.mark.asyncio
async def test_fetch_student_attendance_percentage_success():
    """Tracks fetch_student_attendance_percentage logic under standard success data."""
    fetch_func = student_tools["fetch_student_attendance_percentage"]

    # 1. Setup mock asynchronous DB session responses
    mock_db = AsyncMock()
    mock_execute_total = MagicMock()
    mock_execute_attended = MagicMock()

    # First query (total sessions) returns 20
    mock_execute_total.scalar.return_value = 20
    # Second query (attended sessions) returns 15
    mock_execute_attended.scalar.return_value = 15

    # Map sequential side effects for each db.execute call
    mock_db.execute.side_effect = [mock_execute_total, mock_execute_attended]

    # 2. Invoke unit independently
    result = await fetch_func(
        course_id=33, 
        db_session=mock_db, 
        verified_user_id=101
    )

    # 3. Assert calculation matches 15/20 = 75.0%
    assert result["status"] == "success"
    assert result["course_id"] == 33
    assert result["total_sessions"] == 20
    assert result["attended_sessions"] == 15
    assert result["percentage"] == "75.0%"


@pytest.mark.asyncio
async def test_fetch_student_attendance_percentage_zero_sessions():
    """Ensures division by zero is avoided if a course has no sessions logged yet."""
    fetch_func = student_tools["fetch_student_attendance_percentage"]

    mock_db = AsyncMock()
    mock_execute = MagicMock()
    mock_execute.scalar.return_value = 0
    mock_db.execute.return_value = mock_execute

    result = await fetch_func(course_id=44, db_session=mock_db, verified_user_id=101)

    assert result["status"] == "success"
    assert result["percentage"] == "0%"
    assert "No sessions" in result["detail"]


@pytest.mark.asyncio
async def test_get_class_analytics_unauthorized():
    """Guarantees that a student profile attempting instructor queries is blocked."""
    analytics_func = instructor_tools["get_class_analytics"]
    mock_db = AsyncMock()

    result = await analytics_func(
        course_id=33,
        db_session=mock_db,
        verified_user_id=101,
        verified_user_role="student"  # ◄── Unauthorized role
    )

    assert result["status"] == "error"
    assert "Unauthorized" in result["detail"]


@pytest.mark.asyncio
async def test_get_class_analytics_success():
    """Tracks cumulative and monthly statistics formatting for faculty reviews."""
    analytics_func = instructor_tools["get_class_analytics"]

    mock_db = AsyncMock()
    
    # Mock Total Enrolled Students query response
    mock_enroll_exec = MagicMock()
    mock_enroll_exec.scalar.return_value = 50  # 50 students enrolled
    
    # Mock Session Rows query response
    mock_session_exec = MagicMock()
    
    # Build structural mock session objects mimicking SQLAlchemy models
    mock_session_obj = MagicMock()
    mock_session_obj.created_at.strftime.return_value = "May 2026"
    
    # Simulated data row tuple list: (AcademicSession, present_count)
    mock_session_exec.all.return_value = [
        (mock_session_obj, 40),  # Session 1: 40 present, 10 absent
        (mock_session_obj, 45)   # Session 2: 45 present, 5 absent
    ]

    mock_db.execute.side_effect = [mock_enroll_exec, mock_session_exec]

    result = await analytics_func(
        course_id=33,
        db_session=mock_db,
        verified_user_id=505,
        verified_user_role="lecturer"
    )

    assert result["status"] == "success"
    assert result["course_id"] == 33
    
    summary = result["overall_summary"]
    assert summary["total_enrolled_students"] == 50
    assert summary["total_sessions_conducted"] == 2
    # Grand total possible: 2 sessions * 50 students = 100. Present: 45 + 40 = 85 -> 85.0%
    assert summary["cumulative_attendance_rate"] == "85.0%"
    
    assert "May 2026" in result["monthly_breakdown"]