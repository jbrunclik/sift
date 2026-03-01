import asyncio
import logging
import typing
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database import get_db
from backend.models import HealthResponse, StatsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])

# Track running jobs to prevent concurrent triggers
_running_jobs: set[str] = set()
_background_tasks: set[asyncio.Task[None]] = set()


class IssuesResponse(BaseModel):
    fetch_errors: int = 0
    scoring_errors: int = 0
    unscored: int = 0


class CostEntry(BaseModel):
    month: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    batches: int


class SchedulerJobStatus(BaseModel):
    job_name: str
    last_run_at: str | None = None
    last_status: str | None = None
    last_details: str | None = None
    last_error: str | None = None
    interval_minutes: int | None = None
    next_run_at: str | None = None


class StatsExtended(StatsResponse):
    scheduler_jobs: list[SchedulerJobStatus] = Field(default_factory=list)


class JobTriggerResponse(BaseModel):
    status: str
    message: str


@router.get("/health")
async def health() -> HealthResponse:
    db = await get_db()
    try:
        sources = list(await db.execute_fetchall("SELECT COUNT(*) as cnt FROM sources"))
        articles = list(await db.execute_fetchall("SELECT COUNT(*) as cnt FROM articles"))
        unscored = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) as cnt FROM articles WHERE relevance_score IS NULL"
            )
        )
        return HealthResponse(
            status="ok",
            database="ok",
            sources_count=int(sources[0][0]),
            articles_count=int(articles[0][0]),
            unscored_count=int(unscored[0][0]),
        )
    except Exception as e:
        logger.exception("Health check failed")
        return HealthResponse(status="error", database=str(e))
    finally:
        await db.close()


@router.get("/stats")
async def stats() -> StatsExtended:
    db = await get_db()
    try:
        total = list(await db.execute_fetchall("SELECT COUNT(*) FROM articles"))
        scored = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) FROM articles WHERE relevance_score IS NOT NULL"
            )
        )
        avg_score = list(
            await db.execute_fetchall(
                "SELECT AVG(relevance_score) FROM articles "
                "WHERE relevance_score IS NOT NULL AND relevance_score >= 0"
            )
        )
        feedback_stats = list(
            await db.execute_fetchall(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) as negative
                FROM feedback
                """
            )
        )
        source_stats = await db.execute_fetchall(
            """
            SELECT s.id, s.name, s.slug, s.source_type, s.enabled,
                   s.last_fetched_at, s.category, s.fetch_interval_minutes,
                   COUNT(a.id) as article_count,
                   MAX(a.fetched_at) as last_article_at
            FROM sources s
            LEFT JOIN articles a ON s.id = a.source_id
            GROUP BY s.id
            ORDER BY s.name
            """
        )

        # Score distribution (histogram 0-10)
        distribution = [0] * 11
        dist_rows = await db.execute_fetchall(
            """
            SELECT CAST(relevance_score AS INTEGER) as bucket, COUNT(*) as cnt
            FROM articles
            WHERE relevance_score IS NOT NULL AND relevance_score >= 0
            GROUP BY bucket
            """
        )
        for row in dist_rows:
            bucket = int(row[0])
            if 0 <= bucket <= 10:
                distribution[bucket] = int(row[1])

        # Inbox count (unread, score >= 7 OR starred source)
        inbox = list(
            await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM articles a
                JOIN sources s ON a.source_id = s.id
                WHERE a.is_read = 0 AND a.is_hidden = 0
                  AND a.relevance_score IS NOT NULL
                  AND (a.relevance_score >= 7.0 OR s.starred = 1)
                """
            )
        )

        # Scheduler job statuses
        job_rows = await db.execute_fetchall(
            """
            SELECT job_name, started_at, status, details, error_message
            FROM scheduler_runs
            WHERE id IN (
                SELECT MAX(id) FROM scheduler_runs GROUP BY job_name
            )
            ORDER BY job_name
            """
        )
        # Known job intervals (must match main.py scheduler config)
        job_intervals: dict[str, int] = {
            "fetch_all": 30,
            "score": settings.scoring_interval_minutes,
            "extract": settings.extraction_interval_minutes,
            "cleanup": 24 * 60,
        }

        scheduler_jobs: list[SchedulerJobStatus] = []
        for r in job_rows:
            job_name = str(r[0])
            last_run_at = str(r[1]) if r[1] else None
            interval = job_intervals.get(job_name)

            next_run_at: str | None = None
            if last_run_at and interval:
                try:
                    last_dt = datetime.fromisoformat(last_run_at).replace(tzinfo=UTC)
                    next_dt = last_dt + timedelta(minutes=interval)
                    next_run_at = next_dt.isoformat()
                except ValueError, TypeError:
                    pass

            scheduler_jobs.append(
                SchedulerJobStatus(
                    job_name=job_name,
                    last_run_at=last_run_at,
                    last_status=str(r[2]) if r[2] else None,
                    last_details=str(r[3]) if r[3] else None,
                    last_error=str(r[4]) if r[4] else None,
                    interval_minutes=interval,
                    next_run_at=next_run_at,
                )
            )

        fb = feedback_stats[0]
        return StatsExtended(
            total_articles=int(total[0][0]),
            scored_articles=int(scored[0][0]),
            average_score=float(avg_score[0][0]) if avg_score[0][0] is not None else None,
            total_feedback=int(fb[0]),
            positive_feedback=int(fb[1] or 0),
            negative_feedback=int(fb[2] or 0),
            sources=[dict(row) for row in source_stats],
            score_distribution=distribution,
            inbox_count=int(inbox[0][0]),
            scheduler_jobs=scheduler_jobs,
        )
    finally:
        await db.close()


class IssueDetails(BaseModel):
    fetch_errors: int = 0
    scoring_failures: int = 0
    scoring_retryable: int = 0
    unscored: int = 0


@router.get("/stats/issue-details")
async def get_issue_details() -> IssueDetails:
    db = await get_db()
    try:
        fetch_errors = list(
            await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM fetch_logs
                WHERE status = 'error'
                  AND started_at > datetime('now', '-24 hours')
                """
            )
        )
        scoring_failures = list(
            await db.execute_fetchall("SELECT COUNT(*) FROM articles WHERE relevance_score = -1.0")
        )
        scoring_retryable = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) FROM articles WHERE relevance_score = -1.0 AND score_attempts < 3"
            )
        )
        unscored = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) FROM articles WHERE relevance_score IS NULL AND scored_at IS NULL"
            )
        )
        return IssueDetails(
            fetch_errors=int(fetch_errors[0][0]),
            scoring_failures=int(scoring_failures[0][0]),
            scoring_retryable=int(scoring_retryable[0][0]),
            unscored=int(unscored[0][0]),
        )
    finally:
        await db.close()


class ScoringFailure(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    score_attempts: int
    scored_at: str | None
    error: str | None = None


@router.get("/stats/scoring-failures")
async def get_scoring_failures() -> list[ScoringFailure]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT a.id, a.title, a.url, s.name, a.score_attempts, a.scored_at,
                   a.score_explanation
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.relevance_score = -1.0
            ORDER BY a.scored_at DESC
            """
        )
        return [
            ScoringFailure(
                id=int(r[0]),
                title=str(r[1]),
                url=str(r[2]),
                source_name=str(r[3]),
                score_attempts=int(r[4]),
                scored_at=str(r[5]) if r[5] else None,
                error=str(r[6]) if r[6] else None,
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/jobs/retry-scoring")
async def trigger_retry_scoring() -> JobTriggerResponse:
    """Reset failed scoring articles so they'll be retried on next scoring run."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            UPDATE articles
            SET relevance_score = NULL, scored_at = NULL,
                score_explanation = NULL, summary = NULL
            WHERE relevance_score = -1.0 AND score_attempts < 3
            """
        )
        await db.commit()
        count = cursor.rowcount
    finally:
        await db.close()

    if count == 0:
        return JobTriggerResponse(status="no_action", message="No retryable scoring failures found")
    return JobTriggerResponse(status="started", message=f"Reset {count} articles for re-scoring")


@router.post("/jobs/force-retry-scoring")
async def force_retry_scoring() -> JobTriggerResponse:
    """Reset ALL failed scoring articles, ignoring max attempts."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            UPDATE articles
            SET relevance_score = NULL, scored_at = NULL,
                score_explanation = NULL, summary = NULL, score_attempts = 0
            WHERE relevance_score = -1.0
            """
        )
        await db.commit()
        count = cursor.rowcount
    finally:
        await db.close()

    if count == 0:
        return JobTriggerResponse(status="no_action", message="No scoring failures found")
    return JobTriggerResponse(status="started", message=f"Reset {count} articles for re-scoring")


@router.get("/stats/issues")
async def get_issues() -> IssuesResponse:
    db = await get_db()
    try:
        fetch_errors = list(
            await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM fetch_logs
                WHERE status = 'error'
                  AND started_at > datetime('now', '-24 hours')
                """
            )
        )
        scoring_errors = list(
            await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM articles
                WHERE relevance_score = -1.0
                  AND scored_at > datetime('now', '-24 hours')
                """
            )
        )
        unscored = list(
            await db.execute_fetchall(
                "SELECT COUNT(*) FROM articles WHERE relevance_score IS NULL AND scored_at IS NULL"
            )
        )
        return IssuesResponse(
            fetch_errors=int(fetch_errors[0][0]),
            scoring_errors=int(scoring_errors[0][0]),
            unscored=int(unscored[0][0]),
        )
    finally:
        await db.close()


@router.get("/stats/costs")
async def get_costs() -> list[CostEntry]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT
                strftime('%Y-%m', scored_at) as month,
                model,
                SUM(tokens_in) as total_in,
                SUM(tokens_out) as total_out,
                SUM(cost_usd) as total_cost,
                COUNT(*) as batches
            FROM scoring_logs
            GROUP BY month, model
            ORDER BY month DESC, model
            """
        )
        return [
            CostEntry(
                month=str(row[0]),
                model=str(row[1]),
                tokens_in=int(row[2]),
                tokens_out=int(row[3]),
                cost_usd=float(row[4]),
                batches=int(row[5]),
            )
            for row in rows
        ]
    finally:
        await db.close()


def _launch_job(coro: typing.Coroutine[typing.Any, typing.Any, None]) -> None:
    """Launch a background job, storing the task reference to prevent GC."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.post("/jobs/fetch")
async def trigger_fetch() -> JobTriggerResponse:
    if "fetch" in _running_jobs:
        return JobTriggerResponse(status="already_running", message="Fetch is already running")
    _running_jobs.add("fetch")

    async def run() -> None:
        try:
            from backend.scheduler.worker import fetch_all_sources

            await fetch_all_sources()
        finally:
            _running_jobs.discard("fetch")

    _launch_job(run())
    return JobTriggerResponse(status="started", message="Fetch started")


@router.post("/jobs/score")
async def trigger_score() -> JobTriggerResponse:
    if "score" in _running_jobs:
        return JobTriggerResponse(status="already_running", message="Scoring is already running")
    _running_jobs.add("score")

    async def run() -> None:
        try:
            from backend.scheduler.worker import score_unscored_articles

            await score_unscored_articles()
        finally:
            _running_jobs.discard("score")

    _launch_job(run())
    return JobTriggerResponse(status="started", message="Scoring started")


@router.post("/jobs/extract")
async def trigger_extract() -> JobTriggerResponse:
    if "extract" in _running_jobs:
        return JobTriggerResponse(status="already_running", message="Extraction is already running")
    _running_jobs.add("extract")

    async def run() -> None:
        try:
            from backend.scheduler.worker import extract_unextracted_articles

            await extract_unextracted_articles()
        finally:
            _running_jobs.discard("extract")

    _launch_job(run())
    return JobTriggerResponse(status="started", message="Extraction started")


@router.post("/jobs/cleanup")
async def trigger_cleanup() -> JobTriggerResponse:
    if "cleanup" in _running_jobs:
        return JobTriggerResponse(status="already_running", message="Cleanup is already running")
    _running_jobs.add("cleanup")

    async def run() -> None:
        try:
            from backend.scheduler.cleanup import run_cleanup

            await run_cleanup()
        finally:
            _running_jobs.discard("cleanup")

    _launch_job(run())
    return JobTriggerResponse(status="started", message="Cleanup started")
