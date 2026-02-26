import logging

from fastapi import APIRouter

from backend.database import get_db
from backend.models import HealthResponse, StatsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["health"])


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
async def stats() -> StatsResponse:
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
                "SELECT AVG(relevance_score) FROM articles WHERE relevance_score IS NOT NULL"
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
                   s.last_fetched_at,
                   COUNT(a.id) as article_count,
                   MAX(a.fetched_at) as last_article_at
            FROM sources s
            LEFT JOIN articles a ON s.id = a.source_id
            GROUP BY s.id
            ORDER BY s.name
            """
        )

        fb = feedback_stats[0]
        return StatsResponse(
            total_articles=int(total[0][0]),
            scored_articles=int(scored[0][0]),
            average_score=float(avg_score[0][0]) if avg_score[0][0] is not None else None,
            total_feedback=int(fb[0]),
            positive_feedback=int(fb[1] or 0),
            negative_feedback=int(fb[2] or 0),
            sources=[dict(row) for row in source_stats],
        )
    finally:
        await db.close()
