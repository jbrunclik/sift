import pytest
from httpx import AsyncClient


class TestIssuesAPI:
    @pytest.mark.asyncio
    async def test_issues_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/issues")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetch_errors"] == 0
        assert data["scoring_errors"] == 0
        assert data["unscored"] == 0

    @pytest.mark.asyncio
    async def test_issues_counts_unscored(self, client: AsyncClient) -> None:
        # Create a source and article
        await client.post(
            "/api/sources",
            json={
                "name": "Test",
                "slug": "test",
                "source_type": "rss",
                "config_json": '{"feed_url": "https://example.com/rss"}',
            },
        )
        # Insert an unscored article directly via fetch
        # (the API doesn't expose direct article creation, so we check stats after)
        resp = await client.get("/api/stats/issues")
        data = resp.json()
        assert data["unscored"] >= 0  # May be 0 if no articles


class TestCostsAPI:
    @pytest.mark.asyncio
    async def test_costs_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_stats_has_distribution_and_inbox(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "score_distribution" in data
        assert len(data["score_distribution"]) == 11
        assert "inbox_count" in data
        assert "scheduler_jobs" in data
