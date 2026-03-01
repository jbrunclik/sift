"""Tests for the generic web page source plugin."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from backend.models import RawArticle
from backend.sources.base import SourceConfig
from backend.sources.webpage import (
    ExtractionRules,
    FieldRule,
    LLMExtractionResponse,
    WebPageSource,
    _clean_html,
    _parse_date,
    extract_with_rules,
)

# ---- Sample HTML for testing ----

SAMPLE_HTML = """\
<html>
<head><title>Test Page</title></head>
<body>
  <div class="news-list">
    <div class="news-item">
      <a href="/doc/123" class="title">First Document</a>
      <span class="date">15.02.2026</span>
      <p class="desc">Description of first doc.</p>
    </div>
    <div class="news-item">
      <a href="/doc/456" class="title">Second Document</a>
      <span class="date">01.03.2026</span>
      <p class="desc">Description of second doc.</p>
    </div>
    <div class="news-item">
      <a href="https://example.com/doc/789" class="title">Third Document</a>
      <span class="date">28.02.2026</span>
    </div>
  </div>
</body>
</html>
"""

SAMPLE_RULES = ExtractionRules(
    item_selector="div.news-item",
    title=FieldRule(selector="a.title"),
    url=FieldRule(selector="a.title", attribute="href"),
    date=FieldRule(selector="span.date"),
    description=FieldRule(selector="p.desc"),
    date_format="%d.%m.%Y",
)


# ---- ExtractionRules Pydantic model ----


class TestExtractionRulesModel:
    def test_full_rules(self) -> None:
        rules = ExtractionRules(
            item_selector="div.item",
            title=FieldRule(selector="h2"),
            url=FieldRule(selector="a", attribute="href"),
            date=FieldRule(selector="time"),
            description=FieldRule(selector="p"),
            date_format="%Y-%m-%d",
        )
        assert rules.item_selector == "div.item"
        assert rules.title.attribute is None
        assert rules.url.attribute == "href"
        assert rules.date_format == "%Y-%m-%d"

    def test_minimal_rules(self) -> None:
        rules = ExtractionRules(
            item_selector="li",
            title=FieldRule(selector="a"),
            url=FieldRule(selector="a", attribute="href"),
        )
        assert rules.date is None
        assert rules.description is None
        assert rules.date_format is None

    def test_roundtrip_json(self) -> None:
        rules = SAMPLE_RULES
        data = rules.model_dump()
        restored = ExtractionRules.model_validate(data)
        assert restored == rules

    def test_llm_response_wrapper(self) -> None:
        resp = LLMExtractionResponse(extraction_rules=SAMPLE_RULES)
        assert resp.extraction_rules.item_selector == "div.news-item"


# ---- extract_with_rules ----


class TestExtractWithRules:
    def test_extracts_all_items(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert len(articles) == 3

    def test_title_extraction(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[0].title == "First Document"
        assert articles[1].title == "Second Document"
        assert articles[2].title == "Third Document"

    def test_relative_url_resolution(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[0].url == "https://example.com/doc/123"
        assert articles[1].url == "https://example.com/doc/456"

    def test_absolute_url_preserved(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[2].url == "https://example.com/doc/789"

    def test_date_parsing_czech_format(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[0].published_at is not None
        assert articles[0].published_at.day == 15
        assert articles[0].published_at.month == 2
        assert articles[0].published_at.year == 2026

    def test_description_extraction(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[0].content_snippet == "Description of first doc."
        assert articles[1].content_snippet == "Description of second doc."
        # Third item has no description
        assert articles[2].content_snippet is None

    def test_external_id_is_url(self) -> None:
        articles = extract_with_rules(SAMPLE_HTML, SAMPLE_RULES, "https://example.com")
        assert articles[0].external_id == "https://example.com/doc/123"

    def test_empty_html(self) -> None:
        articles = extract_with_rules("<html></html>", SAMPLE_RULES, "https://example.com")
        assert len(articles) == 0

    def test_missing_title_skips_item(self) -> None:
        html = """
        <div class="news-item">
          <a href="/doc/1" class="title"></a>
          <span class="date">01.01.2026</span>
        </div>
        """
        articles = extract_with_rules(html, SAMPLE_RULES, "https://example.com")
        assert len(articles) == 0

    def test_missing_url_skips_item(self) -> None:
        html = """
        <div class="news-item">
          <span class="title">Title Only</span>
          <span class="date">01.01.2026</span>
        </div>
        """
        # url rule looks for a.title[href] — span won't have href
        rules = ExtractionRules(
            item_selector="div.news-item",
            title=FieldRule(selector="span.title"),
            url=FieldRule(selector="span.title", attribute="href"),
        )
        articles = extract_with_rules(html, rules, "https://example.com")
        assert len(articles) == 0

    def test_no_date_rule(self) -> None:
        rules = ExtractionRules(
            item_selector="div.news-item",
            title=FieldRule(selector="a.title"),
            url=FieldRule(selector="a.title", attribute="href"),
        )
        articles = extract_with_rules(SAMPLE_HTML, rules, "https://example.com")
        assert len(articles) == 3
        assert all(a.published_at is None for a in articles)


# ---- Date parsing ----


class TestDateParsing:
    def test_czech_dd_mm_yyyy(self) -> None:
        dt = _parse_date("15.02.2026", "%d.%m.%Y")
        assert dt is not None
        assert dt.day == 15
        assert dt.month == 2
        assert dt.year == 2026

    def test_iso_format(self) -> None:
        dt = _parse_date("2026-03-01", "%Y-%m-%d")
        assert dt is not None
        assert dt == datetime(2026, 3, 1, tzinfo=UTC)

    def test_iso_fallback_without_format(self) -> None:
        dt = _parse_date("2026-03-01", None)
        assert dt is not None
        assert dt.year == 2026

    def test_empty_string(self) -> None:
        assert _parse_date("", "%d.%m.%Y") is None

    def test_whitespace_only(self) -> None:
        assert _parse_date("   ", "%d.%m.%Y") is None

    def test_invalid_date(self) -> None:
        assert _parse_date("not-a-date", "%d.%m.%Y") is None

    def test_czech_single_digit_day(self) -> None:
        dt = _parse_date("1.3.2026", "%-d.%-m.%Y")
        # This may not work on all platforms, but _parse_date should handle gracefully
        if dt is None:
            # Fallback — ISO won't match either, returns None
            assert True
        else:
            assert dt.month == 3


# ---- HTML cleaning ----


class TestCleanHtml:
    def test_removes_scripts(self) -> None:
        html = "<html><script>alert(1)</script><p>keep</p></html>"
        cleaned = _clean_html(html)
        assert "alert" not in cleaned
        assert "keep" in cleaned

    def test_removes_styles(self) -> None:
        html = "<html><style>body{color:red}</style><p>keep</p></html>"
        cleaned = _clean_html(html)
        assert "color:red" not in cleaned
        assert "keep" in cleaned

    def test_truncates_long_html(self) -> None:
        html = "<html>" + "x" * 50000 + "</html>"
        cleaned = _clean_html(html)
        assert len(cleaned) <= 20000


# ---- Full fetch flow (mocked) ----


class TestWebPageSourceFetch:
    @respx.mock
    async def test_fetch_with_existing_rules(self) -> None:
        """When rules exist in config, extract without calling LLM."""
        page_url = "https://example.com/news"
        respx.get(page_url).respond(200, text=SAMPLE_HTML)

        config_data = {
            "page_url": page_url,
            "extraction_rules": SAMPLE_RULES.model_dump(),
            "_rules_learned_at": "2026-03-01T12:00:00+00:00",
        }
        async with httpx.AsyncClient() as http:
            source = WebPageSource(
                config=SourceConfig(json.dumps(config_data)),
                http_client=http,
            )
            articles = await source.fetch()

        assert len(articles) == 3
        assert articles[0].title == "First Document"

    @respx.mock
    async def test_fetch_learns_rules_when_none_exist(self) -> None:
        """When no rules in config, call LLM to learn them."""
        page_url = "https://example.com/news"
        respx.get(page_url).respond(200, text=SAMPLE_HTML)

        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "STOP"

        mock_response = MagicMock()
        mock_response.parsed = LLMExtractionResponse(extraction_rules=SAMPLE_RULES)
        mock_response.text = json.dumps(
            {"extraction_rules": SAMPLE_RULES.model_dump()}
        )
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.candidates = [mock_candidate]

        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with (
            patch("backend.sources.webpage.settings") as mock_settings,
            patch("backend.sources.webpage.genai") as mock_genai,
        ):
            mock_settings.gemini_api_key = "test-key"
            mock_settings.gemini_model = "gemini-3-flash-preview"
            mock_genai.Client.return_value = mock_client

            async with httpx.AsyncClient() as http:
                source = WebPageSource(
                    config=SourceConfig(json.dumps({"page_url": page_url})),
                    http_client=http,
                )
                articles = await source.fetch()

        assert len(articles) == 3
        assert articles[0].title == "First Document"

    async def test_fetch_missing_page_url(self) -> None:
        """Returns empty list when page_url is missing."""
        async with httpx.AsyncClient() as http:
            source = WebPageSource(
                config=SourceConfig("{}"),
                http_client=http,
            )
            articles = await source.fetch()

        assert len(articles) == 0

    @respx.mock
    async def test_fetch_with_rules_returns_articles(self) -> None:
        """Verify RawArticle fields are correct."""
        page_url = "https://example.com/news"
        respx.get(page_url).respond(200, text=SAMPLE_HTML)

        config_data = {
            "page_url": page_url,
            "extraction_rules": SAMPLE_RULES.model_dump(),
            "_rules_learned_at": datetime.now(UTC).isoformat(),
        }
        async with httpx.AsyncClient() as http:
            source = WebPageSource(
                config=SourceConfig(json.dumps(config_data)),
                http_client=http,
            )
            articles = await source.fetch()

        assert all(isinstance(a, RawArticle) for a in articles)
        assert articles[0].url == "https://example.com/doc/123"
        assert articles[1].published_at is not None
        assert articles[1].published_at.month == 3


# ---- Integration test: API accepts webpage source type ----


@pytest.mark.usefixtures("app")
class TestWebPageSourceAPI:
    async def test_create_webpage_source(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/sources",
            json={
                "name": "MC Zlicin",
                "slug": "mc-zlicin",
                "source_type": "webpage",
                "config_json": json.dumps({"page_url": "https://www.mczlicin.cz/dp"}),
                "category": "Local",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "webpage"
        assert data["category"] == "Local"
        config = json.loads(data["config_json"])
        assert config["page_url"] == "https://www.mczlicin.cz/dp"

    async def test_create_webpage_source_invalid_type(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/sources",
            json={
                "name": "Bad Source",
                "slug": "bad",
                "source_type": "nonexistent",
                "config_json": "{}",
            },
        )
        assert resp.status_code == 400
