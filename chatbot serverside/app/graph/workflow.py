"""
app/graph/workflow.py  —  Phase 3: LangGraph State Machine Assembly
─────────────────────────────────────────────────────────────────────
Compiles the full LangGraph topology.

Performance: The compiled graph is cached per role in a module-level dict.
MemorySaver is thread-safe, so the same graph instance handles concurrent
sessions correctly — conversation threads are isolated by thread_id in config.
"""
import functools

import structlog
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings
from app.graph.nodes.analytics_agent import analytics_agent_node
from app.graph.nodes.supervisor import route_from_supervisor, supervisor_node
from app.graph.state import AttendifyAgentState

# Import unparameterized tool kits
from app.tools.instructor_tools import make_instructor_tools
from app.tools.student_tools import make_student_tools

settings = get_settings()
log = structlog.get_logger()


_graph_cache: dict[str, object] = {}


def build_tools_by_role(role: str) -> dict:
    """
    Assembles role-appropriate tools into a flat name→callable map.
    Enforces that lecturer-scoped modifications cannot bleed into student sessions.
    """
    tools = []

    if role == "student":
        tools.extend(make_student_tools())

    elif role in ["lecturer", "admin"]:
        tools.extend(make_student_tools())
        tools.extend(make_instructor_tools())

    return {t.name: t for t in tools}


def _compile_graph(role: str):
    """
    Builds and compiles the LangGraph state machine for a given role.
    Should only be called once per role — use get_or_create_graph() instead.
    """
    tools_by_name = build_tools_by_role(role)

    bound_analytics = functools.partial(analytics_agent_node, tools_by_name=tools_by_name)

    graph = StateGraph(AttendifyAgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("analytics", bound_analytics)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "analytics": "analytics",
            "end": END,
        },
    )


    graph.add_edge("analytics", "supervisor")


    checkpointer = MemorySaver()

    compiled = graph.compile(checkpointer=checkpointer)
    log.info("graph.compiled", role=role, tools=list(tools_by_name.keys()))
    return compiled


def get_or_create_graph(role: str):
    """
    Returns a cached compiled graph for the given role, building it on first access.

    Args:
        role: The verified user role ("student", "lecturer", or "admin").

    Returns:
        CompiledStateGraph with checkpoint memory tracking active.
    """
    cache_key = "lecturer" if role in ("lecturer", "admin") else "student"

    if cache_key not in _graph_cache:
        log.info("graph.cache.miss", role=cache_key)
        _graph_cache[cache_key] = _compile_graph(role)
    else:
        log.debug("graph.cache.hit", role=cache_key)

    return _graph_cache[cache_key]


async def create_graph(state_context: dict):
    """
    Deprecated: prefer get_or_create_graph(role) for cached access.
    Retained for backwards compatibility.
    """
    user_role = state_context.get("verified_user_role", "student")
    return get_or_create_graph(user_role)
