"""
One-off migration: moves existing resume/submission files from the old
campaigns/{campaign_id}/candidates/{candidate_id}/... layout to the new
campaigns/{campaign_id}/{candidate_id}/... layout (see
infrastructure/storage/keys.py), and backfills report.pdf for every
already-evaluated submission that doesn't have one yet.

Safe to re-run: candidates already on the new layout (no "candidates/<id>/"
segment in their stored key) are skipped, and report backfill only touches
rows where report_storage_key is still null.

Usage (from the backend/ directory):
    python scripts/migrate_storage_layout.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, select, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.domain.models import FinalReport  # noqa: E402
from app.infrastructure.db.database import create_all_tables, get_session_factory, init_db  # noqa: E402
from app.infrastructure.db.models import CampaignORM, CandidateORM, SubmissionORM  # noqa: E402
from app.infrastructure.storage.factory import get_file_storage  # noqa: E402
from app.infrastructure.storage.keys import report_key  # noqa: E402
from app.services.review.report_pdf import render_report_pdf  # noqa: E402

logger = get_logger(__name__)


def _old_to_new(value: str, candidate_id: str) -> str | None:
    """The old key/path always contains 'candidates/<id>/' (or a
    backslash variant, for local Windows paths) right before the
    candidate id segment. Returns None if that marker isn't present -
    either already migrated, or not this candidate's file."""

    for sep in ("/", "\\"):
        marker = f"candidates{sep}{candidate_id}{sep}"
        if marker in value:
            return value.replace(marker, f"{candidate_id}{sep}", 1)
    return None


async def _ensure_columns(engine) -> None:
    def _get_columns(sync_conn, table: str) -> set[str]:
        return {c["name"] for c in inspect(sync_conn).get_columns(table)}

    async with engine.begin() as conn:
        submission_cols = await conn.run_sync(_get_columns, "submissions")
        candidate_cols = await conn.run_sync(_get_columns, "candidates")

        if "report_storage_key" not in submission_cols:
            logger.info("Adding submissions.report_storage_key")
            await conn.execute(text("ALTER TABLE submissions ADD COLUMN report_storage_key VARCHAR(500)"))
        if "pending_decision" not in candidate_cols:
            logger.info("Adding candidates.pending_decision")
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN pending_decision VARCHAR(16)"))


async def _move_local(old_value: str, new_value: str, dry_run: bool) -> None:
    old_path, new_path = Path(old_value), Path(new_value)
    if not old_path.exists():
        logger.warning("Old file missing on disk, skipping move: %s", old_path)
        return
    logger.info("MOVE %s -> %s", old_path, new_path)
    if dry_run:
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.move, str(old_path), str(new_path))


async def _move_s3(old_value: str, new_value: str, settings, dry_run: bool) -> None:
    import boto3

    bucket = settings.aws_s3_bucket
    old_key = old_value.removeprefix(f"s3://{bucket}/")
    new_key = new_value.removeprefix(f"s3://{bucket}/")
    logger.info("S3 COPY+DELETE %s -> %s", old_key, new_key)
    if dry_run:
        return
    client = boto3.client(
        "s3", region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id, aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.aws_s3_endpoint_url or None,
    )

    def _do() -> None:
        client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": old_key}, Key=new_key)
        client.delete_object(Bucket=bucket, Key=old_key)

    await asyncio.to_thread(_do)


async def main(dry_run: bool) -> None:
    settings = get_settings()
    engine = init_db(settings)
    await create_all_tables()
    await _ensure_columns(engine)

    session_factory = get_session_factory()
    storage = get_file_storage()

    moved = 0
    backfilled = 0
    skipped = 0

    async with session_factory() as session:
        candidates = (await session.execute(select(CandidateORM))).scalars().all()
        for candidate in candidates:
            if candidate.resume_storage_key:
                new_value = _old_to_new(candidate.resume_storage_key, candidate.id)
                if new_value:
                    if settings.storage_backend == "s3":
                        await _move_s3(candidate.resume_storage_key, new_value, settings, dry_run)
                    else:
                        await _move_local(candidate.resume_storage_key, new_value, dry_run)
                    if not dry_run:
                        candidate.resume_storage_key = new_value
                    moved += 1
                else:
                    skipped += 1

        submissions = (await session.execute(select(SubmissionORM))).scalars().all()
        for submission in submissions:
            if submission.submission_storage_key:
                new_value = _old_to_new(submission.submission_storage_key, submission.candidate_id)
                if new_value:
                    if settings.storage_backend == "s3":
                        await _move_s3(submission.submission_storage_key, new_value, settings, dry_run)
                    else:
                        await _move_local(submission.submission_storage_key, new_value, dry_run)
                    if not dry_run:
                        submission.submission_storage_key = new_value
                    moved += 1
                else:
                    skipped += 1

            # Backfill report.pdf for already-evaluated submissions that
            # predate report_storage_key existing at all.
            if submission.report and not submission.report_storage_key:
                candidate = await session.get(CandidateORM, submission.candidate_id)
                campaign = await session.get(CampaignORM, candidate.campaign_id) if candidate else None
                if candidate is None or campaign is None:
                    logger.warning("Submission %s has an orphaned candidate/campaign - skipping report backfill", submission.id)
                    continue
                report = FinalReport.model_validate(submission.report)
                logger.info("BACKFILL report.pdf for candidate %s", candidate.id)
                if not dry_run:
                    pdf_buffer = render_report_pdf(candidate.name or "Candidate", campaign.job_title, report)
                    key = report_key(campaign.id, candidate.id)
                    submission.report_storage_key = await storage.save(key, pdf_buffer.getvalue())
                backfilled += 1

        if not dry_run:
            await session.commit()

    logger.info(
        "%sDone: %d file(s) moved, %d report(s) backfilled, %d already-migrated/skipped.",
        "[DRY RUN] " if dry_run else "", moved, backfilled, skipped,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Log planned changes without touching disk/DB.")
    args = parser.parse_args()

    configure_logging("INFO")
    asyncio.run(main(args.dry_run))
