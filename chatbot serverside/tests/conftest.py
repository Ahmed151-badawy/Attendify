"""
tests/conftest.py — Shared test fixtures.
──────────────────────────────────────────
Provides non-blocking async HTTP clients targeting the FastAPI server application.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import get_settings

settings = get_settings()


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client pointed at the FastAPI test app loop."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client