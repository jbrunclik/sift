import asyncio
import logging
from datetime import UTC, datetime

import aiosqlite

from backend.config import settings
from backend.database import get_db
from backend.preferences.tag_vocabulary import (
    maybe_bootstrap_vocabulary,
    record_candidate,
    resolve_tag,
)
from backend.scoring.deduplicator import (
    ArticleForScoring,
    DeduplicatedGroup,
    find_duplicate_groups,
)
from backend.scoring.pricing import calculate_cost
from backend.scoring.prompts import ArticlePromptData, build_batch_prompt, build_system_prompt
from backend.scoring.scorer import (
    BATCH_SIZE,
    BatchTooLargeError,
    ScoringError,
    ScoringResult,
    create_gemini_client,
    score_batch,
)

logger = logging.getLogger(__name__)


class PipelineStats:
    """Collects stats during a scoring pipeline run."""

    def __init__(self) -> None:
        self.articles_found: int = 0
        self.unique_groups: int = 0
        self.batches: int = 0
        self.scored: int = 0
        self.failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "articles_found": self.articles_found,
            "unique_groups": self.unique_groups,
            "batches": self.batches,
            "scored": self.scored,
            "failed": self.failed,
        }


async def run_scoring_pipeline() -> dict[str, int]:
    """Main entry point: score all unscored articles. Returns stats dict."""
    stats = PipelineStats()
    try:
        client = create_gemini_client()
    except ValueError:
        logger.warning("Scoring skipped: no Gemini API key configured")
        return stats.to_dict()

    db = await get_db()
    try:
        articles = await _fetch_unscored_articles(db)
        stats.articles_found = len(articles)
        if not articles:
            logger.debug("No unscored articles to process")
            return stats.to_dict()

        logger.info("Scoring %d unscored articles", len(articles))

        groups = find_duplicate_groups(articles)
        stats.unique_groups = len(groups)
        logger.info("Deduplicated to %d unique articles", len(groups))

        # Fetch user profile for prompt building
        system_prompt, vocabulary = await _build_system_prompt(db)

        # Chunk groups into batches of BATCH_SIZE
        batches: list[list[DeduplicatedGroup]] = []
        for i in range(0, len(groups), BATCH_SIZE):
            batches.append(groups[i : i + BATCH_SIZE])
        stats.batches = len(batches)

        # Score batches concurrently with semaphore
        semaphore = asyncio.Semaphore(settings.scoring_max_concurrent)

        async def _score_one_batch(batch: list[DeduplicatedGroup]) -> None:
            async with semaphore:
                ok = await _process_batch(client, system_prompt, vocabulary, batch, db)
                if ok:
                    stats.scored += len(batch)
                else:
                    stats.failed += len(batch)

        await asyncio.gather(*[_score_one_batch(batch) for batch in batches])

        logger.info("Scoring pipeline complete")
        return stats.to_dict()
    finally:
        await db.close()


async def _fetch_unscored_articles(
    db: aiosqlite.Connection,
) -> list[ArticleForScoring]:
    """Fetch articles that haven't been scored yet, including failed ones for retry."""
    rows = await db.execute_fetchall(
        """
        SELECT a.id, a.source_id, a.url_normalized, a.title, a.author,
               a.content_snippet, a.content_full, a.published_at,
               s.name as source_name
        FROM articles a
        JOIN sources s ON a.source_id = s.id
        WHERE (a.relevance_score IS NULL AND a.scored_at IS NULL)
           OR (a.relevance_score = -1.0 AND a.score_attempts < 3)
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


async def _build_system_prompt(db: aiosqlite.Connection) -> tuple[str, list[str]]:
    """Build the system prompt from the user profile. Returns (prompt, vocabulary)."""
    rows = list(
        await db.execute_fetchall(
            "SELECT prose_profile, tag_weights_json, interests_json, summary_language"
            " FROM user_profile WHERE id = 1"
        )
    )

    # Get approved vocabulary for tag constraint (bootstraps on cold start)
    vocabulary = await maybe_bootstrap_vocabulary(db)

    if rows:
        row = rows[0]
        prompt = build_system_prompt(
            prose_profile=str(row[0] or ""),
            tag_weights_json=str(row[1] or "{}"),
            interests_json=str(row[2] or "[]"),
            summary_language=str(row[3] or "en"),
            approved_tags=vocabulary,
        )
    else:
        prompt = build_system_prompt("", "{}", "[]", approved_tags=vocabulary)
    return prompt, vocabulary


async def _process_batch(
    client: object,
    system_prompt: str,
    vocabulary: list[str],
    batch: list[DeduplicatedGroup],
    db: aiosqlite.Connection,
) -> bool:
    """Score a single batch of deduplicated groups and store results. Returns True on success."""
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
        batch_result = await score_batch(client, system_prompt, batch_prompt, article_ids)  # type: ignore[arg-type]
    except BatchTooLargeError as e:
        if len(batch) == 1:
            # Already a single article — cannot split further
            logger.error("Single article too large for scoring: %s", e.reason)
            await _mark_as_scored_with_no_result(db, all_group_ids, reason=e.reason)
            return False
        logger.warning(
            "Batch of %d hit MAX_TOKENS, retrying articles individually", len(batch)
        )
        all_ok = True
        for group in batch:
            ok = await _process_batch(client, system_prompt, vocabulary, [group], db)
            if not ok:
                all_ok = False
        return all_ok
    except ScoringError as e:
        logger.error("Batch scoring failed: %s", e.reason)
        await _mark_as_scored_with_no_result(db, all_group_ids, reason=e.reason)
        return False

    # Log scoring cost
    cost = calculate_cost(settings.gemini_model, batch_result.tokens_in, batch_result.tokens_out)
    await db.execute(
        """
        INSERT INTO scoring_logs (batch_size, tokens_in, tokens_out, model, cost_usd)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            len(batch),
            batch_result.tokens_in,
            batch_result.tokens_out,
            settings.gemini_model,
            cost,
        ),
    )

    # Store results, mapping each result to all article IDs in the group
    now = datetime.now(UTC).isoformat()
    for group, result in zip(batch, batch_result.results, strict=True):
        await _store_scoring_result(db, group, result, now, vocabulary)

    await db.commit()
    return True


async def _store_scoring_result(
    db: aiosqlite.Connection,
    group: DeduplicatedGroup,
    result: ScoringResult,
    scored_at: str,
    vocabulary: list[str],
) -> None:
    """Store a scoring result for all articles in a deduplicated group."""
    for article_id in group.all_ids:
        await db.execute(
            """
            UPDATE articles
            SET relevance_score = ?, score_explanation = ?, summary = ?, scored_at = ?,
                score_attempts = score_attempts + 1
            WHERE id = ?
            """,
            (result.relevance_score, result.explanation, result.summary, scored_at, article_id),
        )

    # Store tags with vocabulary resolution
    primary_id = group.primary.id
    for raw_tag in result.tags:
        # Strip '+' prefix (LLM suggestion for new tag)
        is_suggestion = raw_tag.startswith("+")
        tag_name = raw_tag.lstrip("+").lower().strip()
        if not tag_name:
            continue

        if is_suggestion:
            # New tag suggestion — record as candidate
            await record_candidate(db, tag_name, primary_id)
            resolved_name = tag_name
        else:
            # Resolve against vocabulary
            resolved_name, is_candidate = resolve_tag(tag_name, vocabulary)
            if is_candidate and vocabulary:
                # Not in vocabulary — record as candidate
                await record_candidate(db, resolved_name, primary_id)

        # Insert or ignore the tag and link to articles
        await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (resolved_name,))
        tag_rows = list(
            await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (resolved_name,))
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
    *,
    reason: str = "Unknown error",
) -> None:
    """Mark articles as failed, incrementing attempt counter for retry."""
    now = datetime.now(UTC).isoformat()
    for article_id in article_ids:
        await db.execute(
            """
            UPDATE articles
            SET relevance_score = -1.0, scored_at = ?,
                score_attempts = score_attempts + 1,
                score_explanation = ?
            WHERE id = ?
            """,
            (now, reason, article_id),
        )
    await db.commit()
