import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
import trafilatura

from backend.config import settings
from backend.database import get_db
from backend.extraction.cache import read_cached, remove_cached, write_cached
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


@dataclass
class ExtractionResult:
    """Result of extracting a single article."""

    article_id: int
    source_id: int
    status: str  # 'success', 'failed', 'skipped', 'truncated'
    content: str | None
    avg_length: float | None


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

    async def fetch_one(
        article: dict[str, object],
        client: httpx.AsyncClient,
    ) -> ExtractionResult:
        """Fetch and classify a single article. No DB writes."""
        article_id = int(str(article["id"]))
        url = str(article["url"])
        source_id = int(str(article["source_id"]))
        snippet = article["snippet"]
        raw_avg = article["avg_content_length"]
        avg_length: float | None = float(str(raw_avg)) if raw_avg is not None else None
        config = source_configs[source_id]

        # Check local cache first (survives DB write failures)
        cached = read_cached(article_id)
        if cached is not None:
            logger.debug("Cache hit for article %d", article_id)
            return ExtractionResult(
                article_id, source_id,
                str(cached["status"]),
                str(cached["content"]) if cached["content"] is not None else None,
                avg_length,
            )

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

        if result is None:
            write_cached(article_id, "failed", None)
            return ExtractionResult(article_id, source_id, "failed", None, avg_length)
        if result == "":
            write_cached(article_id, "skipped", None)
            return ExtractionResult(article_id, source_id, "skipped", None, avg_length)

        # Check truncation for auth sources
        if config.has_auth() and _detect_truncation(
            result,
            str(snippet) if snippet else None,
            avg_length,
        ):
            logger.warning(
                "Truncation detected for article %d (%s) — %d chars",
                article_id, url, len(result),
            )
            write_cached(article_id, "truncated", result)
            return ExtractionResult(article_id, source_id, "truncated", result, avg_length)

        write_cached(article_id, "success", result)
        return ExtractionResult(article_id, source_id, "success", result, avg_length)

    # --- Phase 1: Fetch all articles concurrently ---
    default_headers = {"User-Agent": USER_AGENT}

    results: list[ExtractionResult] = []
    async with httpx.AsyncClient(
        headers=default_headers,
        follow_redirects=True,
    ) as default_client:
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
                tasks.append(fetch_one(art, client))
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for c in auth_clients.values():
                await c.aclose()

    # Separate successful results from exceptions
    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, BaseException):
            article_id = int(str(articles[i]["id"]))
            logger.error("Extraction task failed for article %d: %s", article_id, outcome)
            results.append(ExtractionResult(
                article_id,
                int(str(articles[i]["source_id"])),
                "failed",
                None,
                None,
            ))
        else:
            results.append(outcome)

    # --- Phase 2: Write all results to DB in a single transaction ---
    stats = {"total": len(articles), "success": 0, "failed": 0, "skipped": 0, "truncated": 0}
    now = datetime.now(UTC).isoformat()

    # Track EMA updates per source (last one wins)
    ema_updates: dict[int, float] = {}

    db = await get_db()
    try:
        for r in results:
            if r.status == "failed":
                stats["failed"] += 1
                await db.execute(
                    """
                    UPDATE articles
                    SET extraction_status = 'failed', extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (now, r.article_id),
                )
            elif r.status == "skipped":
                stats["skipped"] += 1
                await db.execute(
                    """
                    UPDATE articles
                    SET extraction_status = 'skipped', extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (now, r.article_id),
                )
            elif r.status == "truncated":
                stats["truncated"] += 1
                await db.execute(
                    """
                    UPDATE articles
                    SET content_full = ?, extraction_status = 'truncated',
                        extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (r.content, now, r.article_id),
                )
            else:
                stats["success"] += 1
                await db.execute(
                    """
                    UPDATE articles
                    SET content_full = ?, extraction_status = 'success',
                        extraction_attempted_at = ?
                    WHERE id = ?
                    """,
                    (r.content, now, r.article_id),
                )
                # Compute EMA update
                content_len = len(r.content) if r.content else 0
                current_avg = r.avg_length
                if current_avg is None:
                    ema_updates[r.source_id] = float(content_len)
                else:
                    ema_updates[r.source_id] = (
                        EMA_ALPHA * content_len + (1 - EMA_ALPHA) * current_avg
                    )

        # Apply EMA updates for sources
        for source_id, new_avg in ema_updates.items():
            await db.execute(
                "UPDATE sources SET avg_content_length = ? WHERE id = ?",
                (new_avg, source_id),
            )

        await db.commit()

        # DB commit succeeded — remove cache files for all committed articles
        for r in results:
            remove_cached(r.article_id)
    finally:
        await db.close()

    logger.info(
        "Extraction complete: %d total, %d success, %d failed, %d skipped, %d truncated",
        stats["total"],
        stats["success"],
        stats["failed"],
        stats["skipped"],
        stats["truncated"],
    )
    return stats
