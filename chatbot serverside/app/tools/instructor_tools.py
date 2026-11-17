"""
app/tools/instructor_tools.py  —  Phase 2: Lecturer-Scoped Management Tools
───────────────────────────────────────────────────────────────────────────
Provides data queries optimized for purely conversational text responses.

All tools use config: RunnableConfig for context injection so they work
correctly when invoked via tool_fn.ainvoke(args, config=config).
"""
import datetime
import structlog
from typing import Any

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_log import Session as AcademicSession, Attendance, CheckInEnum
from app.models.course import Course, Enrollment
from app.models.user import User
from app.schemas.tools_input import (
    AttendanceOverrideInput,
    ClassAnalyticsInput,
    AbsenteeReportInput,
)

log = structlog.get_logger()


def make_instructor_tools() -> list:
    """
    Factory compiling tools restricted to lecturers and administrators.
    """

    @tool(args_schema=AttendanceOverrideInput)
    async def override_attendance(
        student_id: int,
        course_id: int,
        session_date: str,
        new_status: str,
        config: RunnableConfig = None,
    ) -> dict[str, Any]:
        """
        Manually overrides a student's attendance log state.
        To mark a student present, enter new_status='PRESENT'. To mark them absent, enter new_status='ABSENT'.
        """
        db: AsyncSession = config["configurable"].get("db_session")
        lecturer_id: int = config["configurable"].get("verified_user_id")
        user_role: str = config["configurable"].get("verified_user_role")

        if not db:
            return {"status": "error", "detail": "Missing database session."}

        if user_role not in ["lecturer", "admin"]:
            return {"status": "error", "detail": "Unauthorized: Action restricted to faculty staff logs."}

        if new_status.upper() not in ["PRESENT", "ABSENT"]:
            return {"status": "error", "detail": "Invalid target status parameter. Choose 'PRESENT' or 'ABSENT'."}

        parsed_date = datetime.date.fromisoformat(session_date) if isinstance(session_date, str) else session_date

        session_stmt = select(AcademicSession).where(
            AcademicSession.course_id == course_id,
            AcademicSession.lecturer_id == lecturer_id,
            func.date(AcademicSession.created_at) == parsed_date
        )
        session_row = (await db.execute(session_stmt)).scalar_one_or_none()

        if not session_row:
            return {
                "status": "error",
                "detail": f"No verified class session found for course {course_id} on {session_date} under your lecturer ID."
            }

        log_stmt = select(Attendance).where(
            Attendance.session_id == session_row.session_id,
            Attendance.student_id == student_id
        )
        existing_log = (await db.execute(log_stmt)).scalar_one_or_none()

        if new_status.upper() == "PRESENT":
            if not existing_log:
                new_presence = Attendance(
                    session_id=session_row.session_id,
                    student_id=student_id,
                    checkin_method=CheckInEnum.manual,
                    scan_time=datetime.datetime.now(datetime.timezone.utc)
                )
                db.add(new_presence)
                await db.flush()
                await db.commit()
            action_taken = "CREATED_PRESENCE_RECORD"
        else:
            if existing_log:
                await db.delete(existing_log)
                await db.flush()
                await db.commit()
            action_taken = "DELETED_PRESENCE_RECORD_MARKED_ABSENT"

        log.info(
            "instructor.override_attendance",
            action=action_taken,
            student_id=student_id,
            course_id=course_id,
            session_date=str(parsed_date),
            lecturer_id=lecturer_id,
        )

        return {
            "status": "success",
            "action_executed": action_taken,
            "student_id": student_id,
            "session_id": session_row.session_id,
            "assigned_final_state": new_status.upper()
        }

    @tool(args_schema=ClassAnalyticsInput)
    async def get_class_analytics(
        course_id: int, 
        db_session: Any = None, 
        verified_user_id: Any = None, 
        verified_user_role: Any = None
    ) -> dict[str, Any]:
        """
        Computes text-optimized attendance percentages and trends for an entire course section.
        Use this when a lecturer asks for statistical metrics or month-by-month overviews.
        """
        db = db_session
        user_role = verified_user_role

        if not db:
            return {"status": "error", "detail": "Database connection handle missing context."}
        if user_role not in ["lecturer", "admin"]:
            return {"status": "error", "detail": "Unauthorized: Access restricted to faculty members."}

        enroll_stmt = select(func.count(Enrollment.student_id)).where(Enrollment.course_id == course_id)
        total_enrolled = (await db.execute(enroll_stmt)).scalar() or 0

        if total_enrolled == 0:
            return {"status": "empty", "detail": f"Course ID {course_id} currently has zero registered student profiles."}

        stmt = (
            select(AcademicSession, func.count(Attendance.log_id).label("present_count"))
            .outerjoin(Attendance, Attendance.session_id == AcademicSession.session_id)
            .where(AcademicSession.course_id == course_id)
            .group_by(AcademicSession.session_id)
            .order_by(AcademicSession.created_at.asc())
        )
        rows = (await db.execute(stmt)).all()

        if not rows:
            return {"status": "empty", "detail": f"No completed sessions are logged for course section {course_id}."}

        from collections import defaultdict
        monthly_stats = defaultdict(lambda: {"total_present": 0, "total_absent": 0, "session_count": 0})

        for academic_session, present_count in rows:
            month_key = academic_session.created_at.strftime("%B %Y")
            absent_count = max(0, total_enrolled - present_count)
            
            monthly_stats[month_key]["total_present"] += present_count
            monthly_stats[month_key]["total_absent"] += absent_count
            monthly_stats[month_key]["session_count"] += 1

        monthly_breakdown = {}
        grand_total_present = 0
        grand_total_possible = 0

        for month, metrics in monthly_stats.items():
            month_possible = metrics["session_count"] * total_enrolled
            month_rate = round((metrics["total_present"] / month_possible) * 100, 1) if month_possible else 0.0
            
            monthly_breakdown[month] = {
                "attendance_rate": f"{month_rate}%",
                "sessions_held": metrics["session_count"],
                "avg_present_students_per_class": round(metrics["total_present"] / metrics["session_count"], 1),
                "avg_absent_students_per_class": round(metrics["total_absent"] / metrics["session_count"], 1)
            }
            grand_total_present += metrics["total_present"]
            grand_total_possible += month_possible

        overall_rate = round((grand_total_present / grand_total_possible) * 100, 1) if grand_total_possible else 0.0

        return {
            "status": "success",
            "course_id": course_id,
            "overall_summary": {
                "cumulative_attendance_rate": f"{overall_rate}%",
                "total_enrolled_students": total_enrolled,
                "total_sessions_conducted": len(rows)
            },
            "monthly_breakdown": monthly_breakdown
        }

    @tool(args_schema=AbsenteeReportInput)
    async def get_absentee_report(course_id: int, session_date: str, config: RunnableConfig = None) -> dict[str, Any]:
        """
        Returns the names and database IDs of all students registered for a course who missed a class session.
        Use this to handle queries like 'Who missed class today?'.
        """
        db: AsyncSession = config["configurable"].get("db_session")

        if not db:
            return {"status": "error", "detail": "Missing database session."}

        parsed_date = datetime.date.fromisoformat(session_date) if isinstance(session_date, str) else session_date

        session_stmt = select(AcademicSession).where(
            AcademicSession.course_id == course_id,
            func.date(AcademicSession.created_at) == parsed_date
        )
        academic_session = (await db.execute(session_stmt)).scalar_one_or_none()

        if not academic_session:
            return {"status": "error", "explanation": f"No classroom entry matching date {session_date} could be located."}

        absent_students_stmt = (
            select(User.id, User.name)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(Enrollment.course_id == course_id)
            .where(
                ~User.id.in_(
                    select(Attendance.student_id).where(Attendance.session_id == academic_session.session_id)
                )
            )
        )

        result = await db.execute(absent_students_stmt)
        absentees = result.all()

        return {
            "course_id": course_id,
            "session_id": academic_session.session_id,
            "session_date": session_date,
            "absent_count": len(absentees),
            "students": [{"student_id": row.id, "name": row.name, "status": "ABSENT"} for row in absentees]
        }

    return [
        override_attendance,
        get_class_analytics,
        get_absentee_report,
    ]