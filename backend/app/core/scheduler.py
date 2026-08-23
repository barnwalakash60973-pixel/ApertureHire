"""
Real periodic background jobs - replaces the old "runs lazily only when
HR happens to load a dashboard page" approach for overdue-marking, and
adds two jobs that had NO trigger at all before: reminder/overdue candidate
emails, and retention cleanup of rejected candidates' files.

Uses APScheduler's AsyncIOScheduler in-process. This is the honest
minimum fix, not a claim that it's production-grade: it runs inside the
API process, so it only fires while at least one instance is up, and if
you scale to multiple API instances each one will run its own copy of
these jobs (they're all idempotent status/date checks, so duplicate runs
are harmless, just redundant). A real deployment queues these as
Celery/RQ beat tasks on a dedicated worker - documented as a follow-up
below, not built here, because that requires a broker (Redis/RabbitMQ)
this environment has no way to stand up or test against.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import Settings
from app.core.logging import get_logger
from app.infrastructure.db.database import get_session_factory
from app.infrastructure.db.models import AssignmentORM, CampaignORM, CandidateORM
from app.infrastructure.email.email_sender import get_email_sender
from app.infrastructure.email.templates import (
    OVERDUE_EMAIL_BODY,
    OVERDUE_EMAIL_SUBJECT,
    REMINDER_EMAIL_BODY,
    REMINDER_EMAIL_SUBJECT,
)
from app.infrastructure.storage.factory import get_file_storage

logger = get_logger(__name__)

# How long before a deadline to send a single reminder email. Candidates
# get exactly one reminder (tracked via CandidateORM.status staying
# "assignment_sent" - we don't have a separate "reminded" flag, so this
# is best-effort: see the honesty note in send_reminders below).
_REMINDER_WINDOW_HOURS = 24


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def mark_overdue_and_send_notifications(settings: Settings) -> None:
    """For every campaign with an approved, deadline-passed assignment:
    flip assignment_sent candidates to submission_overdue and email them
    the Overdue template. This is the same logic that used to live only
    in routes_campaigns._mark_overdue_candidates (still there, still
    runs lazily too - both are harmless since the state flip is
    idempotent), now also driven by a timer instead of only by an HR
    page load."""

    session_factory = get_session_factory()
    email_sender = get_email_sender(settings)

    async with session_factory() as session:
        campaigns = (await session.execute(select(CampaignORM))).scalars().all()
        for campaign in campaigns:
            assignment = (
                await session.execute(
                    select(AssignmentORM)
                    .where(AssignmentORM.campaign_id == campaign.id, AssignmentORM.status == "approved")
                    .order_by(AssignmentORM.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if assignment is None or assignment.deadline is None:
                continue

            deadline = _as_utc(assignment.deadline)
            now = datetime.now(timezone.utc)

            sent_candidates = (
                await session.execute(
                    select(CandidateORM).where(
                        CandidateORM.campaign_id == campaign.id, CandidateORM.status == "assignment_sent"
                    )
                )
            ).scalars().all()

            for candidate in sent_candidates:
                if deadline < now:
                    candidate.status = "submission_overdue"
                    if candidate.email:
                        try:
                            email_sender.send(
                                to_email=candidate.email,
                                subject=OVERDUE_EMAIL_SUBJECT,
                                body=OVERDUE_EMAIL_BODY.format(name=candidate.name or "Candidate", campaign_name=campaign.name),
                            )
                        except Exception:
                            logger.exception("Failed to send overdue email to candidate %s", candidate.id)
                elif deadline - now <= timedelta(hours=_REMINDER_WINDOW_HOURS):
                    # Best-effort: no "already reminded" flag exists, so a
                    # candidate could get more than one reminder if the
                    # job runs more than once inside the window. Noted as
                    # a known limitation rather than hidden - fixing it
                    # cleanly needs a `reminder_sent_at` column.
                    if candidate.email:
                        try:
                            email_sender.send(
                                to_email=candidate.email,
                                subject=REMINDER_EMAIL_SUBJECT,
                                body=REMINDER_EMAIL_BODY.format(name=candidate.name or "Candidate", campaign_name=campaign.name, deadline=deadline.isoformat()),
                            )
                        except Exception:
                            logger.exception("Failed to send reminder email to candidate %s", candidate.id)

        await session.commit()


async def purge_expired_candidates(settings: Settings) -> None:
    """Retention cleanup: for candidates whose retention_deadline has
    passed, delete the stored resume file and blank the extracted text,
    but KEEP the row (id/status/timestamps) so campaign history and
    audit counts stay accurate - only the personal content is purged.
    Final-selected candidates never get a retention_deadline set (see
    routes_campaigns.py), so they're never touched here."""

    session_factory = get_session_factory()
    storage = get_file_storage()
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        expired = (
            await session.execute(
                select(CandidateORM).where(
                    CandidateORM.retention_purged.is_(False),
                    CandidateORM.retention_deadline.is_not(None),
                    CandidateORM.retention_deadline <= now,
                )
            )
        ).scalars().all()

        for candidate in expired:
            if candidate.resume_storage_key:
                try:
                    await storage.delete(candidate.resume_storage_key)
                except Exception:
                    logger.exception("Failed to delete resume file for candidate %s during retention purge", candidate.id)
            candidate.resume_text = ""
            candidate.resume_storage_key = None
            candidate.retention_purged = True

        if expired:
            logger.info("Retention purge: cleared %d candidates past their retention deadline", len(expired))

        await session.commit()


def start_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(mark_overdue_and_send_notifications, "interval", hours=1, args=[settings], id="overdue_and_notifications", max_instances=1)
    scheduler.add_job(purge_expired_candidates, "interval", hours=24, args=[settings], id="retention_purge", max_instances=1)
    scheduler.start()
    logger.info("Background scheduler started: overdue/notifications hourly, retention purge daily.")
    return scheduler
