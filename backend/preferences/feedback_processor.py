import json
import logging

import aiosqlite

from backend.preferences.tag_weights import (
    DELTA_MISSED,
    DELTA_NEGATIVE,
    DELTA_POSITIVE,
    TagWithConfidence,
    adjust_weights,
    prune_zero_weights,
)

logger = logging.getLogger(__name__)

CURATED_THRESHOLD = 7.0


async def process_feedback(
    db: aiosqlite.Connection,
    article_id: int,
    rating: int,
) -> None:
    """Process feedback by adjusting tag weights in the user profile.

    Rating 0 is a no-op (undo). Positive feedback on low-score articles
    (missed) applies a stronger delta.
    """
    if rating == 0:
        return

    # Fetch article's tags + confidence
    tags_rows = await db.execute_fetchall(
        """
        SELECT t.name, at.confidence
        FROM article_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.article_id = ?
        """,
        (article_id,),
    )
    tags = [TagWithConfidence(name=str(row[0]), confidence=float(row[1])) for row in tags_rows]
    if not tags:
        return

    # Determine delta
    if rating == 1:
        # Check article score to detect "missed" signal
        score_rows = list(
            await db.execute_fetchall(
                "SELECT relevance_score FROM articles WHERE id = ?", (article_id,)
            )
        )
        score = float(score_rows[0][0]) if score_rows and score_rows[0][0] is not None else 0.0
        delta = DELTA_MISSED if score < CURATED_THRESHOLD else DELTA_POSITIVE
    else:
        delta = DELTA_NEGATIVE

    # Load current profile
    profile_rows = list(
        await db.execute_fetchall(
            "SELECT tag_weights_json, profile_version FROM user_profile WHERE id = 1"
        )
    )
    row = profile_rows[0]
    current_weights: dict[str, float] = json.loads(str(row[0]))
    version = int(row[1])

    # Adjust and prune
    new_weights = adjust_weights(current_weights, tags, delta)
    new_weights = prune_zero_weights(new_weights)

    # Save back
    await db.execute(
        """
        UPDATE user_profile
        SET tag_weights_json = ?, profile_version = ?, updated_at = datetime('now')
        WHERE id = 1
        """,
        (json.dumps(new_weights), version + 1),
    )

    # Update tag feedback stats
    is_positive = rating == 1
    for tag in tags:
        tag_rows = list(
            await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (tag.name,))
        )
        if not tag_rows:
            continue
        tag_id = int(tag_rows[0][0])
        if is_positive:
            await db.execute(
                """
                INSERT INTO tag_feedback_stats (tag_id, positive_votes, updated_at)
                VALUES (?, 1, datetime('now'))
                ON CONFLICT(tag_id) DO UPDATE SET
                    positive_votes = positive_votes + 1,
                    updated_at = datetime('now')
                """,
                (tag_id,),
            )
        else:
            await db.execute(
                """
                INSERT INTO tag_feedback_stats (tag_id, negative_votes, updated_at)
                VALUES (?, 1, datetime('now'))
                ON CONFLICT(tag_id) DO UPDATE SET
                    negative_votes = negative_votes + 1,
                    updated_at = datetime('now')
                """,
                (tag_id,),
            )
