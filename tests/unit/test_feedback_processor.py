import json

import aiosqlite
import pytest
import pytest_asyncio

from backend.database import run_migrations
from backend.preferences.feedback_processor import process_feedback
from backend.preferences.tag_weights import DELTA_MISSED, DELTA_NEGATIVE, DELTA_POSITIVE


@pytest_asyncio.fixture
async def db() -> aiosqlite.Connection:
    """In-memory SQLite database with schema and a test article with tags."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn)

    # Insert a source + article
    await conn.execute(
        "INSERT INTO sources (name, slug, source_type) VALUES ('Test', 'test', 'rss')"
    )
    await conn.execute(
        """
        INSERT INTO articles (id, source_id, url, url_normalized, title, relevance_score)
        VALUES (1, 1, 'https://example.com/a', 'example.com/a', 'Test Article', 5.0)
        """
    )

    # Insert tags
    await conn.execute("INSERT INTO tags (id, name) VALUES (1, 'python')")
    await conn.execute("INSERT INTO tags (id, name) VALUES (2, 'ai')")
    await conn.execute(
        "INSERT INTO article_tags (article_id, tag_id, confidence) VALUES (1, 1, 1.0)"
    )
    await conn.execute(
        "INSERT INTO article_tags (article_id, tag_id, confidence) VALUES (1, 2, 0.8)"
    )
    await conn.commit()

    yield conn  # type: ignore[misc]
    await conn.close()


async def _get_weights(db: aiosqlite.Connection) -> dict[str, float]:
    rows = await db.execute_fetchall("SELECT tag_weights_json FROM user_profile WHERE id = 1")
    return json.loads(str(rows[0][0]))  # type: ignore[no-any-return]


async def _get_version(db: aiosqlite.Connection) -> int:
    rows = await db.execute_fetchall("SELECT profile_version FROM user_profile WHERE id = 1")
    return int(rows[0][0])


@pytest.mark.asyncio
async def test_positive_feedback_increases_weights(db: aiosqlite.Connection) -> None:
    # Article score is 5.0 (below threshold), so this is a "missed" signal
    await process_feedback(db, article_id=1, rating=1)
    weights = await _get_weights(db)
    assert weights["python"] == pytest.approx(DELTA_MISSED)
    assert weights["ai"] == pytest.approx(DELTA_MISSED * 0.8)


@pytest.mark.asyncio
async def test_negative_feedback_decreases_weights(db: aiosqlite.Connection) -> None:
    await process_feedback(db, article_id=1, rating=-1)
    weights = await _get_weights(db)
    assert weights["python"] == pytest.approx(DELTA_NEGATIVE)
    assert weights["ai"] == pytest.approx(DELTA_NEGATIVE * 0.8)


@pytest.mark.asyncio
async def test_missed_uses_stronger_delta(db: aiosqlite.Connection) -> None:
    """Article score < 7.0 + positive rating = missed signal (stronger delta)."""
    await process_feedback(db, article_id=1, rating=1)
    weights = await _get_weights(db)
    assert weights["python"] == pytest.approx(DELTA_MISSED)
    assert DELTA_MISSED > DELTA_POSITIVE


@pytest.mark.asyncio
async def test_positive_on_high_score_uses_normal_delta(db: aiosqlite.Connection) -> None:
    """Article score >= 7.0 + positive = normal positive delta."""
    await db.execute("UPDATE articles SET relevance_score = 8.0 WHERE id = 1")
    await db.commit()
    await process_feedback(db, article_id=1, rating=1)
    weights = await _get_weights(db)
    assert weights["python"] == pytest.approx(DELTA_POSITIVE)


@pytest.mark.asyncio
async def test_neutral_rating_is_noop(db: aiosqlite.Connection) -> None:
    await process_feedback(db, article_id=1, rating=0)
    weights = await _get_weights(db)
    assert weights == {}


@pytest.mark.asyncio
async def test_no_tags_is_noop(db: aiosqlite.Connection) -> None:
    """Article with no tags should not change weights."""
    await db.execute("DELETE FROM article_tags WHERE article_id = 1")
    await db.commit()
    await process_feedback(db, article_id=1, rating=1)
    weights = await _get_weights(db)
    assert weights == {}


@pytest.mark.asyncio
async def test_version_bumps(db: aiosqlite.Connection) -> None:
    assert await _get_version(db) == 0
    await process_feedback(db, article_id=1, rating=1)
    assert await _get_version(db) == 1
    await process_feedback(db, article_id=1, rating=-1)
    assert await _get_version(db) == 2
