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
            async with httpx.AsyncClient() as http_client:
                config = SourceConfig(str(source_row["config_json"]))
                source = source_cls(config=config, http_client=http_client)
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
            await db.execute(
                "UPDATE sources SET last_fetched_at = datetime('now') WHERE id = ?",
                (source_id,),
            )
            await db.commit()
            logger.info(
                "Source %d: fetched %d, %d new in %dms",
                source_id,
                len(raw_articles),
                items_new,
                duration_ms,
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
    try:
        rows = await db.execute_fetchall("SELECT id FROM sources WHERE enabled = 1")
        source_ids = [int(row[0]) for row in rows]
    finally:
        await db.close()

    for source_id in source_ids:
        try:
            await fetch_source(source_id)
        except Exception:
            logger.exception("Error fetching source %d", source_id)


async def score_unscored_articles() -> None:
    """Score all unscored articles via the Gemini pipeline."""
    try:
        from backend.scoring import run_scoring_pipeline

        await run_scoring_pipeline()
    except Exception:
        logger.exception("Scoring pipeline failed")


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
