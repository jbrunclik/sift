import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_empty_vocabulary(client: AsyncClient) -> None:
    resp = await client.get("/api/preferences/vocabulary")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_vocabulary_tag(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/preferences/vocabulary", json={"name": "python"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "python"
    assert data["id"] > 0
    assert data["article_count"] == 0


@pytest.mark.asyncio
async def test_list_vocabulary_after_add(client: AsyncClient) -> None:
    await client.post("/api/preferences/vocabulary", json={"name": "rust"})
    await client.post("/api/preferences/vocabulary", json={"name": "python"})

    resp = await client.get("/api/preferences/vocabulary")
    assert resp.status_code == 200
    tags = resp.json()
    names = [t["name"] for t in tags]
    assert "python" in names
    assert "rust" in names


@pytest.mark.asyncio
async def test_remove_vocabulary_tag(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/preferences/vocabulary", json={"name": "remove-me"}
    )
    tag_id = resp.json()["id"]

    resp = await client.delete(f"/api/preferences/vocabulary/{tag_id}")
    assert resp.status_code == 200

    # Should no longer appear in vocabulary
    resp = await client.get("/api/preferences/vocabulary")
    names = [t["name"] for t in resp.json()]
    assert "remove-me" not in names


@pytest.mark.asyncio
async def test_remove_nonexistent_tag(client: AsyncClient) -> None:
    resp = await client.delete("/api/preferences/vocabulary/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_merge_vocabulary_tags(client: AsyncClient) -> None:
    r1 = await client.post("/api/preferences/vocabulary", json={"name": "ml"})
    r2 = await client.post(
        "/api/preferences/vocabulary", json={"name": "machine-learning"}
    )
    source_id = r1.json()["id"]
    target_id = r2.json()["id"]

    resp = await client.post(
        "/api/preferences/vocabulary/merge",
        json={"source_id": source_id, "target_id": target_id},
    )
    assert resp.status_code == 200

    # Source tag should be gone
    resp = await client.get("/api/preferences/vocabulary")
    names = [t["name"] for t in resp.json()]
    assert "ml" not in names
    assert "machine-learning" in names


@pytest.mark.asyncio
async def test_merge_same_tag_fails(client: AsyncClient) -> None:
    r = await client.post("/api/preferences/vocabulary", json={"name": "self"})
    tag_id = r.json()["id"]

    resp = await client.post(
        "/api/preferences/vocabulary/merge",
        json={"source_id": tag_id, "target_id": tag_id},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_candidates_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/preferences/vocabulary/candidates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_approve_candidate(client: AsyncClient) -> None:
    # Manually insert an unapproved tag via the add then remove workflow
    r = await client.post("/api/preferences/vocabulary", json={"name": "draft-tag"})
    tag_id = r.json()["id"]
    # Remove it from vocabulary (makes it unapproved)
    await client.delete(f"/api/preferences/vocabulary/{tag_id}")

    # Now approve
    resp = await client.post(
        f"/api/preferences/vocabulary/candidates/{tag_id}/approve"
    )
    assert resp.status_code == 200

    # Should now be in vocabulary
    resp = await client.get("/api/preferences/vocabulary")
    names = [t["name"] for t in resp.json()]
    assert "draft-tag" in names


@pytest.mark.asyncio
async def test_reject_candidate(client: AsyncClient) -> None:
    r = await client.post("/api/preferences/vocabulary", json={"name": "reject-me"})
    tag_id = r.json()["id"]
    await client.delete(f"/api/preferences/vocabulary/{tag_id}")

    resp = await client.delete(
        f"/api/preferences/vocabulary/candidates/{tag_id}"
    )
    assert resp.status_code == 200

    # Tag should be completely gone
    resp = await client.get("/api/preferences/vocabulary")
    names = [t["name"] for t in resp.json()]
    assert "reject-me" not in names
