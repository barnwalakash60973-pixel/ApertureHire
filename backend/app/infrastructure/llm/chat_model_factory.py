"""
Builds the LangChain chat model used for all LLM calls in this app.

Centralizing this means every evaluator/matcher shares the same retry,
timeout, and provider configuration instead of constructing clients ad hoc.
"""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _configure_langsmith(settings: Settings) -> None:
    """Turn on LangChain's built-in tracer by setting its env vars.

    LangChain/LangSmith read tracing config from the environment, not from
    constructor args, so this is the one place that needs to run before any
    chat model is built. Every ainvoke() call made through the model this
    factory returns - extraction, matching, evaluation, assignment
    generation - then shows up in the LangSmith project automatically.
    """
    if not settings.langsmith_tracing:
        return

    if not settings.langsmith_api_key:
        logger.warning("LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is empty - tracing will fail to authenticate.")

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    logger.info("LangSmith tracing enabled for project %r", settings.langsmith_project)


def build_chat_model(settings: Settings) -> BaseChatModel:
    """Construct the configured chat model."""

    _configure_langsmith(settings)

    if settings.llm_provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            temperature=settings.llm_temperature,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_request_timeout_seconds,
        )

    # settings.llm_provider is Literal["gemini", "azure_openai"], so this is
    # the only remaining case - pydantic rejects any other value at startup.
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.llm_temperature,
    )


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Return a process-wide cached chat model instance."""
    return build_chat_model(get_settings())
