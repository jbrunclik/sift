import asyncio
import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import trafilatura

from backend.config import settings
from backend.database import get_db
from backend.sources.base import SourceConfig

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
USER_AGENT = "Sift/0.1 (personal news aggregator)"
FETCH_TIMEOUT = 15.0
DOMAIN_COOLDOWN_SECONDS = 2.0
EMA_ALPHA = 0.2


async def extract_single_article(url: str, http_client: httpx.AsyncClient) -> str | None:
    """Fetch and extract article text from a URL.

    Returns:
        Extracted text on success, empty string if no content found, None on fetch/error.
    """
    try:
        response = await http_client.get(url, follow_redirects=True, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None

    # Skip oversized responses
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_RESPONSE_BYTES:
        logger.info("Skipping oversized response (%s bytes): %s", content_length, url)
        return None
    if len(response.content) > MAX_RESPONSE_BYTES:
        logger.info("Skipping oversized response (%d bytes): %s", len(response.content), url)
        return None

    html = response.text
    try:
        text = await asyncio.to_thread(trafilatura.extract, html)
    except Exception:
        logger.exception("Extraction error for %s", url)
        return None

    if text is None:
        return ""
    return text


def _detect_truncation(
    content: str,
    snippet: str | None,
    avg_length: float | None,
) -> bool:
    """Heuristic truncation detection for auth-configured sources."""
    content_len = len(content)

    # Signal 1: extracted content shorter than RSS snippet
    if snippet and content_len < len(snippet) * 0.8:
        return True

    # Signal 2: suspiciously short content
    if content_len < 300:
        return True

    # Signal 3: way below historical average
    return bool(avg_length and content_len < avg_length * 0.3)


async def _update_avg_content_length(
    source_id: int, content_length: int, current_avg: float | None
) -> None:
    """Update EMA of content length for a source."""
    if current_avg is None:
        new_avg = float(content_length)
    else:
        new_avg = EMA_ALPHA * content_length + (1 - EMA_ALPHA) * current_avg

    db = await get_db()
    try:
        await db.execute(
            "UPDATE sources SET avg_content_length = ? WHERE id = ?",
            (new_avg, source_id),
        )
        await db.commit()
    finally:
        await db.close()


async def extract_articles() -> dict[str, int]:
    """Extract content for articles missing content_full. Returns stats dict."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT a.id, a.url, a.source_id, a.content_snippet,
                   s.config_json, s.avg_content_length
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE (a.content_full IS NULL
                   AND (a.extraction_status IS NULL OR a.extraction_status = 'failed'))
               OR a.extraction_status = 'truncated'
            ORDER BY a.published_at DESC
            LIMIT ?
            """,
            (settings.extraction_batch_size,),
        )
        articles: list[dict[str, object]] = [
            {
                "id": int(row[0]),
                "url": str(row[1]),
                "source_id": int(row[2]),
                "snippet": str(row[3]) if row[3] else None,
                "config_json": str(row[4]),
                "avg_content_length": float(row[5]) if row[5] is not None else None,
            }
            for row in rows
        ]
    finally:
        await db.close()

    if not articles:
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "truncated": 0}

    # Build per-source configs
    source_configs: dict[int, SourceConfig] = {}
    for art in articles:
        sid = int(str(art["source_id"]))
        if sid not in source_configs:
            source_configs[sid] = SourceConfig(str(art["config_json"]))

    semaphore = asyncio.Semaphore(settings.extraction_max_concurrent)
    domain_last_request: dict[str, float] = {}
    domain_locks: dict[str, asyncio.Lock] = {}
    stats = {
        "total": len(articles),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "truncated": 0,
    }

    async def process(
        article: dict[str, object],
        client: httpx.AsyncClient,
    ) -> None:
        article_id = int(str(article["id"]))
        url = str(article["url"])
        source_id = int(str(article["source_id"]))
        snippet = article["snippet"]
        avg_length = article["avg_content_length"]
        config = source_configs[source_id]

        domain = urlparse(url).netloc

        # Per-domain rate limiting
        if domain not in domain_locks:
            domain_locks[domain] = asyncio.Lock()

        async with domain_locks[domain]:
            last = domain_last_request.get(domain, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < DOMAIN_COOLDOWN_SECONDS:
                await asyncio.sleep(DOMAIN_COOLDOWN_SECONDS - elapsed)
            domain_last_request[domain] = time.monotonic()

        async with semaphore:
            result = await extract_single_article(url, client)

        now = datetime.now(UTC).isoformat()
        db_conn = await get_db()
        try:
            if result is None:
                stats["failed"] += 1
                await db_conn.execute(
                    """
                    UPDATE articles
                    SET extraction_status = 'failed', extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (now, article_id),
                )
            elif result == "":
                stats["skipped"] += 1
                await db_conn.execute(
                    """
                    UPDATE articles
                    SET extraction_status = 'skipped', extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (now, article_id),
                )
            else:
                # Check truncation for auth sources
                is_truncated = False
                if config.has_auth():
                    is_truncated = _detect_truncation(
                        result,
                        str(snippet) if snippet else None,
                        float(str(avg_length)) if avg_length is not None else None,
                    )

                if is_truncated:
                    stats["truncated"] += 1
                    await db_conn.execute(
                        """
                        UPDATE articles
                        SET content_full = ?, extraction_status = 'truncated',
                            extraction_attempted_at = ?
                        WHERE id = ?
                        """,
                        (result, now, article_id),
                    )
                    logger.warning(
                        "Truncation detected for article %d (%s) — %d chars",
                        article_id, url, len(result),
                    )
                else:
                    stats["success"] += 1
                    await db_conn.execute(
                        """
                        UPDATE articles
                        SET content_full = ?, extraction_status = 'success',
                            extraction_attempted_at = ?
                        WHERE id = ?
                        """,
                        (result, now, article_id),
                    )
                    # Update EMA for non-truncated successful extractions
                    await _update_avg_content_length(
                        source_id,
                        len(result),
                        float(str(avg_length)) if avg_length is not None else None,
                    )
            await db_conn.commit()
        finally:
            await db_conn.close()

    # Create per-source clients for auth sources, share default for the rest
    default_headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(
        headers=default_headers,
        follow_redirects=True,
    ) as default_client:
        # Build auth clients for sources that need them
        auth_clients: dict[int, httpx.AsyncClient] = {}
        for sid, config in source_configs.items():
            if config.has_auth():
                auth_headers = {**default_headers, **config.get_auth_headers()}
                auth_clients[sid] = httpx.AsyncClient(
                    headers=auth_headers,
                    follow_redirects=True,
                )

        try:
            tasks = []
            for art in articles:
                sid = int(str(art["source_id"]))
                client = auth_clients.get(sid, default_client)
                tasks.append(process(art, client))
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for c in auth_clients.values():
                await c.aclose()

    logger.info(
        "Extraction complete: %d total, %d success, %d failed, %d skipped, %d truncated",
        stats["total"],
        stats["success"],
        stats["failed"],
        stats["skipped"],
        stats["truncated"],
    )
    return stats
