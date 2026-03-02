"""Managed tag vocabulary for consistent LLM tagging.

Approved tags form the vocabulary the LLM must use. New tags suggested by
the LLM (prefixed with '+') are tracked as candidates and auto-promoted
after appearing in 3+ distinct articles.
"""

import json
import logging
from difflib import SequenceMatcher

import aiosqlite

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.85
AUTO_PROMOTE_COUNT = 3


async def get_vocabulary(db: aiosqlite.Connection) -> list[str]:
    """Return all approved tag names, sorted alphabetically."""
    rows = await db.execute_fetchall(
        "SELECT name FROM tags WHERE is_approved = 1 ORDER BY name"
    )
    return [str(row[0]) for row in rows]


async def maybe_bootstrap_vocabulary(db: aiosqlite.Connection) -> list[str]:
    """Return vocabulary, bootstrapping from article_tags if empty.

    On cold start, migration 007's one-shot bootstrap may have run before any
    articles were scored, leaving zero approved tags permanently. This re-runs
    the same promotion logic: approve any tag with >= AUTO_PROMOTE_COUNT distinct
    articles. Once vocabulary exists, this is a single cheap SELECT.
    """
    vocab = await get_vocabulary(db)
    if vocab:
        return vocab

    cursor = await db.execute(
        """
        UPDATE tags SET is_approved = 1
        WHERE id IN (
            SELECT tag_id FROM article_tags
            GROUP BY tag_id HAVING COUNT(DISTINCT article_id) >= ?
        )
        """,
        (AUTO_PROMOTE_COUNT,),
    )
    if cursor.rowcount:
        await db.commit()
        logger.info("Bootstrap promoted %d tags to vocabulary", cursor.rowcount)
        return await get_vocabulary(db)

    return []


def resolve_tag(tag: str, vocabulary: list[str]) -> tuple[str, bool]:
    """Resolve a tag against the vocabulary.

    Returns (resolved_name, is_candidate). If exact match or fuzzy match
    >= threshold, returns the vocabulary tag. Otherwise returns the original
    tag marked as candidate.
    """
    tag_lower = tag.lower().strip()

    # Exact match (case-insensitive)
    for v in vocabulary:
        if v.lower() == tag_lower:
            return v, False

    # Fuzzy match
    best_match = ""
    best_ratio = 0.0
    for v in vocabulary:
        ratio = SequenceMatcher(None, tag_lower, v.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = v

    if best_ratio >= FUZZY_THRESHOLD:
        return best_match, False

    return tag_lower, True


async def record_candidate(
    db: aiosqlite.Connection, tag_name: str, article_id: int
) -> bool:
    """Record a candidate tag occurrence. Returns True if auto-promoted."""
    # Ensure tag exists
    await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    rows = list(
        await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (tag_name,))
    )
    if not rows:
        return False
    tag_id = int(rows[0][0])

    # Record the candidate occurrence
    await db.execute(
        "INSERT OR IGNORE INTO tag_candidates (tag_id, article_id) VALUES (?, ?)",
        (tag_id, article_id),
    )

    # Check if this tag has enough occurrences to auto-promote
    count_rows = list(
        await db.execute_fetchall(
            "SELECT COUNT(*) FROM tag_candidates WHERE tag_id = ?", (tag_id,)
        )
    )
    count = int(count_rows[0][0])

    if count >= AUTO_PROMOTE_COUNT:
        await db.execute(
            "UPDATE tags SET is_approved = 1 WHERE id = ?", (tag_id,)
        )
        logger.info(
            "Auto-promoted tag '%s' to vocabulary (%d articles)",
            tag_name,
            count,
        )
        return True

    return False


async def merge_tags(
    db: aiosqlite.Connection, source_id: int, target_id: int
) -> None:
    """Merge source tag into target: repoint article_tags, transfer weight, delete source."""
    # Get tag names for logging
    source_rows = list(
        await db.execute_fetchall("SELECT name FROM tags WHERE id = ?", (source_id,))
    )
    target_rows = list(
        await db.execute_fetchall("SELECT name FROM tags WHERE id = ?", (target_id,))
    )
    if not source_rows or not target_rows:
        return
    source_name = str(source_rows[0][0])
    target_name = str(target_rows[0][0])

    # Repoint article_tags: update where target doesn't already exist
    await db.execute(
        """
        UPDATE OR IGNORE article_tags SET tag_id = ? WHERE tag_id = ?
        """,
        (target_id, source_id),
    )
    # Delete remaining (duplicates that couldn't be repointed)
    await db.execute("DELETE FROM article_tags WHERE tag_id = ?", (source_id,))

    # Repoint tag_candidates
    await db.execute(
        "UPDATE OR IGNORE tag_candidates SET tag_id = ? WHERE tag_id = ?",
        (target_id, source_id),
    )
    await db.execute("DELETE FROM tag_candidates WHERE tag_id = ?", (source_id,))

    # Transfer weight in user_profile
    profile_rows = list(
        await db.execute_fetchall(
            "SELECT tag_weights_json, profile_version FROM user_profile WHERE id = 1"
        )
    )
    if profile_rows:
        weights: dict[str, float] = json.loads(str(profile_rows[0][0]))
        if source_name in weights:
            source_weight = weights.pop(source_name)
            weights[target_name] = weights.get(target_name, 0.0) + source_weight
            version = int(profile_rows[0][1])
            await db.execute(
                """
                UPDATE user_profile
                SET tag_weights_json = ?, profile_version = ?,
                    updated_at = datetime('now')
                WHERE id = 1
                """,
                (json.dumps(weights), version + 1),
            )

    # Delete source tag (CASCADE will clean up any remaining references)
    await db.execute("DELETE FROM tags WHERE id = ?", (source_id,))

    logger.info("Merged tag '%s' into '%s'", source_name, target_name)


async def add_tag(db: aiosqlite.Connection, name: str) -> int:
    """Add a new approved tag to the vocabulary. Returns the tag id."""
    name = name.lower().strip()
    await db.execute(
        "INSERT OR IGNORE INTO tags (name, is_approved) VALUES (?, 1)", (name,)
    )
    rows = list(
        await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (name,))
    )
    tag_id = int(rows[0][0])
    # Ensure it's approved (in case it existed as unapproved)
    await db.execute("UPDATE tags SET is_approved = 1 WHERE id = ?", (tag_id,))
    return tag_id


async def remove_tag(db: aiosqlite.Connection, tag_id: int) -> None:
    """Remove a tag from the vocabulary (sets is_approved = 0)."""
    await db.execute("UPDATE tags SET is_approved = 0 WHERE id = ?", (tag_id,))


async def get_candidates(db: aiosqlite.Connection) -> list[dict[str, object]]:
    """Return unapproved tags with their article occurrence counts."""
    rows = await db.execute_fetchall(
        """
        SELECT t.id, t.name, COUNT(tc.article_id) as occurrences
        FROM tags t
        LEFT JOIN tag_candidates tc ON t.id = tc.tag_id
        WHERE t.is_approved = 0
        GROUP BY t.id
        HAVING occurrences > 0
        ORDER BY occurrences DESC
        """
    )
    return [
        {"id": int(row[0]), "name": str(row[1]), "occurrences": int(row[2])}
        for row in rows
    ]
