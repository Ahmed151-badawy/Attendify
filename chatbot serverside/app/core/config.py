"""
app/core/config.py
─────────────────
Centralised settings loaded from environment variables.
Pydantic-settings validates types at startup — no silent misconfiguration.
"""
from functools import lru_cache
from pydantic import Field, PostgresDsn, SecretStr, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Attendify Chatbot API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        ...,
        description="Async SQLAlchemy connection string for Neon Postgres (using asyncpg driver).",
    )

    # ── Security ──────────────────────────────────────────────────────────────
    jwt_secret_key: SecretStr = Field(
        ...,  # Forces value extraction from .env at startup
        description="HS256 signing key for JWT tokens.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── LLM ───────────────────────────────────────────────────────────────────
    google_api_key: SecretStr = Field(
        ..., 
        description="Google AI Studio API key (Free Tier)."
    )
    primary_llm_model: str = "gemini-2.5-flash"  # Extremely fast, free, outstanding tool calling

    # Fallback Model: Groq Cloud
    groq_api_key: SecretStr = Field(
        ..., 
        description="Groq Cloud API Key used as an automated fallback gateway."
    )
    fallback_llm_model: str = "llama-3.3-70b-versatile"  # Highly capable open-weight alternative
    
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2048

    # ── Graph / LangGraph ─────────────────────────────────────────────────────
    agent_max_iterations: int = Field(
        default=12,
        description="Hard cap on supervisor loop iterations to prevent runaway chains.",
    )
    checkpointer_backend: str = Field(
        default="sqlite",
        description="'sqlite' (dev) or 'postgres' (prod).",
    )

    # ── Observability ─────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = Field(
        default=False,
        validation_alias=AliasChoices("langsmith_tracing", "langchain_tracing_v2")
    )
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias=AliasChoices("langsmith_endpoint", "langchain_endpoint")
    )
    langchain_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("langsmith_api_key", "langchain_api_key")
    )
    langchain_project: str = Field(
        default="attendify-chatbot",
        validation_alias=AliasChoices("langsmith_project", "langchain_project")
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns a singleton Settings instance (cached after first call)."""
    return Settings()
