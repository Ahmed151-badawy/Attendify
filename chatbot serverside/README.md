# Attendify Chatbot

An enterprise-grade AI attendance management chatbot built on FastAPI, LangGraph, and GPT-4o-mini. Implements all 5 phases of the Attendify MVP architecture blueprint.

## Architecture Overview

```
[Phase 1] Hardened API Layer     → Pydantic v2 schemas, SQLAlchemy ORM, IDOR-safe tools
[Phase 2] Zero-Trust Gateways    → JWT RBAC, dynamic tool injection, system prompt isolation
[Phase 3] LangGraph Engine       → Supervisor + Analytics node, checkpointing
[Phase 4] Guardrails & SSE       → Structured JSON outputs, Server-Sent Events streaming
[Phase 5] Observability          → LangSmith tracing, routing eval tests, injection defense
```

## Quick Start

### 1. Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in: OPENAI_API_KEY, JWT_SECRET_KEY, DATABASE_URL
```

### 3. Run (dev mode with SQLite)
```bash
DEBUG=true uvicorn app.main:app --reload --port 8000
```

### 4. Mint a dev token
```bash
curl -X POST http://localhost:8000/auth/dev-token \
  -H "Content-Type: application/json" \
  -d '{"email": "student@uni.edu", "roles": ["student"], "institution_id": "inst-uuid-here"}'
```

### 5. Initialize chat session
```bash
curl -X POST http://localhost:8000/api/v1/chat/init \
  -H "Authorization: Bearer <token>"
```

### 6. Send a message (SSE stream)
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<session_id>", "message": "What is my attendance for CS-402?"}'
```

## Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Role escalation via chat | JWT claims only — chat text never sets roles |
| IDOR (access others' data) | `effective_id = session.user_id` overrides LLM-parsed IDs |
| Prompt injection | Role-scoped system prompts + tool arrays pre-filtered |
| Runaway agent loops | `iteration_count` cap + error surfacing after 3 retries |
| Broad tool signatures | Strict Pydantic v2 schemas — no `**kwargs`, no `dict` |

## SSE Event Types

| Event | Payload |
|-------|---------|
| `text_chunk` | `{"text": "...", "node": "analytics"}` |
| `ui_component` | `{"ui_component_type": "ATTENDANCE_BAR_CHART", "series": [...]}` |
| `error` | `{"error": "...", "code": "STREAM_ERROR"}` |
| `done` | `{}` |

## State Synchronisation (Mobile ↔ Backend)

BLE/QR logs collected offline by the mobile app are uploaded to `/api/v1/attendance/sync` 
as a batch payload before chat session initialisation, ensuring the chat session always 
operates on server-authoritative attendance data rather than client-claimed telemetry.

## Project Structure

```
app/
├── core/          # Config, DB engine, JWT security
├── models/        # SQLAlchemy ORM models
├── schemas/       # Pydantic v2 validation schemas
├── tools/         # Deterministic tool functions (Phase 1)
└── graph/         # LangGraph engine (Phase 3)
    ├── state.py       # Global state TypedDict
    ├── workflow.py    # Graph topology compilation
    ├── prompts.py     # Role-segregated system prompts
    └── nodes/         # Supervisor, Analytics nodes

tests/
├── test_injection.py  # Prompt injection defense (Phase 4/5)
├── test_routing.py    # Supervisor intent evaluation (Phase 5)
└── test_tools.py      # Tool schema enforcement (Phase 1)
```
