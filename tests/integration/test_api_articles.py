from httpx import AsyncClient


async def test_list_articles_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/articles")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


async def test_stats_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_articles"] == 0
