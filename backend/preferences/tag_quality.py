"""Tag quality analysis — identifies noisy or inconsistent tags."""

from dataclasses import dataclass

import aiosqlite


@dataclass(frozen=True)
class TagQuality:
    tag_id: int
    name: str
    positive_votes: int
    negative_votes: int
    total_votes: int
    disagreement_ratio: float


async def get_noisy_tags(
    db: aiosqlite.Connection,
    min_votes: int = 5,
) -> list[TagQuality]:
    """Return tags with high disagreement ratio, sorted by disagreement descending.

    Disagreement ratio = min(positive, negative) / total_votes.
    A ratio of 0.5 means equal positive and negative votes (maximum noise).
    """
    rows = await db.execute_fetchall(
        """
        SELECT tfs.tag_id, t.name, tfs.positive_votes, tfs.negative_votes
        FROM tag_feedback_stats tfs
        JOIN tags t ON tfs.tag_id = t.id
        WHERE (tfs.positive_votes + tfs.negative_votes) >= ?
        """,
        (min_votes,),
    )
    results: list[TagQuality] = []
    for row in rows:
        pos = int(row[2])
        neg = int(row[3])
        total = pos + neg
        disagreement = min(pos, neg) / total if total > 0 else 0.0
        results.append(
            TagQuality(
                tag_id=int(row[0]),
                name=str(row[1]),
                positive_votes=pos,
                negative_votes=neg,
                total_votes=total,
                disagreement_ratio=disagreement,
            )
        )
    results.sort(key=lambda x: x.disagreement_ratio, reverse=True)
    return results
