from datetime import UTC, datetime, timedelta

import aiosqlite
import pytest

from backend.scoring.pipeline import (
    RESCORE_VERSION_DELTA,
    maybe_rescore_borderline,
)

_source_counter = 0


async def _setup_article(
    db: aiosqlite.Connection,
    raw_score: float = 6.5,
    published_hours_ago: int = 1,
    tag_name: str = "python",
    tag_confidence: float = 0.9,
    is_read: int = 0,
) -> int:
    """Insert source + article + tag + article_tag for rescore testing."""
    global _source_counter
    _source_counter += 1
    slug = f"test-{_source_counter}"
    cursor = await db.execute(
        "INSERT INTO sources (name, slug, source_type) VALUES (?, ?, 'rss')",
        (f"Test {_source_counter}", slug),
    )
    source_id = cursor.lastrowid
    published = (datetime.now(UTC) - timedelta(hours=published_hours_ago)).isoformat()
    url = f"https://test.com/{slug}"
    cursor = await db.execute(
        """
        INSERT INTO articles (source_id, url, url_normalized, title, published_at,
                              relevance_score, raw_llm_score, scored_at, is_read)
        VALUES (?, ?, ?, 'Test', ?, ?, ?, datetime('now'), ?)
        """,
        (source_id, url, url, published, raw_score, raw_score, is_read),
    )
    art_id = cursor.lastrowid
    assert art_id is not None

    await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    tag_rows = list(
        await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (tag_name,))
    )
    tag_id = int(tag_rows[0][0])
    await db.execute(
        "INSERT INTO article_tags (article_id, tag_id, confidence) VALUES (?, ?, ?)",
        (art_id, tag_id, tag_confidence),
    )
    await db.commit()
    return art_id


class TestMaybeRescoreBorderline:
    @pytest.mark.asyncio
    async def test_below_threshold_no_op(self, db: aiosqlite.Connection) -> None:
        """Version delta below RESCORE_VERSION_DELTA does nothing."""
        await db.execute(
            "UPDATE user_profile SET profile_version = ?, last_rescore_version = ? WHERE id = 1",
            (4, 0),
        )
        await db.commit()

        count = await maybe_rescore_borderline(db, {"python": 5.0})
        assert count == 0

    @pytest.mark.asyncio
    async def test_above_threshold_rescores(self, db: aiosqlite.Connection) -> None:
        """Version delta >= RESCORE_VERSION_DELTA triggers rescore."""
        art_id = await _setup_article(db, raw_score=6.5, tag_name="python", tag_confidence=1.0)
        await db.execute(
            "UPDATE user_profile SET profile_version = ?, last_rescore_version = ? WHERE id = 1",
            (RESCORE_VERSION_DELTA, 0),
        )
        await db.commit()

        weights = {"python": 3.0}
        count = await maybe_rescore_borderline(db, weights)
        assert count == 1

        rows = list(
            await db.execute_fetchall(
                "SELECT relevance_score FROM articles WHERE id = ?", (art_id,)
            )
        )
        # 6.5 + 3.0 * 1.0 * 0.3 = 7.4
        assert float(rows[0][0]) == pytest.approx(7.4)

    @pytest.mark.asyncio
    async def test_only_borderline_articles_rescored(self, db: aiosqlite.Connection) -> None:
        """Articles outside the 5.0-8.0 band are not rescored."""
        # Score 4.0 — below band
        cursor = await db.execute(
            "INSERT INTO sources (name, slug, source_type) VALUES ('S', 's', 'rss')"
        )
        source_id = cursor.lastrowid
        published = datetime.now(UTC).isoformat()
        await db.execute(
            """
            INSERT INTO articles (source_id, url, url_normalized, title, published_at,
                                  relevance_score, raw_llm_score, scored_at)
            VALUES (?, 'https://t.com/lo', 'https://t.com/lo', 'Low',
                    ?, 4.0, 4.0, datetime('now'))
            """,
            (source_id, published),
        )
        # Score 9.0 — above band
        await db.execute(
            """
            INSERT INTO articles (source_id, url, url_normalized, title, published_at,
                                  relevance_score, raw_llm_score, scored_at)
            VALUES (?, 'https://t.com/hi', 'https://t.com/hi', 'High',
                    ?, 9.0, 9.0, datetime('now'))
            """,
            (source_id, published),
        )
        await db.execute(
            "UPDATE user_profile SET profile_version = ?, last_rescore_version = ? WHERE id = 1",
            (10, 0),
        )
        await db.commit()

        count = await maybe_rescore_borderline(db, {"python": 5.0})
        assert count == 0

    @pytest.mark.asyncio
    async def test_only_recent_articles_rescored(self, db: aiosqlite.Connection) -> None:
        """Articles older than RESCORE_RECENCY_HOURS are not rescored."""
        await _setup_article(db, raw_score=6.5, published_hours_ago=48)
        await db.execute(
            "UPDATE user_profile SET profile_version = ?, last_rescore_version = ? WHERE id = 1",
            (10, 0),
        )
        await db.commit()

        count = await maybe_rescore_borderline(db, {"python": 5.0})
        assert count == 0

    @pytest.mark.asyncio
    async def test_read_articles_skipped(self, db: aiosqlite.Connection) -> None:
        """Already-read articles are not rescored."""
        await _setup_article(db, raw_score=6.5, is_read=1)
        await db.execute(
            "UPDATE user_profile SET profile_version = ?, last_rescore_version = ? WHERE id = 1",
            (10, 0),
        )
        await db.commit()

        count = await maybe_rescore_borderline(db, {"python": 5.0})
        assert count == 0

    @pytest.mark.asyncio
    async def test_last_rescore_version_updated(self, db: aiosqlite.Connection) -> None:
        """After rescore, last_rescore_version is set to current profile_version."""
        await _setup_article(db, raw_score=6.5)
        await db.execute(
            "UPDATE user_profile SET profile_version = 15, last_rescore_version = 5 WHERE id = 1"
        )
        await db.commit()

        await maybe_rescore_borderline(db, {"python": 1.0})

        rows = list(
            await db.execute_fetchall(
                "SELECT last_rescore_version FROM user_profile WHERE id = 1"
            )
        )
        assert int(rows[0][0]) == 15
