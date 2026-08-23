"""
Application settings, loaded from environment variables / .env.

Centralizing config here means every other module (LLM client, FastAPI app,
logging) reads from one typed object instead of scattered os.getenv calls.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # -- LLM provider -----------------------------------------------------
    llm_provider: Literal["gemini", "azure_openai"] = Field(default="gemini")

    gemini_api_key: str = Field(default="", description="Used when llm_provider=openai")
    gemini_model: str = Field(default="gemini-3.5-flash")

    azure_openai_api_key: str = Field(default="")
    azure_openai_endpoint: str = Field(default="")
    azure_openai_deployment: str = Field(default="")
    azure_openai_api_version: str = Field(default="2024-08-01-preview")

    llm_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_max_retries: int = Field(default=3, ge=0)
    llm_request_timeout_seconds: int = Field(default=60, ge=1)

    # -- LangSmith (LLM call tracing/observability) --------------------------
    # Off by default so local dev/tests never need a LangSmith account. When
    # enabled, every chat model call made via get_chat_model() (extraction,
    # matching, evaluation, assignment generation) is traced automatically -
    # see infrastructure/llm/chat_model_factory.py.
    langsmith_tracing: bool = Field(default=False)
    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="ai-recruitment-assistant")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com")

    # -- App behavior -------------------------------------------------------
    max_upload_mb: int = Field(default=15, ge=1)
    log_level: str = Field(default="INFO")
    max_concurrent_llm_calls: int = Field(default=4, ge=1)

    # -- Email (SMTP) -----------------------------------------------------------
    # If any of these are missing, emails are logged instead of sent (see
    # infrastructure/email/email_sender.py) - safe default for local dev.
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="")

    # Same stray-whitespace guard as the AWS fields below - a leading/
    # trailing space on SMTP_HOST or SMTP_USERNAME is enough to make
    # smtplib fail to connect/authenticate with a cryptic error.
    @field_validator("smtp_host", "smtp_username", "smtp_password", "smtp_from_email", mode="before")
    @classmethod
    def _strip_smtp_fields(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    # Base URL of the candidate-facing frontend, used to build submission
    # links in the assignment email (e.g. "https://myapp.vercel.app").
    frontend_public_url: str = Field(default="http://localhost:5173")

    # Base URL of THIS backend, used to build an absolute candidate-facing
    # assignment link when HR uploaded/generated a file instead of giving a
    # Google Drive link (the token-gated /api/v1/submissions/{token}/assignment
    # route, not the HR-only /api/v1/assignments/{id}/download route).
    backend_public_url: str = Field(default="http://localhost:8000")

    # -- Auth (JWT + OTP password reset) -----------------------------------
    # CHANGE THIS in production - a real random secret, not the placeholder.
    jwt_secret_key: str = Field(default="change-me-in-production-use-a-real-random-secret")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60 * 12)  # 12 hours
    otp_expire_minutes: int = Field(default=10)

    # -- Database -------------------------------------------------------------
    # SQLite by default (zero infra to start). Swap to Postgres for real
    # concurrent/bulk load by setting DATABASE_URL to an asyncpg URL, e.g.
    # "postgresql+asyncpg://user:pass@host/dbname" - no code changes needed,
    # SQLAlchemy's async engine handles both via the same interface.
    database_url: str = Field(default="sqlite+aiosqlite:///./reviewer.db")
    # Comma-separated list of allowed frontend origins, e.g.
    # "https://myapp.vercel.app,http://localhost:5173". Needed because in
    # production the frontend (Vercel) and backend (Render) live on
    # different origins - without this, browsers block every request.
    #
    # NoDecode tells pydantic-settings NOT to try to JSON-parse this env
    # var before our validator runs (its default behavior for list-typed
    # fields is to expect a JSON array string like '["a","b"]', which
    # would reject a plain comma-separated value with a confusing error).
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Comma-separated allowed origins for CORS.",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # -- 3-call architecture -------------------------------------------------
    # The pipeline makes EXACTLY 3 LLM calls per assignment, always:
    #   1. extraction (whole question paper -> all questions)
    #   2. matching   (whole submission -> all answers)
    #   3. evaluation (all question/answer pairs -> all reviews)
    # No per-section or per-question calls, and no batching fallback that
    # could add extra calls. If a document is larger than the limits below,
    # it is TRUNCATED (kept as head+tail) rather than split into more calls,
    # so the call count never changes.
    max_chars_extraction: int = Field(
        default=24000, ge=1000, description="Max question-paper chars sent in the single extraction call."
    )
    max_chars_matching: int = Field(
        default=24000, ge=1000, description="Max submission chars sent in the single matching call."
    )
    max_chars_evaluation: int = Field(
        default=28000, ge=1000, description="Max combined question+answer chars sent in the single evaluation call."
    )

    # -- Scoring ------------------------------------------------------------
    score_dimensions: tuple[str, ...] = (
        "requirement_coverage",
        "technical_correctness",
        "ai_engineering",
        "software_engineering",
        "production_readiness",
        "reasoning_depth",
    )
    max_score_per_dimension: int = 10

    # -- File storage ---------------------------------------------------------
    # "local" (default) writes to local_storage_dir - zero cloud account
    # needed to run the app. "s3" requires the aws_* fields below. Both
    # backends implement the same FileStorage interface (see
    # infrastructure/storage/), so nothing else in the app changes when
    # you switch.
    storage_backend: Literal["local", "s3"] = Field(default="local")
    local_storage_dir: str = Field(default="./data/storage")

    aws_s3_bucket: str = Field(default="")
    aws_region: str = Field(default="ap-south-1")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    # Only set for S3-compatible non-AWS endpoints (e.g. MinIO in local
    # dev/tests). Leave blank for real AWS S3.
    aws_s3_endpoint_url: str = Field(default="")

    # Stray leading/trailing whitespace in these (a copy-paste artifact in
    # .env or an OS-level env var) fails boto3's bucket-name/credential
    # validation with a confusing ParamValidationError, so trim it here
    # once instead of at every call site.
    @field_validator(
        "aws_s3_bucket", "aws_region", "aws_access_key_id", "aws_secret_access_key", "aws_s3_endpoint_url",
        mode="before",
    )
    @classmethod
    def _strip_aws_fields(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    # -- Retention ------------------------------------------------------------
    # Rejected-at-screening and finally-rejected candidates' resume/
    # submission files and extracted text are deleted this many days
    # after they enter that status. Spec says "30-90 days"; 60 is the
    # midpoint default, override per deployment.
    rejected_candidate_retention_days: int = Field(default=60, ge=30, le=90)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
