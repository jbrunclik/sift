import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from backend.preferences.decay import DECAY_FACTOR
from backend.preferences.profile_synthesizer import synthesize_profile


class TestSynthesizeProfile:
    @pytest.mark.asyncio
    async def test_synthesis_updates_profile(self, db: aiosqlite.Connection) -> None:
        """Synthesis should decay weights, update prose, and bump version."""
        await db.execute(
            """
            UPDATE user_profile
            SET tag_weights_json = ?, prose_profile = 'old prose', profile_version = 5
            WHERE id = 1
            """,
            (json.dumps({"python": 2.0, "rust": 1.0}),),
        )
        await db.commit()

        mock_response = MagicMock()
        mock_response.text = "Interested in Python and Rust programming."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("backend.preferences.profile_synthesizer.genai.Client") as mock_genai_cls,
            patch("backend.preferences.profile_synthesizer.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test-key"
            mock_settings.gemini_model = "gemini-flash"
            mock_genai_cls.return_value = mock_client

            result = await synthesize_profile(db)

        assert result is True

        rows = list(
            await db.execute_fetchall(
                "SELECT tag_weights_json, prose_profile, profile_version"
                " FROM user_profile WHERE id = 1"
            )
        )
        weights = json.loads(str(rows[0][0]))
        prose = str(rows[0][1])
        version = int(rows[0][2])

        # Weights should be decayed
        assert weights["python"] == pytest.approx(2.0 * DECAY_FACTOR)
        assert weights["rust"] == pytest.approx(1.0 * DECAY_FACTOR)
        # Prose should be updated
        assert prose == "Interested in Python and Rust programming."
        # Version bumped
        assert version == 6

    @pytest.mark.asyncio
    async def test_no_weights_skips_synthesis(self, db: aiosqlite.Connection) -> None:
        """Empty tag weights should skip synthesis."""
        result = await synthesize_profile(db)
        assert result is False

    @pytest.mark.asyncio
    async def test_llm_failure_keeps_existing_prose(self, db: aiosqlite.Connection) -> None:
        """If LLM call fails, existing prose is preserved but decay still applies."""
        await db.execute(
            """
            UPDATE user_profile
            SET tag_weights_json = ?, prose_profile = 'existing prose', profile_version = 3
            WHERE id = 1
            """,
            (json.dumps({"python": 1.0}),),
        )
        await db.commit()

        with (
            patch("backend.preferences.profile_synthesizer.genai.Client") as mock_genai_cls,
            patch("backend.preferences.profile_synthesizer.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test-key"
            mock_settings.gemini_model = "gemini-flash"
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=RuntimeError("API error")
            )
            mock_genai_cls.return_value = mock_client

            result = await synthesize_profile(db)

        assert result is True
        rows = list(
            await db.execute_fetchall(
                "SELECT prose_profile, profile_version FROM user_profile WHERE id = 1"
            )
        )
        assert str(rows[0][0]) == "existing prose"
        assert int(rows[0][1]) == 4  # Still bumped
