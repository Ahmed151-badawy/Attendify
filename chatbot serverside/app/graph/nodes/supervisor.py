"""
app/graph/nodes/supervisor.py  —  Phase 3: Central Routing Supervisor
──────────────────────────────────────────────────────────────────────
Evaluates the conversation state and guides routing paths via conditional edges.
"""
import structlog
from langchain_core.messages import AIMessage, SystemMessage

from app.core.config import get_settings
from app.graph.prompts import (
    SUPERVISOR_ROUTING_PROMPT,
    STUDENT_SYSTEM_PROMPT,
    INSTRUCTOR_SYSTEM_PROMPT,
)
from app.graph.state import AttendifyAgentState
from app.graph.llm import get_chatbot_llm

settings = get_settings()
log = structlog.get_logger()


def _get_role_prompt(role: str) -> str:
    """Returns the role-appropriate system prompt for direct conversational replies."""
    if role in ("lecturer", "admin"):
        return INSTRUCTOR_SYSTEM_PROMPT
    return STUDENT_SYSTEM_PROMPT


async def supervisor_node(state: AttendifyAgentState) -> dict:
    """
    Evaluates the conversation history state and outputs the next node routing label.
    Valid routing outputs: "analytics", "end".
    """
    iteration = state.get("iteration_count", 0) + 1

    # ── Runaway Loop Protection Guard ────────────────────────────────────────
    if iteration > settings.agent_max_iterations:
        log.warning(
            "supervisor.loop.exceeded",
            iteration=iteration,
            max=settings.agent_max_iterations,
            session_id=state.get("session_id"),
        )
        return {
            "iteration_count": iteration,
            "next_routing_step": "end",
            "messages": [
                AIMessage(
                    content=(
                        "I encountered an issue processing your request after multiple internal loops. "
                        "Please try rephrasing your question or contact support if this error persists."
                    )
                )
            ],
        }

    # ── SECURE SHORT-CIRCUIT: Check if Sub-Agent Already Responded ───────────
    # If the last message in history is a final AIMessage (not an intermediate tool call),
    # the request is completely fulfilled. Route to "end" instantly without an LLM call!
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
            log.info(
                "supervisor.routing.completed",
                label="end",
                reason="Sub-agent final response detected.",
                iteration=iteration,
                session_id=state.get("session_id"),
            )
            return {
                "iteration_count": iteration,
                "next_routing_step": "end",
                "last_tool_error": None,
            }

    # ── Graceful Core Failure Recovery ────────────────────────────────────────
    last_error = state.get("last_tool_error")
    if last_error and iteration > 3:
        # ... (keep your existing error recovery block here)
        pass

    # ── LLM Intent Routing Splitter ───────────────────────────────────────────
    llm = get_chatbot_llm()
    recent_messages = list(state["messages"])[-6:]

    response = await llm.ainvoke(
        [SystemMessage(content=SUPERVISOR_ROUTING_PROMPT)] + recent_messages
    )

    routing_label = (
        response.content.strip().replace('"', "").replace("'", "").lower()
    )

    # Validate output labels — fallback to "end" to safely close loops
    valid_labels = {"analytics", "end"}
    if routing_label not in valid_labels:
        log.warning(
            "supervisor.invalid_label",
            raw_label=routing_label,
            fallback="end",
            session_id=state.get("session_id"),
        )
        routing_label = "end"

    log.info(
        "supervisor.routing",
        label=routing_label,
        iteration=iteration,
        session_id=state.get("session_id"),
    )

    result = {
        "iteration_count": iteration,
        "next_routing_step": routing_label,
        "last_tool_error": None,
    }

    # ── Generate Conversational Response for Direct "end" Routing ─────────────
    if routing_label == "end" and iteration == 1:
        user_role = state.get("verified_user_role", "student")
        role_prompt = _get_role_prompt(user_role)

        conversational_response = await llm.ainvoke(
            [SystemMessage(content=role_prompt)] + recent_messages
        )
        result["messages"] = [conversational_response]
        log.debug(
            "supervisor.direct_response",
            session_id=state.get("session_id"),
        )

    return result


def route_from_supervisor(state: AttendifyAgentState) -> str:
    """
    Pure conditional edge function reading the active supervisor routing decision.
    """
    return state.get("next_routing_step", "end")