from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.extraction.extractor import (
    DOMAIN_COOLDOWN_SECONDS,
    MAX_RESPONSE_BYTES,
    extract_articles,
    extract_single_article,
)
from backend.scoring.prompts import (
    HEAD_CHARS,
    MAX_CONTENT_CHARS,
    TAIL_CHARS,
    ArticlePromptData,
    build_batch_prompt,
)


class TestExtractSingleArticle:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock(spec=httpx.AsyncClient)
        return client

    async def test_success(self, mock_client: AsyncMock) -> None:
        response = httpx.Response(
            200,
            text="<html><body><p>Article text here</p></body></html>",
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(return_value=response)

        with patch("backend.extraction.extractor.trafilatura") as mock_traf:
            mock_traf.extract.return_value = "Article text here"
            result = await extract_single_article("https://example.com/article", mock_client)

        assert result == "Article text here"

    async def test_fetch_failure_returns_none(self, mock_client: AsyncMock) -> None:
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await extract_single_article("https://example.com/article", mock_client)
        assert result is None

    async def test_http_error_returns_none(self, mock_client: AsyncMock) -> None:
        response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(return_value=response)

        result = await extract_single_article("https://example.com/article", mock_client)
        assert result is None

    async def test_empty_extraction_returns_empty_string(self, mock_client: AsyncMock) -> None:
        response = httpx.Response(
            200,
            text="<html><body></body></html>",
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(return_value=response)

        with patch("backend.extraction.extractor.trafilatura") as mock_traf:
            mock_traf.extract.return_value = None
            result = await extract_single_article("https://example.com/article", mock_client)

        assert result == ""

    async def test_skips_oversized_response_content_length(self, mock_client: AsyncMock) -> None:
        response = httpx.Response(
            200,
            text="small",
            headers={"content-length": str(MAX_RESPONSE_BYTES + 1)},
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(return_value=response)

        result = await extract_single_article("https://example.com/big", mock_client)
        assert result is None

    async def test_skips_oversized_response_body(self, mock_client: AsyncMock) -> None:
        big_content = "x" * (MAX_RESPONSE_BYTES + 1)
        response = httpx.Response(
            200,
            text=big_content,
            request=httpx.Request("GET", "https://example.com"),
        )
        mock_client.get = AsyncMock(return_value=response)

        result = await extract_single_article("https://example.com/big", mock_client)
        assert result is None

    async def test_timeout_returns_none(self, mock_client: AsyncMock) -> None:
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))

        result = await extract_single_article("https://example.com/slow", mock_client)
        assert result is None


class TestExtractArticles:
    async def test_batch_extraction(self, tmp_path: object) -> None:
        """Test that extract_articles processes a batch and returns stats."""
        mock_db = AsyncMock()
        mock_db.execute_fetchall = AsyncMock(
            return_value=[
                (1, "https://example.com/a1"),
                (2, "https://other.com/a2"),
            ]
        )
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.close = AsyncMock()

        with (
            patch("backend.extraction.extractor.get_db", return_value=mock_db),
            patch("backend.extraction.extractor.extract_single_article") as mock_extract,
        ):
            mock_extract.side_effect = ["Extracted text", "More text"]
            stats = await extract_articles()

        assert stats["total"] == 2
        assert stats["success"] == 2
        assert stats["failed"] == 0

    async def test_empty_batch(self) -> None:
        """Test that empty batch returns zero stats."""
        mock_db = AsyncMock()
        mock_db.execute_fetchall = AsyncMock(return_value=[])
        mock_db.close = AsyncMock()

        with patch("backend.extraction.extractor.get_db", return_value=mock_db):
            stats = await extract_articles()

        assert stats == {"total": 0, "success": 0, "failed": 0, "skipped": 0}


class TestPerDomainRateLimiting:
    def test_cooldown_constant(self) -> None:
        """Verify the domain cooldown is set to 2 seconds."""
        assert DOMAIN_COOLDOWN_SECONDS == 2.0


class TestHeadTailTruncation:
    def _make_article(self, content: str) -> ArticlePromptData:
        return ArticlePromptData(
            title="Test",
            source_name="Test Source",
            author=None,
            published_at=None,
            url="https://example.com",
            content=content,
        )

    def test_short_content_not_truncated(self) -> None:
        content = "x" * 100
        result = build_batch_prompt([self._make_article(content)])
        assert content in result
        assert "[...]" not in result

    def test_exact_limit_not_truncated(self) -> None:
        content = "x" * MAX_CONTENT_CHARS
        result = build_batch_prompt([self._make_article(content)])
        assert content in result
        assert "[...]" not in result

    def test_over_limit_uses_head_tail(self) -> None:
        head = "H" * (HEAD_CHARS + 100)
        tail = "T" * (TAIL_CHARS + 100)
        content = head + tail
        assert len(content) > MAX_CONTENT_CHARS

        result = build_batch_prompt([self._make_article(content)])
        assert "[...]" in result
        # Head portion preserved
        assert "H" * HEAD_CHARS in result
        # Tail portion preserved
        assert "T" * TAIL_CHARS in result

    def test_truncation_preserves_boundaries(self) -> None:
        content = "A" * 5000 + "B" * 2000
        result = build_batch_prompt([self._make_article(content)])
        # Should have head (first 3000) + [...] + tail (last 1000)
        assert "[...]" in result
        # Last 1000 chars of original are all B's
        assert "B" * TAIL_CHARS in result
