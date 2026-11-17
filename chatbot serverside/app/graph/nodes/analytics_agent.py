"""
app/graph/nodes/analytics_agent.py
"""
import json
import inspect  # ◄── Ensure this is imported
from langchain_core.messages import SystemMessage, ToolMessage
from app.graph.state import AttendifyAgentState
from langchain_core.runnables import RunnableConfig
from app.graph.llm import get_chatbot_llm
from app.graph.prompts import ANALYTICS_NODE_PROMPT

async def analytics_agent_node(state: AttendifyAgentState, config: RunnableConfig, tools_by_name: dict) -> dict:
    """Executes database queries for attendance logs, summaries, and overrides."""
    llm = get_chatbot_llm()

    analytics_tools = [v for k, v in tools_by_name.items() if k in {
        "get_class_analytics",
        "fetch_student_attendance_percentage",
        "get_my_attendance_history",
        "get_absentee_report",
        "override_attendance",
    }]

    bound_llm = llm.bind_tools(analytics_tools) if analytics_tools else llm

    course_ctx = state.get("active_course_context") or "Not Specified"
    user_role = state.get("verified_user_role") or "student"
    user_id = state.get("verified_user_id") or "Unknown"

    enriched_prompt = (
        f"{ANALYTICS_NODE_PROMPT}\n\n"
        f"⏳ [METADATA CONTEXT LAYER — DO NOT ASK USER FOR THESE DETAILS]:\n"
        f"- Active Course ID Context: {course_ctx}\n"
        f"- Authenticated User ID: {user_id}\n"
        f"- User Security Role: {user_role}\n"
        f"If a tool requires a 'course_id', use the Active Course ID Context provided above automatically."
    )

    response = await bound_llm.ainvoke(
        [SystemMessage(content=enriched_prompt)] + list(state["messages"])
    )

    updates: dict = {"messages": [response], "next_routing_step": "supervisor"}

    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_messages = []

        # Safely capture context values out-of-band
        db_session = config["configurable"].get("db_session")
        verified_user_id = config["configurable"].get("verified_user_id")
        verified_user_role = config["configurable"].get("verified_user_role")

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_fn = tools_by_name.get(tool_name)

            if tool_fn:
                try:
                    execution_kwargs = {**tool_args}
                    
                    # ✅ Secure the true underlying function (handles async/sync tools perfectly)
                    actual_func = tool_fn.coroutine if tool_fn.coroutine else tool_fn.func
                    
                    # Inspect the true function signature
                    sig = inspect.signature(actual_func)
                    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

                    if accepts_kwargs or "db_session" in sig.parameters:
                        execution_kwargs["db_session"] = db_session
                    if accepts_kwargs or "verified_user_id" in sig.parameters:
                        execution_kwargs["verified_user_id"] = verified_user_id
                    if accepts_kwargs or "verified_user_role" in sig.parameters:
                        execution_kwargs["verified_user_role"] = verified_user_role
                    if accepts_kwargs or "config" in sig.parameters:
                        execution_kwargs["config"] = config

                    # ✅ Execute the correct non-None function variable
                    raw_result = await actual_func(**execution_kwargs)
                    
                    tool_messages.append(
                        ToolMessage(content=json.dumps(raw_result), tool_call_id=tool_call["id"], name=tool_name)
                    )
                except Exception as exc:
                    error_msg = str(exc)
                    tool_messages.append(
                        ToolMessage(content=json.dumps({"status": "error", "detail": error_msg}), tool_call_id=tool_call["id"], name=tool_name)
                    )
                    updates["last_tool_error"] = error_msg

        if tool_messages:
            # Always pass the tool outputs back to synthesise a clean conversational answer
            final_response = await bound_llm.ainvoke(
                [SystemMessage(content=enriched_prompt)] + list(state["messages"]) + [response] + tool_messages
            )
            updates["messages"] = [response] + tool_messages + [final_response]

    return updates