from httpx import AsyncClient

from backend.database import get_db


async def _seed_article_with_tags(client: AsyncClient) -> int:
    """Create a source, article, and tags for testing. Returns article ID."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO sources (name, slug, source_type) VALUES ('Test', 'test', 'rss')"
        )
        await db.execute(
            """
            INSERT INTO articles (id, source_id, url, url_normalized, title, relevance_score)
            VALUES (1, 1, 'https://example.com/a', 'example.com/a', 'Test Article', 5.0)
            """
        )
        await db.execute("INSERT INTO tags (id, name) VALUES (1, 'python')")
        await db.execute("INSERT INTO tags (id, name) VALUES (2, 'ai')")
        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id, confidence) VALUES (1, 1, 1.0)"
        )
        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id, confidence) VALUES (1, 2, 0.8)"
        )
        await db.commit()
    finally:
        await db.close()
    return 1


async def test_feedback_updates_preferences(client: AsyncClient) -> None:
    article_id = await _seed_article_with_tags(client)

    # Submit positive feedback (article score < 7.0, so this is "missed")
    resp = await client.post("/api/feedback", json={"article_id": article_id, "rating": 1})
    assert resp.status_code == 200

    # Check preferences reflect tag weight changes
    resp = await client.get("/api/preferences")
    assert resp.status_code == 200
    prefs = resp.json()
    assert prefs["profile_version"] == 1
    assert "python" in prefs["tag_weights"]
    assert prefs["tag_weights"]["python"] > 0


async def test_manual_preference_edit(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/preferences",
        json={"prose_profile": "I like systems programming", "interests": ["rust", "linux"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["prose_profile"] == "I like systems programming"
    assert data["interests"] == ["rust", "linux"]
    assert data["profile_version"] == 1

    # Verify persistence
    resp = await client.get("/api/preferences")
    assert resp.json()["prose_profile"] == "I like systems programming"


async def test_tag_weight_reset(client: AsyncClient) -> None:
    article_id = await _seed_article_with_tags(client)

    # Build up a tag weight via feedback
    await client.post("/api/feedback", json={"article_id": article_id, "rating": 1})
    resp = await client.get("/api/preferences/tags")
    assert resp.status_code == 200
    tags = resp.json()
    tag_names = [t["name"] for t in tags]
    assert "python" in tag_names

    # Delete the tag weight
    resp = await client.delete("/api/preferences/tags/python")
    assert resp.status_code == 200

    # Verify it's gone
    resp = await client.get("/api/preferences/tags")
    tag_names = [t["name"] for t in resp.json()]
    assert "python" not in tag_names
