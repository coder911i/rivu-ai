"""Database-backed worker for durable dataset-processing jobs.

Run as a separate Render background worker:
    python -m app.workers.runner
PostgreSQL row locks ensure only one worker claims a queued job at a time.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import close_db, get_session, init_db
from app.models.dataset import DataSource
from app.models.quality import Job
from app.workers.processor import process_dataset_async

logger = structlog.get_logger(__name__)
POLL_SECONDS = 2
STALE_JOB_MINUTES = 120


async def _recover_stale_jobs(db) -> None:
    """Requeue crashed jobs after a generous lease window; cap retries."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_JOB_MINUTES)
    stale = await db.execute(
        select(Job).where(
            Job.status == "processing",
            Job.started_at.is_not(None),
            Job.started_at < cutoff,
        )
    )
    now = datetime.now(timezone.utc)
    for job in stale.scalars().all():
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.started_at = None
            job.progress_message = "Recovered after worker interruption; retry queued"
            logger.warning("job_requeued_after_worker_interruption", job_id=str(job.id), attempts=job.attempts)
        else:
            job.status = "failed"
            job.error_message = "Worker interrupted repeatedly; maximum attempts exceeded"
            job.completed_at = now
            logger.error("job_failed_after_repeated_worker_interruptions", job_id=str(job.id))
    await db.commit()


async def _claim_one_job():
    """Atomically claim the highest-priority queued profiling job."""
    async with get_session() as db:
        result = await db.execute(
            select(Job)
            .where(Job.status == "queued", Job.job_type == "profile")
            .order_by(Job.priority.asc(), Job.queued_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        job.progress_pct = max(job.progress_pct or 0, 1)
        job.progress_message = "Worker claimed job"
        await db.commit()
        return {
            "job_id": str(job.id),
            "version_id": str(job.dataset_version_id),
            "data_source_id": str(job.data_source_id),
            "org_id": str(job.organization_id),
        }


async def _process_claim(claim: dict) -> None:
    from app.models.dataset import DatasetVersion

    async with get_session() as db:
        source_result = await db.execute(
            select(DataSource).where(DataSource.id == claim["data_source_id"])
        )
        source = source_result.scalar_one_or_none()
        version_result = await db.execute(
            select(DatasetVersion).where(DatasetVersion.id == claim["version_id"])
        )
        version = version_result.scalar_one_or_none()
        if source is None or version is None:
            job_result = await db.execute(select(Job).where(Job.id == claim["job_id"]))
            job = job_result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = "Job references a missing dataset or dataset version"
                job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return
        file_format = source.file_format

    await process_dataset_async(
        job_id=claim["job_id"],
        version_id=claim["version_id"],
        data_source_id=claim["data_source_id"],
        org_id=claim["org_id"],
        raw_bytes=None,
        file_format=file_format,
    )


async def run_worker() -> None:
    await init_db()
    logger.info("rivu_worker_started", poll_seconds=POLL_SECONDS)
    try:
        while True:
            async with get_session() as db:
                await _recover_stale_jobs(db)
            claim = await _claim_one_job()
            if claim is None:
                await asyncio.sleep(POLL_SECONDS)
                continue
            try:
                await _process_claim(claim)
            except Exception as exc:
                logger.exception("worker_job_unhandled_error", job_id=claim["job_id"], error=str(exc))
                async with get_session() as db:
                    result = await db.execute(select(Job).where(Job.id == claim["job_id"]))
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = "failed" if job.attempts >= job.max_attempts else "queued"
                        job.error_message = str(exc)[:2000]
                        job.completed_at = datetime.now(timezone.utc) if job.status == "failed" else None
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(run_worker())
