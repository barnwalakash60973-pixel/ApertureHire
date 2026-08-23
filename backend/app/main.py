"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.routes_assignments import router as assignments_router
from app.api.routes_auth import router as auth_router
from app.api.routes_campaign_files import router as campaign_files_router
from app.api.routes_campaigns import router as campaigns_router
from app.api.routes_public import router as public_router
from app.api.routes_submissions import router as submissions_router
from app.core.config import get_settings
from app.core.exceptions import ReviewerError
from app.core.logging import configure_logging, get_logger
from app.core.scheduler import start_scheduler
from app.infrastructure.auth.dependency import get_current_user
from app.infrastructure.db.database import create_all_tables, init_db

logger = get_logger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="AI Recruitment Assistant API",
        version="1.0.0",
        description="""
        AI-powered recruitment platform that automates resume screening,
        assignment generation, assignment evaluation, candidate management,
        and hiring workflow using deterministic logic and Large Language Models.
    """
    )

    # Frontend (Vercel) and backend (Render) are on different origins in
    # production, so the browser will block requests without this.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(router)
    # HR-only routers, guarded by JWT - candidates never see these.
    # Candidate portal (submissions_router) deliberately stays unguarded -
    # candidates authenticate via their mailed token, not a login.
    app.include_router(campaigns_router, dependencies=[Depends(get_current_user)])
    app.include_router(campaign_files_router, dependencies=[Depends(get_current_user)])
    app.include_router(assignments_router, dependencies=[Depends(get_current_user)])
    app.include_router(submissions_router)
    # Public, unauthenticated candidate application intake - the
    # "Candidates Apply" step of the flowchart. Deliberately NOT under
    # get_current_user, same reasoning as submissions_router: this is
    # meant to be linked from LinkedIn/Naukri/the careers page, hit by
    # people who have no HR account.
    app.include_router(public_router)

    @app.on_event("startup")
    async def startup() -> None:
        init_db(settings)
        await create_all_tables()

        # Background jobs: overdue-marking + reminder/overdue emails
        # (hourly) and retention purge of rejected candidates' files
        # (daily). Previously nothing drove these on a timer - see
        # core/scheduler.py docstring for what this does and doesn't fix.
        app.state.scheduler = start_scheduler(settings)

        logger.info("AI Assignment Reviewer started. Database: %s", settings.database_url.split("://")[0])

    @app.on_event("shutdown")
    async def shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        logger.info("AI Assignment Reviewer stopped.")

    @app.exception_handler(ReviewerError)
    async def reviewer_error_handler(
        request: Request,
        exc: ReviewerError,
    ) -> JSONResponse:
        """Handle application-specific exceptions."""

        logger.warning(
            "ReviewerError | %s %s | %s",
            request.method,
            request.url.path,
            str(exc),
        )

        return JSONResponse(
            status_code=400,
            content={
                "error": exc.__class__.__name__,
                "detail": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""

        logger.exception(
            "Unhandled Exception | %s %s",
            request.method,
            request.url.path,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected error occurred.",
            },
        )

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Health endpoint."""

        return {
            "message": "AI Assignment Reviewer API is running.",
            "docs": "/docs",
        }

    return app


app = create_app()
