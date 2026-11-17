"""
app/graph/state.py  —  Phase 3: LangGraph Global State Schema
─────────────────────────────────────────────────────────────
The TypedDict that flows through every node in the LangGraph engine.
"""
from typing import Annotated, Any, Sequence, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession


class AttendifyAgentState(TypedDict):
    """
    Unified state schema persisted across all nodes and conversation turns.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    """Full message timeline. The add_messages reducer appends without replacing."""

    verified_user_id: int
    """Verified user database integer ID from JWT — source of truth for IDOR checks."""

    verified_user_role: Literal["student", "lecturer", "admin"]
    """Determines safe tool injection and system prompt loading blocks."""

    faculty_id: int | None
    """Scopes structural faculty alignment constraints."""

    session_id: str
    """Unique conversation thread ID for the checkpointer mapping."""

    active_course_context: int | None
    """
    Course database integer ID extracted from the context.
    Allows multi-turn conversations without re-stating the course.
    """

    active_session_date: str | None
    """ISO date string for the session being discussed, if applicable."""

    next_routing_step: str
    """
    Edge label written by the Supervisor node.
    Valid values: 'analytics', 'end'.
    """

    iteration_count: int
    """
    Incremented by the Supervisor on each pass.
    Triggers forced termination if it reaches settings.agent_max_iterations.
    """

    pending_ui_payload: dict[str, Any] | None
    """
    JSON chart/table payload staged here before streaming to the client.
    """

    last_tool_error: str | None
    """
    Set by a node when a tool returns an error. Supervisor evaluates this for retries.
    """