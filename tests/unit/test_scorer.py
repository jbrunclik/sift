import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scoring.scorer import (
    BatchScoringResponse,
    BatchTooLargeError,
    ScoringError,
    ScoringResult,
    create_gemini_client,
    score_batch,
)


def _mock_client(parsed: object = None, text: str | None = None) -> MagicMock:
    """Create a mock Gemini client with the given response."""
    response = MagicMock()
    response.parsed = parsed
    response.text = text
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 200
    # Simulate a normal completion (finish_reason = STOP)
    candidate = MagicMock()
    candidate.finish_reason = "STOP"
    response.candidates = [candidate]

    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


def _make_batch_response(scores: list[float]) -> BatchScoringResponse:
    return BatchScoringResponse(
        results=[
            ScoringResult(
                relevance_score=score,
                summary=f"Summary for article with score {score}",
                explanation=f"Explanation for score {score}",
                tags=["tag1", "tag2"],
            )
            for score in scores
        ]
    )


class TestScoreBatch:
    @pytest.mark.asyncio
    async def test_success_via_parsed(self) -> None:
        batch_resp = _make_batch_response([7.5, 3.0])
        client = _mock_client(parsed=batch_resp)

        batch_result = await score_batch(client, "system", "batch", [1, 2])

        assert len(batch_result.results) == 2
        assert batch_result.results[0].relevance_score == 7.5
        assert batch_result.results[1].relevance_score == 3.0
        client.aio.models.generate_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_to_text_parsing(self) -> None:
        text = json.dumps(
            {
                "results": [
                    {
                        "relevance_score": 8.0,
                        "summary": "Good article",
                        "explanation": "Relevant",
                        "tags": ["Python"],
                    }
                ]
            }
        )
        client = _mock_client(parsed=None, text=text)

        batch_result = await score_batch(client, "system", "batch", [1])

        assert len(batch_result.results) == 1
        assert batch_result.results[0].relevance_score == 8.0

    @pytest.mark.asyncio
    async def test_fallback_text_as_array(self) -> None:
        text = json.dumps(
            [
                {
                    "relevance_score": 5.0,
                    "summary": "Ok article",
                    "explanation": "Average",
                    "tags": ["tech"],
                }
            ]
        )
        client = _mock_client(parsed=None, text=text)

        batch_result = await score_batch(client, "system", "batch", [1])
        assert len(batch_result.results) == 1
        assert batch_result.results[0].relevance_score == 5.0

    @pytest.mark.asyncio
    async def test_score_clamping(self) -> None:
        batch_resp = BatchScoringResponse(
            results=[
                ScoringResult(
                    relevance_score=15.0,
                    summary="s",
                    explanation="e",
                    tags=["t"],
                ),
                ScoringResult(
                    relevance_score=-3.0,
                    summary="s",
                    explanation="e",
                    tags=["t"],
                ),
            ]
        )
        client = _mock_client(parsed=batch_resp)

        batch_result = await score_batch(client, "system", "batch", [1, 2])
        assert batch_result.results[0].relevance_score == 10.0
        assert batch_result.results[1].relevance_score == 0.0

    @pytest.mark.asyncio
    async def test_tag_normalization(self) -> None:
        batch_resp = BatchScoringResponse(
            results=[
                ScoringResult(
                    relevance_score=5.0,
                    summary="s",
                    explanation="e",
                    tags=["  Python ", "RUST", " Machine Learning "],
                )
            ]
        )
        client = _mock_client(parsed=batch_resp)

        batch_result = await score_batch(client, "system", "batch", [1])
        assert batch_result.results[0].tags == ["python", "rust", "machine learning"]

    @pytest.mark.asyncio
    async def test_result_count_mismatch_raises(self) -> None:
        batch_resp = _make_batch_response([7.0])  # 1 result for 2 articles
        client = _mock_client(parsed=batch_resp)

        with pytest.raises(ScoringError, match="Result count mismatch"):
            await score_batch(client, "system", "batch", [1, 2])

    @pytest.mark.asyncio
    async def test_api_error_raises_scoring_error(self) -> None:
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API timeout"))

        with pytest.raises(ScoringError, match="Gemini API error"):
            await score_batch(client, "system", "batch", [1])

    @pytest.mark.asyncio
    async def test_max_tokens_raises_batch_too_large(self) -> None:
        """MAX_TOKENS finish reason should raise BatchTooLargeError (subclass of ScoringError)."""
        response = MagicMock()
        response.parsed = None
        response.text = ""
        response.usage_metadata = MagicMock()
        response.usage_metadata.prompt_token_count = 100
        response.usage_metadata.candidates_token_count = 200
        candidate = MagicMock()
        candidate.finish_reason = "FinishReason.MAX_TOKENS"
        response.candidates = [candidate]

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(return_value=response)

        with pytest.raises(BatchTooLargeError, match="truncated"):
            await score_batch(client, "system", "batch", [1, 2])

    @pytest.mark.asyncio
    async def test_other_finish_reason_raises_scoring_error(self) -> None:
        """Non-STOP, non-MAX_TOKENS finish reasons raise plain ScoringError."""
        response = MagicMock()
        response.parsed = None
        response.text = ""
        response.usage_metadata = MagicMock()
        response.usage_metadata.prompt_token_count = 100
        response.usage_metadata.candidates_token_count = 200
        candidate = MagicMock()
        candidate.finish_reason = "SAFETY"
        response.candidates = [candidate]

        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(return_value=response)

        with pytest.raises(ScoringError, match="truncated"):
            await score_batch(client, "system", "batch", [1])

        # Ensure it's NOT a BatchTooLargeError
        try:
            await score_batch(client, "system", "batch", [1])
        except BatchTooLargeError:
            pytest.fail("SAFETY should not raise BatchTooLargeError")
        except ScoringError:
            pass

    @pytest.mark.asyncio
    async def test_empty_response_raises(self) -> None:
        client = _mock_client(parsed=None, text="")

        with pytest.raises(ScoringError, match="Empty response"):
            await score_batch(client, "system", "batch", [1])


class TestCreateGeminiClient:
    def test_missing_api_key_raises(self) -> None:
        with patch("backend.scoring.scorer.settings") as mock_settings:
            mock_settings.gemini_api_key = ""
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                create_gemini_client()

    def test_valid_api_key_creates_client(self) -> None:
        with patch("backend.scoring.scorer.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key-123"
            client = create_gemini_client()
            assert client is not None
