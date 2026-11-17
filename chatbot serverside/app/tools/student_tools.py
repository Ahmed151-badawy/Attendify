"""
app/tools/student_tools.py
──────────────────────────
"""
from typing import Any
from langchain_core.tools import tool
from sqlalchemy import select, func
from app.models.attendance_log import Session as AcademicSession, Attendance

def make_student_tools() -> list:

    @tool
    async def fetch_student_attendance_percentage(
        course_id: int, 
        db_session: Any = None, 
        verified_user_id: Any = None
    ) -> dict[str, Any]:
        """
        Calculates the cumulative attendance percentage for the authenticated student in a specific course.
        Use this whenever a student asks 'what is my attendance?'.
        """
        db = db_session
        student_id = verified_user_id

        if not db:
            return {"status": "error", "detail": "Database connection handle missing context."}

        session_stmt = select(func.count(AcademicSession.session_id)).where(AcademicSession.course_id == course_id)
        total_sessions = (await db.execute(session_stmt)).scalar() or 0

        if total_sessions == 0:
            return {"status": "success", "percentage": "0%", "detail": "No sessions have been recorded for this course yet."}

        attendance_stmt = select(func.count(Attendance.log_id)).join(
            AcademicSession, Attendance.session_id == AcademicSession.session_id
        ).where(
            AcademicSession.course_id == course_id,
            Attendance.student_id == student_id
        )
        attended_sessions = (await db.execute(attendance_stmt)).scalar() or 0

        percentage = round((attended_sessions / total_sessions) * 100, 1)

        return {
            "status": "success",
            "course_id": course_id,
            "student_id": student_id,
            "total_sessions": total_sessions,
            "attended_sessions": attended_sessions,
            "percentage": f"{percentage}%"
        }

    @tool
    async def get_my_attendance_history(
        course_id: int, 
        db_session: Any = None, 
        verified_user_id: Any = None
    ) -> dict[str, Any]:
        """
        Retrieves a detailed list of every class session date and whether the student was present or absent.
        """
        db = db_session
        student_id = verified_user_id

        if not db:
            return {"status": "error", "detail": "Database connection handle missing context."}

        stmt = select(AcademicSession).where(AcademicSession.course_id == course_id).order_by(AcademicSession.created_at.desc())
        sessions = (await db.execute(stmt)).scalars().all()

        if not sessions:
            return {"status": "empty", "detail": "No active sessions found for this course tracking record."}

        history = []
        for sess in sessions:
            log_stmt = select(Attendance).where(
                Attendance.session_id == sess.session_id,
                Attendance.student_id == student_id
            )
            is_present = (await db.execute(log_stmt)).scalar_one_or_none() is not None
            
            history.append({
                "session_id": sess.session_id,
                "date": sess.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "PRESENT" if is_present else "ABSENT"
            })

        return {
            "status": "success",
            "course_id": course_id,
            "history": history
        }

    return [fetch_student_attendance_percentage, get_my_attendance_history]