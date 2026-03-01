import json
import logging
import sqlite3
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db
from backend.models import FetchLog, Source, SourceCreate
from backend.sources import get_source_class

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


@router.post("")
async def create_source(source: SourceCreate) -> Source:
    db = await get_db()
    try:
        # Validate source_type
        if not get_source_class(source.source_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source type: {source.source_type}",
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
            async with httpx.AsyncClient() as http_client:
                config = SourceConfig(str(source_row["config_json"]))
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
