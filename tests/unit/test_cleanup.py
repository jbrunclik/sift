from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from backend.scheduler.cleanup import run_cleanup


async def _insert_source(db: aiosqlite.Connection) -> int:
    cursor = await db.execute(
        "INSERT INTO sources (name, slug, source_type) VALUES ('Test', 'test', 'rss')"
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def _insert_article(
    db: aiosqlite.Connection,
    source_id: int,
    url: str,
    days_old: int = 0,
) -> int:
    cursor = await db.execute(
        """
        INSERT INTO articles (source_id, url, url_normalized, title,
                              created_at)
        VALUES (?, ?, ?, 'Article',
                datetime('now', ? || ' days'))
        """,
        (source_id, url, url, f"-{days_old}"),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


class TestCleanup:
    @pytest.mark.asyncio
    async def test_deletes_old_articles(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        await _insert_article(db, source_id, "https://old.com/1", days_old=100)
        await _insert_article(db, source_id, "https://new.com/2", days_old=10)

        with (
            patch("backend.scheduler.cleanup.get_db", return_value=db),
            patch.object(db, "close", new_callable=AsyncMock),
            patch("backend.scheduler.cleanup.settings") as mock_settings,
        ):
            mock_settings.article_retention_days = 90
            await run_cleanup()

        rows = await db.execute_fetchall("SELECT url FROM articles")
        urls = [str(r[0]) for r in rows]
        assert "https://new.com/2" in urls
        assert "https://old.com/1" not in urls

    @pytest.mark.asyncio
    async def test_keeps_articles_with_feedback(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        art_id = await _insert_article(db, source_id, "https://old.com/feedback", days_old=100)
        await db.execute("INSERT INTO feedback (article_id, rating) VALUES (?, 1)", (art_id,))
        await db.commit()

        with (
            patch("backend.scheduler.cleanup.get_db", return_value=db),
            patch.object(db, "close", new_callable=AsyncMock),
            patch("backend.scheduler.cleanup.settings") as mock_settings,
        ):
            mock_settings.article_retention_days = 90
            await run_cleanup()

        rows = await db.execute_fetchall("SELECT url FROM articles")
        assert len(rows) == 1
        assert str(rows[0][0]) == "https://old.com/feedback"

    @pytest.mark.asyncio
    async def test_prunes_orphaned_tags(self, db: aiosqlite.Connection) -> None:
        # Insert a tag with no article_tags reference
        await db.execute("INSERT INTO tags (name) VALUES ('orphan')")
        await db.commit()

        with (
            patch("backend.scheduler.cleanup.get_db", return_value=db),
            patch.object(db, "close", new_callable=AsyncMock),
            patch("backend.scheduler.cleanup.settings") as mock_settings,
        ):
            mock_settings.article_retention_days = 90
            await run_cleanup()

        rows = await db.execute_fetchall("SELECT name FROM tags")
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_prunes_old_fetch_logs(self, db: aiosqlite.Connection) -> None:
        source_id = await _insert_source(db)
        await db.execute(
            """
            INSERT INTO fetch_logs (source_id, started_at, status)
            VALUES (?, datetime('now', '-40 days'), 'success')
            """,
            (source_id,),
        )
        await db.execute(
            """
            INSERT INTO fetch_logs (source_id, started_at, status)
            VALUES (?, datetime('now'), 'success')
            """,
            (source_id,),
        )
        await db.commit()

        with (
            patch("backend.scheduler.cleanup.get_db", return_value=db),
            patch.object(db, "close", new_callable=AsyncMock),
            patch("backend.scheduler.cleanup.settings") as mock_settings,
        ):
            mock_settings.article_retention_days = 90
            await run_cleanup()

        rows = await db.execute_fetchall("SELECT id FROM fetch_logs")
        assert len(rows) == 1
