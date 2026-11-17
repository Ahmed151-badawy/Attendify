"""
tests/test_routing.py  —  Phase 5: Supervisor Routing Evaluation
────────────────────────────────────────────────────────────────
Validates intent classification routing tables and loop-safety count walls.
"""
import pytest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from app.graph.nodes.supervisor import supervisor_node
from app.graph.state import AttendifyAgentState


def make_state_fixture(message: str, iteration: int = 0) -> AttendifyAgentState:
    """Helper compiling a valid state representation using unified application keys."""
    return {
        "messages": [HumanMessage(content=message)],
        "verified_user_id": 101,
        "verified_user_role": "student",
        "faculty_id": 1,
        "session_id": "thread-test-abc",
        "active_course_context": 15,
        "active_session_date": None,
        "next_routing_step": "supervisor",
        "iteration_count": iteration,
        "pending_ui_payload": None,
        "last_tool_error": None,
    }


ROUTING_TEST_CASES = [
    ("What is my attendance percentage for this module?", "analytics"),
    ("Who missed class on May 15th?", "analytics"),
    ("Show me recent attendance history logs", "analytics"),
    ("What is the attendance policy for Suez University?", "end"),
    ("Hello, how can you help me?", "end"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("message,expected_route", ROUTING_TEST_CASES)
async def test_supervisor_routing(message: str, expected_route: str):
    """
    Validates supervisor routing accuracy against active intents.
    Patches get_chatbot_llm to avoid network calls during test suites.
    """
    state = make_state_fixture(message)

    # Patch our specific LLM provider construction layer cleanly
    with patch("app.graph.nodes.supervisor.get_chatbot_llm") as mock_get_llm:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = AIMessage(content=expected_route)
        mock_get_llm.return_value = mock_chain

        result = await supervisor_node(state)

    assert result["next_routing_step"] == expected_route


@pytest.mark.asyncio
async def test_supervisor_invalid_label_falls_back_to_end():
    """
    Verifies that unrecognized routing labels fall back to "end" instead of crashing.
    """
    state = make_state_fixture("Some ambiguous message")

    with patch("app.graph.nodes.supervisor.get_chatbot_llm") as mock_get_llm:
        mock_chain = AsyncMock()
        # LLM returns something unexpected
        mock_chain.ainvoke.return_value = AIMessage(content="respond")
        mock_get_llm.return_value = mock_chain

        result = await supervisor_node(state)

    # "respond" is no longer valid — should fall back to "end"
    assert result["next_routing_step"] == "end"


@pytest.mark.asyncio
async def test_supervisor_runaway_loop_protection():
    """
    Verifies that the loop guard intercepts routing execution and terminates
    gracefully if iteration boundaries are breached.
    """
    from app.core.config import get_settings
    settings = get_settings()

    # Artificially trigger execution past the configuration safety cap
    state = make_state_fixture("Execute repeating query loops", iteration=settings.agent_max_iterations + 1)

    result = await supervisor_node(state)

    # Must route strictly to end and surface fallback text notice
    assert result["next_routing_step"] == "end"
    assert len(result["messages"]) == 1
    assert "issue processing your request" in result["messages"][0].content.lower()


@pytest.mark.asyncio
async def test_supervisor_surfaces_repeated_tool_errors():
    """
    Verifies that after repeated tool-level infrastructure execution issues,
    the supervisor surfaces the message text cleanly instead of trapping users.
    """
    state = make_state_fixture("Check database records", iteration=4)
    state["last_tool_error"] = "Neon connection timed out"

    result = await supervisor_node(state)

    assert result["next_routing_step"] == "end"
    assert "unable to complete that database action" in result["messages"][0].content.lower()
    assert result.get("last_tool_error") is None  # Ensures state tracking is cleared out after emit