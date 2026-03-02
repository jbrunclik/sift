import json
import logging
import sqlite3
import time

import httpx

from backend.database import get_db
from backend.sources import SourceConfig, get_source_class

logger = logging.getLogger(__name__)


async def fetch_source(source_id: int) -> None:
    """Fetch articles from a single source and store new ones."""
    db = await get_db()
    try:
        rows = list(await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,)))
        if not rows:
            logger.error("Source %d not found", source_id)
            return

        source_row: dict[str, object] = dict(rows[0])
        if not source_row["enabled"]:
            return

        source_cls = get_source_class(str(source_row["source_type"]))
        if not source_cls:
            logger.error("No plugin for source type: %s", source_row["source_type"])
            return

        # Log start
        cursor = await db.execute(
            "INSERT INTO fetch_logs (source_id, status) VALUES (?, 'running')",
            (source_id,),
        )
        await db.commit()
        log_id = cursor.lastrowid
        start_time = time.monotonic()

        try:
            config = SourceConfig(str(source_row["config_json"]))
            client_headers = config.get_auth_headers()
            async with httpx.AsyncClient(headers=client_headers) as http_client:
                source = source_cls(config=config, http_client=http_client, source_id=source_id)
                raw_articles = await source.fetch()

            items_new = 0
            for raw in raw_articles:
                url_norm = _normalize_url(raw.url)
                extra_json = json.dumps(raw.extra) if raw.extra else "{}"
                try:
                    await db.execute(
                        """
                        INSERT INTO articles
                            (source_id, external_id, url, url_normalized, title, author,
                             content_snippet, content_full, published_at, language,
                             image_url, extra_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            source_id,
                            raw.external_id,
                            raw.url,
                            url_norm,
                            raw.title,
                            raw.author,
                            raw.content_snippet,
                            raw.content_full,
                            raw.published_at.isoformat() if raw.published_at else None,
                            raw.language,
                            raw.image_url,
                            extra_json,
                        ),
                    )
                    items_new += 1
                except sqlite3.IntegrityError:
                    pass  # Duplicate URL — skip

            await db.commit()
            duration_ms = int((time.monotonic() - start_time) * 1000)

            await db.execute(
                """
                UPDATE fetch_logs
                SET finished_at = datetime('now'), status = 'success',
                    items_found = ?, items_new = ?, duration_ms = ?
                WHERE id = ?
                """,
                (len(raw_articles), items_new, duration_ms, log_id),
            )

            # Adaptive fetch interval
            avg = float(str(source_row.get("avg_articles_per_fetch", 0) or 0))
            consecutive_empty = int(str(source_row.get("consecutive_empty_fetches", 0) or 0))
            interval = int(str(source_row.get("fetch_interval_minutes", 30) or 30))
            alpha = 0.3
            new_count = float(items_new)
            avg = alpha * new_count + (1 - alpha) * avg
            if items_new == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0
            if consecutive_empty >= 3:
                interval = min(interval * 2, 360)
            elif avg > 5:
                interval = max(interval // 2, 10)
            elif 0 < avg < 2:
                interval = min(int(interval * 1.5), 360)

            await db.execute(
                """
                UPDATE sources
                SET last_fetched_at = datetime('now'),
                    avg_articles_per_fetch = ?,
                    consecutive_empty_fetches = ?,
                    fetch_interval_minutes = ?
                WHERE id = ?
                """,
                (avg, consecutive_empty, interval, source_id),
            )
            await db.commit()
            logger.info(
                "Source %d: fetched %d, %d new in %dms (interval=%dmin)",
                source_id,
                len(raw_articles),
                items_new,
                duration_ms,
                interval,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await db.execute(
                """
                UPDATE fetch_logs
                SET finished_at = datetime('now'), status = 'error',
                    error_message = ?, duration_ms = ?
                WHERE id = ?
                """,
                (str(e), duration_ms, log_id),
            )
            await db.commit()
            logger.exception("Fetch failed for source %d", source_id)

    finally:
        await db.close()


async def fetch_all_sources() -> None:
    """Fetch all enabled sources."""
    db = await get_db()
    run_id = None
    try:
        cursor = await db.execute(
            "INSERT INTO scheduler_runs (job_name, status) VALUES ('fetch_all', 'running')"
        )
        run_id = cursor.lastrowid
        await db.commit()

        rows = await db.execute_fetchall(
            """
            SELECT id FROM sources
            WHERE enabled = 1
              AND (
                last_fetched_at IS NULL
                OR datetime(last_fetched_at, '+' || fetch_interval_minutes || ' minutes')
                   <= datetime('now')
              )
            """
        )
        source_ids = [int(row[0]) for row in rows]
    finally:
        await db.close()

    errors: list[str] = []
    for source_id in source_ids:
        try:
            await fetch_source(source_id)
        except Exception:
            logger.exception("Error fetching source %d", source_id)
            errors.append(f"source {source_id}")

    db = await get_db()
    try:
        status = "error" if errors else "success"
        details = json.dumps(
            {
                "sources": len(source_ids),
                "errors": len(errors),
            }
        )
        error_msg = "; ".join(errors) if errors else None
        await db.execute(
            """
            UPDATE scheduler_runs
            SET finished_at = datetime('now'), status = ?, details = ?, error_message = ?
            WHERE id = ?
            """,
            (status, details, error_msg, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def score_unscored_articles() -> None:
    """Score all unscored articles via the Gemini pipeline."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO scheduler_runs (job_name, status) VALUES ('score', 'running')"
        )
        run_id = cursor.lastrowid
        await db.commit()
    finally:
        await db.close()

    error_msg = None
    status = "success"
    details = "{}"
    try:
        from backend.scoring import run_scoring_pipeline

        stats = await run_scoring_pipeline()
        details = json.dumps(stats)
        if stats.get("failed", 0) > 0:
            status = "error" if stats.get("scored", 0) == 0 else "success"
            error_msg = f"{stats['failed']} groups failed"
    except Exception:
        logger.exception("Scoring pipeline failed")
        status = "error"
        error_msg = "Scoring pipeline failed"

    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE scheduler_runs
            SET finished_at = datetime('now'), status = ?, details = ?, error_message = ?
            WHERE id = ?
            """,
            (status, details, error_msg, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def extract_unextracted_articles() -> None:
    """Extract full content for articles missing content_full."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO scheduler_runs (job_name, status) VALUES ('extract', 'running')"
        )
        run_id = cursor.lastrowid
        await db.commit()
    finally:
        await db.close()

    error_msg = None
    status = "success"
    details = "{}"
    try:
        from backend.extraction import extract_articles

        stats = await extract_articles()
        details = json.dumps(stats)
        if stats.get("failed", 0) > 0:
            status = "error" if stats.get("success", 0) == 0 else "success"
            error_msg = f"{stats['failed']} articles failed extraction"
    except Exception:
        logger.exception("Extraction pipeline failed")
        status = "error"
        error_msg = "Extraction pipeline failed"

    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE scheduler_runs
            SET finished_at = datetime('now'), status = ?, details = ?, error_message = ?
            WHERE id = ?
            """,
            (status, details, error_msg, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def synthesize_profile() -> None:
    """Run profile synthesis (decay weights + generate prose profile)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO scheduler_runs (job_name, status) VALUES ('synthesize', 'running')"
        )
        run_id = cursor.lastrowid
        await db.commit()
    finally:
        await db.close()

    error_msg = None
    status = "success"
    details = "{}"
    try:
        from backend.preferences.profile_synthesizer import synthesize_profile as _synthesize

        db = await get_db()
        try:
            did_run = await _synthesize(db)
            details = json.dumps({"synthesized": did_run})
        finally:
            await db.close()
    except Exception:
        logger.exception("Profile synthesis failed")
        status = "error"
        error_msg = "Profile synthesis failed"

    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE scheduler_runs
            SET finished_at = datetime('now'), status = ?, details = ?, error_message = ?
            WHERE id = ?
            """,
            (status, details, error_msg, run_id),
        )
        await db.commit()
    finally:
        await db.close()


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]

    strip_params = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref"}
    query = parse_qs(parsed.query)
    filtered = {k: v for k, v in query.items() if k not in strip_params}
    new_query = urlencode(filtered, doseq=True) if filtered else ""

    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", new_query, ""))
