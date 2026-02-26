from httpx import AsyncClient


async def test_feedback_requires_valid_article(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/feedback",
        json={"article_id": 9999, "rating": 1},
    )
    assert resp.status_code == 404
