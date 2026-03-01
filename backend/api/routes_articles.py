import logging
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from backend.database import get_db
from backend.models import Article, ArticleListParams

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles", tags=["articles"])

# Default threshold: only show articles the LLM is confident about
CURATED_MIN_SCORE = 7.0


async def _load_tags_for_articles(
    db: aiosqlite.Connection, article_ids: list[int]
) -> dict[int, list[str]]:
    """Batch-load tags for a list of article IDs."""
    if not article_ids:
        return {}
    placeholders = ",".join("?" for _ in article_ids)
    rows = await db.execute_fetchall(
        f"SELECT at.article_id, t.name FROM article_tags at "
        f"JOIN tags t ON at.tag_id = t.id "
        f"WHERE at.article_id IN ({placeholders})",
        article_ids,
    )
    result: dict[int, list[str]] = {}
    for row in rows:
        aid = int(row[0])
        result.setdefault(aid, []).append(str(row[1]))
    return result


def _row_to_article(row: Any) -> Article:
    """Convert a database row (as dict) to an Article model."""
    return Article(
        id=int(row["id"]),
        source_id=int(row["source_id"]),
        external_id=row.get("external_id"),
        url=str(row["url"]),
        url_normalized=str(row["url_normalized"]),
        title=str(row["title"]),
        author=row.get("author"),
        content_snippet=row.get("content_snippet"),
        content_full=row.get("content_full"),
        published_at=row.get("published_at"),
        fetched_at=row["fetched_at"],
        relevance_score=row.get("relevance_score"),
        score_explanation=row.get("score_explanation"),
        summary=row.get("summary"),
        scored_at=row.get("scored_at"),
        language=str(row.get("language", "en")),
        image_url=row.get("image_url"),
        extra_json=str(row.get("extra_json", "{}")),
        is_read=bool(row.get("is_read", 0)),
        is_hidden=bool(row.get("is_hidden", 0)),
        created_at=row["created_at"],
        source_name=row.get("source_name"),
        source_slug=row.get("source_slug"),
        feedback=row.get("feedback_rating"),
    )


@router.get("")
async def list_articles(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: float | None = None,
    source_slug: str | None = None,
    search: str | None = None,
    show_all: bool = False,
    unread: bool = False,
) -> list[Article]:
    params = ArticleListParams(
        limit=limit,
        offset=offset,
        min_score=min_score,
        source_slug=source_slug,
        search=search,
        show_all=show_all,
        unread=unread,
    )

    db = await get_db()
    try:
        conditions = ["a.is_hidden = 0"]
        args: list[object] = []

        # Always exclude unscored articles — they're not ready for the user
        conditions.append("a.relevance_score IS NOT NULL")

        # Apply score filtering:
        # - If searching, show all scored results regardless of score
        # - If explicit min_score provided, use that
        # - If show_all (training mode), show all scored articles
        # - Default: curated feed — only scored articles above threshold
        if params.search:
            conditions.append("a.id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?)")
            args.append(params.search)
        elif params.min_score is not None:
            conditions.append("a.relevance_score >= ?")
            args.append(params.min_score)
        elif not params.show_all:
            conditions.append("a.relevance_score >= ?")
            args.append(CURATED_MIN_SCORE)

        if params.source_slug:
            conditions.append("s.slug = ?")
            args.append(params.source_slug)

        if params.unread:
            conditions.append("a.is_read = 0")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT a.*,
                   s.name as source_name,
                   s.slug as source_slug,
                   f.rating as feedback_rating
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            LEFT JOIN feedback f ON a.id = f.article_id
            WHERE {where_clause}
            ORDER BY
                CASE WHEN a.relevance_score IS NOT NULL
                     THEN a.relevance_score ELSE -1 END DESC,
                a.published_at DESC NULLS LAST
            LIMIT ? OFFSET ?
        """
        args.extend([params.limit, params.offset])

        rows = await db.execute_fetchall(query, args)
        articles = [_row_to_article(dict(row)) for row in rows]
        tags_map = await _load_tags_for_articles(db, [a.id for a in articles])
        for article in articles:
            article.tags = tags_map.get(article.id, [])
        return articles
    finally:
        await db.close()


@router.get("/{article_id}")
async def get_article(article_id: int) -> Article:
    db = await get_db()
    try:
        rows = list(
            await db.execute_fetchall(
                """
                SELECT a.*,
                       s.name as source_name,
                       s.slug as source_slug,
                       f.rating as feedback_rating
                FROM articles a
                JOIN sources s ON a.source_id = s.id
                LEFT JOIN feedback f ON a.id = f.article_id
                WHERE a.id = ?
                """,
                (article_id,),
            )
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Article not found")
        article = _row_to_article(dict(rows[0]))
        tags_map = await _load_tags_for_articles(db, [article.id])
        article.tags = tags_map.get(article.id, [])
        return article
    finally:
        await db.close()


@router.post("/{article_id}/read")
async def mark_read(article_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        cursor = await db.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (article_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "ok"}
    finally:
        await db.close()


@router.post("/{article_id}/unread")
async def mark_unread(article_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        cursor = await db.execute("UPDATE articles SET is_read = 0 WHERE id = ?", (article_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "ok"}
    finally:
        await db.close()


@router.post("/{article_id}/hide")
async def hide_article(article_id: int) -> dict[str, str]:
    db = await get_db()
    try:
        cursor = await db.execute("UPDATE articles SET is_hidden = 1 WHERE id = ?", (article_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"status": "ok"}
    finally:
        await db.close()
