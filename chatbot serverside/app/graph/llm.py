# app/graph/llm.py
from functools import lru_cache
from typing import Any, Sequence

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chatbot_llm():
    """
    Returns a unified, resilient LLM chain with automatic fallback.
    The instance is cached at module level via @lru_cache so model objects
    are not re-created on every node call.

    Tool binding (bind_tools) is done separately in each node because
    different nodes bind different tool subsets. Binding does not mutate
    the cached base model — it returns a new RunnableSequence.
    """
    settings = get_settings()

    # 1. Initialize Primary Model (Gemini)
    primary_model = ChatGoogleGenerativeAI(
        model=settings.primary_llm_model,
        google_api_key=settings.google_api_key.get_secret_value(),
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=True,
    )

    # 2. Initialize Fallback Model (Groq / Llama)
    fallback_model = ChatGroq(
        model=settings.fallback_llm_model,
        groq_api_key=settings.groq_api_key.get_secret_value(),
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=True,
    )

    # 3. Return the self-healing runnable chain (no tools bound here)
    return primary_model.with_fallbacks([fallback_model])