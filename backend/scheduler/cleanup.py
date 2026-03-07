"""Data cleanup: prune old articles, orphaned tags, old logs."""

import json
import logging

from backend.config import settings
from backend.database import get_db
from backend.extraction.cache import cleanup_stale as cleanup_extraction_cache

logger = logging.getLogger(__name__)


async def run_cleanup() -> None:
    """Run all cleanup tasks."""
    db = await get_db()
    run_id = None
    try:
        cursor = await db.execute(
            "INSERT INTO scheduler_runs (job_name, status) VALUES ('cleanup', 'running')"
        )
        run_id = cursor.lastrowid
        await db.commit()
    except Exception:
        logger.exception("Failed to log cleanup run")
        run_id = None

    details: dict[str, int] = {}
    error_msg = None
    status = "success"
    try:
        # Delete old articles without feedback
        cursor = await db.execute(
            """
            DELETE FROM articles
            WHERE created_at < datetime('now', ? || ' days')
              AND id NOT IN (SELECT article_id FROM feedback)
            """,
            (f"-{settings.article_retention_days}",),
        )
        details["articles_deleted"] = cursor.rowcount

        # Prune stale tag_candidates where tag or article no longer exists
        cursor = await db.execute(
            """
            DELETE FROM tag_candidates
            WHERE tag_id NOT IN (SELECT id FROM tags)
               OR article_id NOT IN (SELECT id FROM articles)
            """
        )
        details["stale_candidates"] = cursor.rowcount

        # Prune orphaned tags (only unapproved with no article_tags)
        cursor = await db.execute(
            """
            DELETE FROM tags
            WHERE id NOT IN (SELECT DISTINCT tag_id FROM article_tags)
              AND is_approved = 0
            """
        )
        details["orphan_tags"] = cursor.rowcount

        # Prune old fetch_logs (> 30 days)
        cursor = await db.execute(
            "DELETE FROM fetch_logs WHERE started_at < datetime('now', '-30 days')"
        )
        details["fetch_logs"] = cursor.rowcount

        # Prune old scoring_logs (> 365 days)
        cursor = await db.execute(
            "DELETE FROM scoring_logs WHERE scored_at < datetime('now', '-365 days')"
        )
        details["scoring_logs"] = cursor.rowcount

        # Prune old scheduler_runs (> 30 days)
        cursor = await db.execute(
            "DELETE FROM scheduler_runs WHERE started_at < datetime('now', '-30 days')"
        )
        details["scheduler_runs"] = cursor.rowcount

        await db.commit()

        # Optimize query planner stats (lightweight, no exclusive lock)
        await db.execute("PRAGMA optimize")

        # Clean up stale extraction cache files (> 7 days)
        details["extraction_cache"] = cleanup_extraction_cache()

        logger.info(
            "Cleanup complete: articles=%d, tags=%d, candidates=%d, "
            "fetch_logs=%d, scoring_logs=%d, scheduler_runs=%d, cache=%d",
            details["articles_deleted"],
            details["orphan_tags"],
            details["stale_candidates"],
            details["fetch_logs"],
            details["scoring_logs"],
            details["scheduler_runs"],
            details["extraction_cache"],
        )
    except Exception:
        logger.exception("Cleanup failed")
        status = "error"
        error_msg = "Cleanup failed"
    finally:
        if run_id:
            try:
                await db.execute(
                    """
                    UPDATE scheduler_runs
                    SET finished_at = datetime('now'), status = ?,
                        details = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (status, json.dumps(details), error_msg, run_id),
                )
                await db.commit()
            except Exception:
                logger.exception("Failed to update cleanup run log")
        await db.close()
