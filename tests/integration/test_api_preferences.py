import pytest
from httpx import AsyncClient


class TestPreferencesAPI:
    @pytest.mark.asyncio
    async def test_get_default_preferences(self, client: AsyncClient) -> None:
        resp = await client.get("/api/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_language"] == "en"
        assert data["prose_profile"] == ""
        assert data["interests"] == []

    @pytest.mark.asyncio
    async def test_update_summary_language(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/preferences",
            json={"summary_language": "cs"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_language"] == "cs"

        # Verify persistence
        resp = await client.get("/api/preferences")
        assert resp.json()["summary_language"] == "cs"

    @pytest.mark.asyncio
    async def test_update_language_preserves_other_fields(self, client: AsyncClient) -> None:
        # Set profile first
        await client.put(
            "/api/preferences",
            json={"prose_profile": "I like Python", "interests": ["python"]},
        )

        # Update only language
        resp = await client.put(
            "/api/preferences",
            json={"summary_language": "cs"},
        )
        data = resp.json()
        assert data["prose_profile"] == "I like Python"
        assert data["interests"] == ["python"]
        assert data["summary_language"] == "cs"

    @pytest.mark.asyncio
    async def test_update_increments_version(self, client: AsyncClient) -> None:
        resp1 = await client.get("/api/preferences")
        v1 = resp1.json()["profile_version"]

        await client.put("/api/preferences", json={"summary_language": "cs"})

        resp2 = await client.get("/api/preferences")
        v2 = resp2.json()["profile_version"]
        assert v2 == v1 + 1
