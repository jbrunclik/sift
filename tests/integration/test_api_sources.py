import pytest
from httpx import AsyncClient


class TestSourceCategories:
    @pytest.mark.asyncio
    async def test_create_source_with_category(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/sources",
            json={
                "name": "Tech News",
                "slug": "tech-news",
                "source_type": "rss",
                "config_json": '{"feed_url": "https://example.com/rss"}',
                "category": "Technology",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "Technology"

    @pytest.mark.asyncio
    async def test_create_source_without_category(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/sources",
            json={
                "name": "No Cat",
                "slug": "no-cat",
                "source_type": "rss",
                "config_json": '{"feed_url": "https://example.com/rss"}',
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == ""

    @pytest.mark.asyncio
    async def test_list_sources_includes_category(self, client: AsyncClient) -> None:
        await client.post(
            "/api/sources",
            json={
                "name": "Cat Source",
                "slug": "cat-source",
                "source_type": "rss",
                "config_json": '{"feed_url": "https://example.com/rss"}',
                "category": "Science",
            },
        )
        resp = await client.get("/api/sources")
        assert resp.status_code == 200
        sources = resp.json()
        assert any(s["category"] == "Science" for s in sources)
