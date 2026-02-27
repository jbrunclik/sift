import asyncio
import logging
from datetime import UTC, datetime

import aiosqlite

from backend.config import settings
from backend.database import get_db
from backend.scoring.deduplicator import (
    ArticleForScoring,
    DeduplicatedGroup,
    find_duplicate_groups,
)
from backend.scoring.prompts import ArticlePromptData, build_batch_prompt, build_system_prompt
from backend.scoring.scorer import (
    BATCH_SIZE,
    ScoringError,
    ScoringResult,
    create_gemini_client,
    score_batch,
)

logger = logging.getLogger(__name__)


async def run_scoring_pipeline() -> None:
    """Main entry point: score all unscored articles."""
    try:
        client = create_gemini_client()
    except ValueError:
        logger.warning("Scoring skipped: no Gemini API key configured")
        return

    db = await get_db()
    try:
        articles = await _fetch_unscored_articles(db)
        if not articles:
            logger.debug("No unscored articles to process")
            return

        logger.info("Scoring %d unscored articles", len(articles))

        groups = find_duplicate_groups(articles)
        logger.info("Deduplicated to %d unique articles", len(groups))

        # Fetch user profile for prompt building
        system_prompt = await _build_system_prompt(db)

        # Chunk groups into batches of BATCH_SIZE
        batches: list[list[DeduplicatedGroup]] = []
        for i in range(0, len(groups), BATCH_SIZE):
            batches.append(groups[i : i + BATCH_SIZE])

        # Score batches concurrently with semaphore
        semaphore = asyncio.Semaphore(settings.scoring_max_concurrent)

        async def _score_one_batch(batch: list[DeduplicatedGroup]) -> None:
            async with semaphore:
                await _process_batch(client, system_prompt, batch, db)

        await asyncio.gather(*[_score_one_batch(batch) for batch in batches])

        logger.info("Scoring pipeline complete")
    finally:
        await db.close()


async def _fetch_unscored_articles(
    db: aiosqlite.Connection,
) -> list[ArticleForScoring]:
    """Fetch articles that haven't been scored yet."""
    rows = await db.execute_fetchall(
        """
        SELECT a.id, a.source_id, a.url_normalized, a.title, a.author,
               a.content_snippet, a.content_full, a.published_at,
               s.name as source_name
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        WHERE a.relevance_score IS NULL AND a.scored_at IS NULL
        ORDER BY a.published_at DESC
        LIMIT 100
        """,
    )
    return [
        ArticleForScoring(
            id=int(row[0]),
            source_id=int(row[1]),
            url_normalized=str(row[2]),
            title=str(row[3]),
            author=row[4] if row[4] is not None else None,
            content_snippet=row[5] if row[5] is not None else None,
            content_full=row[6] if row[6] is not None else None,
            published_at=row[7] if row[7] is not None else None,
            source_name=str(row[8]),
        )
        for row in rows
    ]


async def _build_system_prompt(db: aiosqlite.Connection) -> str:
    """Build the system prompt from the user profile."""
    rows = list(
        await db.execute_fetchall(
            "SELECT prose_profile, tag_weights_json, interests_json FROM user_profile WHERE id = 1"
        )
    )
    if rows:
        row = rows[0]
        return build_system_prompt(
            prose_profile=str(row[0] or ""),
            tag_weights_json=str(row[1] or "{}"),
            interests_json=str(row[2] or "[]"),
        )
    return build_system_prompt("", "{}", "[]")


async def _process_batch(
    client: object,
    system_prompt: str,
    batch: list[DeduplicatedGroup],
    db: aiosqlite.Connection,
) -> None:
    """Score a single batch of deduplicated groups and store results."""
    article_ids = [group.primary.id for group in batch]
    all_group_ids = [aid for group in batch for aid in group.all_ids]

    # Build prompt from primary articles
    prompt_articles = [
        ArticlePromptData(
            title=group.primary.title,
            source_name=group.primary.source_name,
            author=group.primary.author,
            published_at=group.primary.published_at,
            url=group.primary.url_normalized,
            content=group.primary.content_full or group.primary.content_snippet or "",
        )
        for group in batch
    ]
    batch_prompt = build_batch_prompt(prompt_articles)

    try:
        results = await score_batch(client, system_prompt, batch_prompt, article_ids)  # type: ignore[arg-type]
    except ScoringError as e:
        logger.error("Batch scoring failed: %s", e.reason)
        await _mark_as_scored_with_no_result(db, all_group_ids)
        return

    # Store results, mapping each result to all article IDs in the group
    now = datetime.now(UTC).isoformat()
    for group, result in zip(batch, results, strict=True):
        await _store_scoring_result(db, group, result, now)

    await db.commit()


async def _store_scoring_result(
    db: aiosqlite.Connection,
    group: DeduplicatedGroup,
    result: ScoringResult,
    scored_at: str,
) -> None:
    """Store a scoring result for all articles in a deduplicated group."""
    for article_id in group.all_ids:
        await db.execute(
            """
            UPDATE articles
            SET relevance_score = ?, score_explanation = ?, summary = ?, scored_at = ?
            WHERE id = ?
            """,
            (result.relevance_score, result.explanation, result.summary, scored_at, article_id),
        )

    # Store tags
    for tag_name in result.tags:
        # Insert or ignore tag
        await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        tag_rows = list(
            await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (tag_name,))
        )
        if tag_rows:
            tag_id = int(tag_rows[0][0])
            for article_id in group.all_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?, ?)",
                    (article_id, tag_id),
                )


async def _mark_as_scored_with_no_result(
    db: aiosqlite.Connection,
    article_ids: list[int],
) -> None:
    """Mark articles as scored with a failure marker to prevent infinite retries."""
    now = datetime.now(UTC).isoformat()
    for article_id in article_ids:
        await db.execute(
            "UPDATE articles SET relevance_score = -1.0, scored_at = ? WHERE id = ?",
            (now, article_id),
        )
    await db.commit()
