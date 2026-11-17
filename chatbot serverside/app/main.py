"""
app/main.py  —  FastAPI Application Entry Point
────────────────────────────────────────────────
Registers all routers, handles application lifespans, and configures middleware.
The chat routes implement Phase 2 (role gateways) and Phase 4 (Pure Text SSE streaming).
"""
import os
import json
import traceback
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.core.config import get_settings
from app.core.database import AsyncSession, get_db, engine
from app.core.security import UserSession, create_access_token, get_current_user
from app.graph.state import AttendifyAgentState
from app.graph.workflow import get_or_create_graph
from app.schemas.chat import ChatRequest, ChatInitResponse, TokenRequest, TokenResponse

settings = get_settings()
log = structlog.get_logger()

# LangChain automatically triggers background hooks if it spots these keys.
# We explicitly overwrite or unset them in memory to kill background tracing loops.
if not settings.langchain_tracing_v2:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ.pop("LANGCHAIN_API_KEY", None)
    os.environ.pop("LANGSMITH_API_KEY", None)


# ── Lifespan (Startup / Shutdown Infrastructure) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("attendify.startup", env=settings.debug)
    # Tables are maintained and migrated directly via the core backend;
    # the chatbot safely reads and queries them out-of-band.
    yield
    log.info("attendify.shutdown")
    await engine.dispose()


# ── Application Initialization ────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_content(content) -> str:
    """
    Normalizes AIMessage content which may arrive as:
      - A plain string: "Hello there"
      - A list of content blocks (Gemini format): [{'type': 'text', 'text': 'Hello'}]
    Always returns a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content) if content else ""


def _is_final_ai_message(msg) -> bool:
    """
    Returns True only for AIMessages that contain human-readable text
    and were NOT generated as a tool-call request (i.e. they have actual content
    and no pending tool_calls). This filters out:
      - Intermediate AIMessages that only contain tool_calls with no text
      - ToolMessages (raw JSON tool results)
      - Empty messages
    """
    if not isinstance(msg, AIMessage):
        return False
    # If the message has tool_calls but no content, it's an intermediate routing message
    tool_calls = getattr(msg, "tool_calls", None) or []
    content = _normalize_content(getattr(msg, "content", "") or "")
    if tool_calls and not content.strip():
        return False
    return bool(content.strip())


# ── Development Token Minting Endpoint ────────────────────────────────────────
@app.post("/auth/dev-token", response_model=TokenResponse, include_in_schema=settings.debug)
async def mint_dev_token(request: TokenRequest) -> TokenResponse:
    """
    Development-only endpoint: mints a cryptographically signed JWT for sandbox testing.
    Emits a "role" (singular string) key to match the token decoder's expectations.
    """
    # Resolve the primary role string — decoder expects "role": str
    primary_role = request.roles[0] if request.roles else "student"

    token = create_access_token(
        data={
            "sub": str(uuid.uuid4()),
            "email": request.email,
            "role": primary_role,  # singular string — matches _decode_token expectations
            "faculty_id": getattr(request, "faculty_id", None),
        }
    )
    return TokenResponse(access_token=token, token_type="bearer")


# ── Phase 2: Zero-Trust Chat Session Initialization ───────────────────────────
@app.post(f"{settings.api_v1_prefix}/chat/init", response_model=ChatInitResponse)
async def initialize_chat_session(
    user: UserSession = Depends(get_current_user),
) -> ChatInitResponse:
    """
    Initialises an isolated conversation thread ID and verifies system permissions.
    Role definitions are derived strictly from the verified JWT cryptograms.
    """
    session_id = str(uuid.uuid4())

    # Map validation triggers precisely to your database RoleEnum naming standards
    if user.primary_role in ["lecturer", "admin"]:
        system_prompt_preview = "Lecturer Mode Enabled — Section metrics summaries and manual roll-call corrections active."
        capabilities = ["class_analytics", "manual_attendance_override", "absentee_roster_generation"]
    else:
        system_prompt_preview = "Student Mode Enabled — Personal attendance log evaluations active."
        capabilities = ["personal_attendance_history"]

    log.info(
        "chat.session.init",
        user_id=user.user_id,
        role=user.primary_role,
        session_id=session_id,
    )

    return ChatInitResponse(
        session_id=session_id,
        user_id=user.user_id,
        role=user.primary_role,
        capabilities=capabilities,
        system_prompt_preview=system_prompt_preview,
    )


# ── Phase 4: Pure Text-Driven Server-Sent Events (SSE) Endpoint ───────────────
@app.post(f"{settings.api_v1_prefix}/chat/message")
async def send_message(
    request: ChatRequest,
    user: UserSession = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Streams conversational text responses block-by-block using safe HTTP Server-Sent Events.
    Only final human-readable AI responses are emitted — intermediate tool calls and raw
    tool result messages are filtered out before reaching the client.
    """
    # Retrieve the cached graph (built once per role, not per request)
    graph = get_or_create_graph(user.primary_role)

    # Assemble initial state parameters mapping strictly to your database keys
    initial_state: AttendifyAgentState = {
        "messages": [HumanMessage(content=request.message)],
        "verified_user_id": int(user.user_id),
        "verified_user_role": user.primary_role,
        "faculty_id": getattr(user, "faculty_id", None),
        "session_id": request.session_id,
        "active_course_context": int(request.course_context) if request.course_context else None,
        "active_session_date": None,
        "next_routing_step": "supervisor",
        "iteration_count": 0,
        "pending_ui_payload": None,
        "last_tool_error": None,
    }

    config = {
        "configurable": {
            "thread_id": request.session_id,
            "db_session": db,
            "verified_user_id": int(user.user_id),
            "verified_user_role": user.primary_role,
            "faculty_id": getattr(user, "faculty_id", None),
        }
    }

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Track which messages have already been streamed to avoid duplicates
            streamed_ids: set = set()

            async for chunk in graph.astream(initial_state, config=config):
                print(f"🪐 [LangGraph Active Node]: {list(chunk.keys())}")
                for node_name, node_output in chunk.items():
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        # Skip messages we've already sent
                        msg_id = id(msg)
                        if msg_id in streamed_ids:
                            continue
                        streamed_ids.add(msg_id)

                        # Only stream final human-readable AI text — filter out:
                        # - ToolMessages (raw JSON tool responses)
                        # - Intermediate AIMessages that only carry tool_calls (no text)
                        if not _is_final_ai_message(msg):
                            continue

                        content = _normalize_content(msg.content).strip()
                        if not content:
                            continue

                        yield f"event: text_chunk\ndata: {json.dumps({'text': content, 'node': node_name})}\n\n"

            # Terminal boundary transmission marker
            yield "event: done\ndata: {}\n\n"

        except Exception as exc:
            log.error(
                "chat.stream.error",
                error=str(exc),
                traceback=traceback.format_exc(),
                session_id=request.session_id,
            )
            error_payload = {"error": "An internal data streaming anomaly occurred.", "code": "STREAM_FAULT"}
            yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disables proxy buffering to maximize push responsiveness
        },
    )


# ── Baseline Diagnostics Infrastructure ──────────────────────────────────────────
@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns service health. Tests actual DB connectivity by executing a lightweight
    query rather than returning a static response.
    """
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        log.error("health.db.error", error=str(exc))
        db_status = "error"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "service": settings.app_name,
        "database": db_status,
    }