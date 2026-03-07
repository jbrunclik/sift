import json
import logging
import sqlite3
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db
from backend.models import FetchLog, Source, SourceCreate
from backend.sources import get_platform_source_types, get_source_class

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
async def list_sources() -> list[Source]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM sources ORDER BY name")
        return [Source(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/platforms")
async def list_platforms() -> list[dict[str, object]]:
    """Return platform metadata merged with DB state."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM sources")
        sources_by_type: dict[str, dict[str, object]] = {}
        for row in rows:
            d = dict(row)
            sources_by_type[str(d["source_type"])] = d

        result: list[dict[str, object]] = []
        for cls in get_platform_source_types():
            source_row = sources_by_type.get(cls.source_type)
            source_obj = Source(**source_row) if source_row else None
            result.append({
                "source_type": cls.source_type,
                "display_name": cls.display_name,
                "description": cls.platform_description,
                "icon": cls.source_type,
                "config_fields": cls.config_fields,
                "auth_type": cls.auth_type,
                "source": source_obj.model_dump(mode="json") if source_obj else None,
            })
        return result
    finally:
        await db.close()


@router.post("")
async def create_source(source: SourceCreate) -> Source:
    db = await get_db()
    try:
        # Validate source_type
        source_cls = get_source_class(source.source_type)
        if not source_cls:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source type: {source.source_type}",
            )

        # Singleton guard for platform sources
        if source_cls.is_platform:
            existing = await db.execute_fetchall(
                "SELECT id FROM sources WHERE source_type = ?", (source.source_type,)
            )
            if list(existing):
                raise HTTPException(
                    409, f"Platform source '{source_cls.display_name}' already exists"
                )

        # Validate config_json is valid JSON
        try:
            json.loads(source.config_json)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid config_json: {e}") from e

        cursor = await db.execute(
            """
            INSERT INTO sources
                (name, slug, source_type, config_json, enabled, fetch_interval_minutes,
                 category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.name,
                source.slug,
                source.source_type,
                source.config_json,
                int(source.enabled),
                source.fetch_interval_minutes,
                source.category,
            ),
        )
        await db.commit()

        rows = list(
            await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (cursor.lastrowid,))
        )
        return Source(**dict(rows[0]))
    finally:
        await db.close()


class SourceUpdate(BaseModel):
    category: str | None = None
    name: str | None = None
    enabled: bool | None = None
    fetch_interval_minutes: int | None = None
    config_json: str | None = None
    starred: bool | None = None


@router.patch("/{source_id}")
async def update_source(source_id: int, data: SourceUpdate) -> Source:
    db = await get_db()
    try:
        rows = list(await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,)))
        if not rows:
            raise HTTPException(status_code=404, detail="Source not found")

        updates: list[str] = []
        params: list[object] = []
        if data.category is not None:
            updates.append("category = ?")
            params.append(data.category)
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.enabled is not None:
            updates.append("enabled = ?")
            params.append(int(data.enabled))
        if data.fetch_interval_minutes is not None:
            updates.append("fetch_interval_minutes = ?")
            params.append(data.fetch_interval_minutes)
        if data.config_json is not None:
            # Validate it's valid JSON
            try:
                json.loads(data.config_json)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid config_json: {e}") from e
            updates.append("config_json = ?")
            params.append(data.config_json)
        if data.starred is not None:
            updates.append("starred = ?")
            params.append(int(data.starred))

        if updates:
            params.append(source_id)
            await db.execute(
                f"UPDATE sources SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            await db.commit()

        rows = list(await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,)))
        return Source(**dict(rows[0]))
    finally:
        await db.close()


@router.delete("/{source_id}")
async def delete_source(source_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"status": "deleted"}
    finally:
        await db.close()


@router.post("/{source_id}/fetch")
async def trigger_fetch(source_id: int) -> FetchLog:
    """Manually trigger a fetch for a specific source."""
    import httpx

    from backend.sources.base import SourceConfig

    db = await get_db()
    try:
        rows = list(await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,)))
        if not rows:
            raise HTTPException(status_code=404, detail="Source not found")

        source_row: dict[str, object] = dict(rows[0])
        source_cls = get_source_class(str(source_row["source_type"]))
        if not source_cls:
            raise HTTPException(
                status_code=400,
                detail=f"No plugin for source type: {source_row['source_type']}",
            )

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

            # Update fetch log
            await db.execute(
                """
                UPDATE fetch_logs
                SET finished_at = datetime('now'), status = 'success',
                    items_found = ?, items_new = ?, duration_ms = ?
                WHERE id = ?
                """,
                (len(raw_articles), items_new, duration_ms, log_id),
            )
            # Update last_fetched_at on source
            await db.execute(
                "UPDATE sources SET last_fetched_at = datetime('now') WHERE id = ?",
                (source_id,),
            )
            await db.commit()

            log_rows = list(
                await db.execute_fetchall("SELECT * FROM fetch_logs WHERE id = ?", (log_id,))
            )
            return FetchLog(**dict(log_rows[0]))

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
            raise HTTPException(status_code=500, detail=f"Fetch failed: {e}") from e

    finally:
        await db.close()


class TestAuthResponse(BaseModel):
    status: str  # "ok" | "truncated" | "error"
    content_length: int = 0
    message: str = ""


@router.post("/{source_id}/test-auth")
async def test_source_auth(source_id: int) -> TestAuthResponse:
    """Test authentication by fetching a recent article with configured cookies."""
    import asyncio

    import httpx
    import trafilatura

    from backend.sources.base import SourceConfig as _SourceConfig

    db = await get_db()
    try:
        rows = list(await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,)))
        if not rows:
            raise HTTPException(status_code=404, detail="Source not found")

        source_row = dict(rows[0])
        config = _SourceConfig(str(source_row["config_json"]))
        if not config.has_auth():
            return TestAuthResponse(
                status="error", message="No authentication configured for this source"
            )

        # Pick a recent article URL
        article_rows = list(
            await db.execute_fetchall(
                """
                SELECT url, content_snippet FROM articles
                WHERE source_id = ?
                ORDER BY published_at DESC
                LIMIT 1
                """,
                (source_id,),
            )
        )
        if not article_rows:
            return TestAuthResponse(
                status="error", message="No articles found — fetch first"
            )

        test_url = str(article_rows[0][0])
        snippet = str(article_rows[0][1]) if article_rows[0][1] else None
        raw_avg = source_row.get("avg_content_length")
        avg_length = float(raw_avg) if raw_avg else None
    finally:
        await db.close()

    # Fetch with auth cookies
    headers = {"User-Agent": "Sift/0.1 (personal news aggregator)", **config.get_auth_headers()}
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            resp = await client.get(test_url, timeout=15.0)
            resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        return TestAuthResponse(status="error", message=f"Fetch failed: {e}")

    try:
        text = await asyncio.to_thread(trafilatura.extract, resp.text)
    except Exception as e:
        return TestAuthResponse(status="error", message=f"Extraction failed: {e}")

    if not text:
        return TestAuthResponse(status="error", content_length=0, message="No content extracted")

    content_length = len(text)

    # Check truncation
    from backend.extraction.extractor import _detect_truncation

    if _detect_truncation(text, snippet, avg_length):
        return TestAuthResponse(
            status="truncated",
            content_length=content_length,
            message="Content appears truncated — cookies may be expired",
        )

    return TestAuthResponse(
        status="ok",
        content_length=content_length,
        message="Full content extracted successfully",
    )


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication: strip tracking params, www, trailing slash."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)

    # Strip www
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]

    # Strip tracking params
    strip_params = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref"}
    query = parse_qs(parsed.query)
    filtered = {k: v for k, v in query.items() if k not in strip_params}
    new_query = urlencode(filtered, doseq=True) if filtered else ""

    # Strip trailing slash
    path = parsed.path.rstrip("/") or "/"

    return urlunparse(("https", host, path, "", new_query, ""))
