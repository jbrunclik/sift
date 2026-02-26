from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.database import init_db, run_migrations, set_db_path
from backend.main import create_app


@pytest_asyncio.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    """In-memory SQLite database with all migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    """FastAPI app instance for testing with a temp database."""
    db_path = str(tmp_path / "test.db")
    set_db_path(db_path)
    # Initialize DB with migrations
    conn = await init_db()
    await conn.close()
    yield create_app()
    set_db_path(None)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_rss_xml() -> str:
    """Sample RSS feed XML for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <link>https://example.com</link>
        <item>
          <title>Test Article 1</title>
          <link>https://example.com/article-1</link>
          <description>This is the first test article.</description>
          <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
          <author>Test Author</author>
        </item>
        <item>
          <title>Test Article 2</title>
          <link>https://example.com/article-2</link>
          <description>This is the second test article.</description>
          <pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""


@pytest.fixture
def sample_hn_topstories() -> list[int]:
    """Sample Hacker News story IDs."""
    return [123, 456, 789]


@pytest.fixture
def sample_hn_story() -> dict[str, object]:
    """Sample Hacker News story item."""
    return {
        "id": 123,
        "type": "story",
        "title": "Show HN: A cool project",
        "url": "https://example.com/cool-project",
        "by": "testuser",
        "score": 42,
        "descendants": 10,
        "time": 1704110400,
    }
