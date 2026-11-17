"""
app/core/database.py
────────────────────
Async SQLAlchemy engine, session factory, and base declarative class.
All ORM models inherit from `Base`; every database interaction flows
through `get_db()` dependency-injected into FastAPI route handlers.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
# echo=False in prod; flip to True only when debugging generated SQL.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,       # validate connections before use
    pool_size=5,              # baseline persistent connections
    max_overflow=10,          # burst capacity above pool_size
    pool_recycle=300,         # recycle connections every 5 min (Neon idle timeout safety)
    connect_args={"ssl": True}
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base.  All SQLAlchemy models inherit from this."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a database session scoped to one request.
    Always rolls back on exception; always closes on exit.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables — used during startup in development mode."""
    async with engine.begin() as conn:
        from app.models import attendance_log, course, user  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
