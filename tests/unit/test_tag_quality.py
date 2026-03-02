import aiosqlite
import pytest

from backend.preferences.tag_quality import get_noisy_tags


async def _setup_tag_with_stats(
    db: aiosqlite.Connection,
    name: str,
    positive: int,
    negative: int,
) -> int:
    """Create a tag and its feedback stats."""
    await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
    rows = list(await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (name,)))
    tag_id = int(rows[0][0])
    await db.execute(
        """
        INSERT INTO tag_feedback_stats (tag_id, positive_votes, negative_votes)
        VALUES (?, ?, ?)
        ON CONFLICT(tag_id) DO UPDATE SET positive_votes = ?, negative_votes = ?
        """,
        (tag_id, positive, negative, positive, negative),
    )
    await db.commit()
    return tag_id


class TestGetNoisyTags:
    @pytest.mark.asyncio
    async def test_stats_populated_on_feedback(self, db: aiosqlite.Connection) -> None:
        """Verify tag feedback stats are readable after insert."""
        tag_id = await _setup_tag_with_stats(db, "python", 8, 3)
        results = await get_noisy_tags(db, min_votes=5)
        assert len(results) == 1
        assert results[0].tag_id == tag_id
        assert results[0].positive_votes == 8
        assert results[0].negative_votes == 3

    @pytest.mark.asyncio
    async def test_noisy_detection_ordering(self, db: aiosqlite.Connection) -> None:
        """Tags with higher disagreement should come first."""
        # Equal split = 0.5 disagreement
        await _setup_tag_with_stats(db, "noisy", 5, 5)
        # Mostly positive = low disagreement
        await _setup_tag_with_stats(db, "clear", 9, 1)

        results = await get_noisy_tags(db, min_votes=5)
        assert len(results) == 2
        assert results[0].name == "noisy"
        assert results[0].disagreement_ratio == pytest.approx(0.5)
        assert results[1].name == "clear"
        assert results[1].disagreement_ratio == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_min_votes_filtering(self, db: aiosqlite.Connection) -> None:
        """Tags with fewer votes than min_votes should be excluded."""
        await _setup_tag_with_stats(db, "few", 2, 1)  # 3 total < 5
        await _setup_tag_with_stats(db, "enough", 3, 3)  # 6 total >= 5

        results = await get_noisy_tags(db, min_votes=5)
        assert len(results) == 1
        assert results[0].name == "enough"

    @pytest.mark.asyncio
    async def test_empty_stats(self, db: aiosqlite.Connection) -> None:
        """No stats should return empty list."""
        results = await get_noisy_tags(db)
        assert results == []
