import asyncio
import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import trafilatura

from backend.config import settings
from backend.database import get_db

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
USER_AGENT = "Sift/0.1 (personal news aggregator)"
FETCH_TIMEOUT = 15.0
DOMAIN_COOLDOWN_SECONDS = 2.0


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


async def extract_articles() -> dict[str, int]:
    """Extract content for articles missing content_full. Returns stats dict."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """
            SELECT id, url FROM articles
            WHERE content_full IS NULL
              AND (extraction_status IS NULL OR extraction_status = 'failed')
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (settings.extraction_batch_size,),
        )
        articles = [(int(row[0]), str(row[1])) for row in rows]
    finally:
        await db.close()

    if not articles:
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    semaphore = asyncio.Semaphore(settings.extraction_max_concurrent)
    domain_last_request: dict[str, float] = {}
    domain_locks: dict[str, asyncio.Lock] = {}
    stats = {"total": len(articles), "success": 0, "failed": 0, "skipped": 0}

    async def process(article_id: int, url: str, client: httpx.AsyncClient) -> None:
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
            await db_conn.commit()
        finally:
            await db_conn.close()

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        tasks = [process(aid, url, client) for aid, url in articles]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(
        "Extraction complete: %d total, %d success, %d failed, %d skipped",
        stats["total"],
        stats["success"],
        stats["failed"],
        stats["skipped"],
    )
    return stats
