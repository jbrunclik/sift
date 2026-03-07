"""Tests for the Hacker News source plugin."""

import json

import httpx
import pytest
import respx

from backend.sources.base import SourceConfig
from backend.sources.hackernews import HN_API, HackerNewsSource


def _make_source(config: dict | None = None) -> HackerNewsSource:
    cfg = SourceConfig(json.dumps(config or {}))
    client = httpx.AsyncClient()
    return HackerNewsSource(config=cfg, http_client=client)


def _story(
    item_id: int = 123,
    title: str = "Show HN: A cool project",
    url: str | None = "https://example.com/cool-project",
    by: str = "testuser",
    score: int = 42,
    descendants: int = 10,
    time: int = 1704110400,
    item_type: str = "story",
    dead: bool = False,
    deleted: bool = False,
    text: str | None = None,
) -> dict:
    d: dict = {
        "id": item_id,
        "type": item_type,
        "title": title,
        "by": by,
        "score": score,
        "descendants": descendants,
        "time": time,
    }
    if url is not None:
        d["url"] = url
    if dead:
        d["dead"] = True
    if deleted:
        d["deleted"] = True
    if text is not None:
        d["text"] = text
    return d


@respx.mock
@pytest.mark.asyncio
async def test_basic_fetch(sample_hn_topstories: list[int], sample_hn_story: dict) -> None:
    """Two stories returned with correct fields."""
    story2 = _story(
        item_id=456, title="Another Post", url="https://other.com/post",
        by="user2", score=100, descendants=5,
    )
    respx.get(f"{HN_API}/topstories.json").respond(json=[123, 456])
    respx.get(f"{HN_API}/item/123.json").respond(json=sample_hn_story)
    respx.get(f"{HN_API}/item/456.json").respond(json=story2)

    source = _make_source()
    articles = await source.fetch()
    assert len(articles) == 2
    assert articles[0].title == "Show HN: A cool project"
    assert articles[0].external_id == "123"
    assert articles[0].author == "testuser"
    assert articles[0].url == "https://example.com/cool-project"
    assert articles[1].title == "Another Post"


@respx.mock
@pytest.mark.asyncio
async def test_limit_respected() -> None:
    """Limit config only fetches that many items."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1, 2, 3, 4, 5])
    respx.get(f"{HN_API}/item/1.json").respond(json=_story(item_id=1, title="A"))
    respx.get(f"{HN_API}/item/2.json").respond(json=_story(item_id=2, title="B"))

    source = _make_source({"limit": 2})
    articles = await source.fetch()
    assert len(articles) == 2


@respx.mock
@pytest.mark.asyncio
async def test_job_and_dead_filtered() -> None:
    """Non-story type and dead items are excluded."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1, 2, 3])
    respx.get(f"{HN_API}/item/1.json").respond(json=_story(item_id=1, item_type="job"))
    respx.get(f"{HN_API}/item/2.json").respond(json=_story(item_id=2, dead=True))
    respx.get(f"{HN_API}/item/3.json").respond(json=_story(item_id=3, title="Good"))

    source = _make_source()
    articles = await source.fetch()
    assert len(articles) == 1
    assert articles[0].title == "Good"


@respx.mock
@pytest.mark.asyncio
async def test_min_score_filter() -> None:
    """Low-score items are excluded."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1, 2])
    respx.get(f"{HN_API}/item/1.json").respond(json=_story(item_id=1, score=5))
    respx.get(f"{HN_API}/item/2.json").respond(json=_story(item_id=2, score=50))

    source = _make_source({"min_score": 10})
    articles = await source.fetch()
    assert len(articles) == 1
    assert articles[0].extra["hn_score"] == "50"


@respx.mock
@pytest.mark.asyncio
async def test_ask_hn_no_url() -> None:
    """Ask HN posts use discussion URL and text in content_snippet."""
    respx.get(f"{HN_API}/askstories.json").respond(json=[1])
    respx.get(f"{HN_API}/item/1.json").respond(
        json=_story(
            item_id=1, url=None, title="Ask HN: Best tools?",
            text="What are your favorite tools?",
        )
    )

    source = _make_source({"endpoint": "ask"})
    articles = await source.fetch()
    assert len(articles) == 1
    assert articles[0].url == "https://news.ycombinator.com/item?id=1"
    assert articles[0].content_snippet == "What are your favorite tools?"


@respx.mock
@pytest.mark.asyncio
async def test_partial_failure() -> None:
    """One item 500, others still returned."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1, 2])
    respx.get(f"{HN_API}/item/1.json").respond(status_code=500)
    respx.get(f"{HN_API}/item/2.json").respond(json=_story(item_id=2, title="OK"))

    source = _make_source()
    articles = await source.fetch()
    assert len(articles) == 1
    assert articles[0].title == "OK"


@respx.mock
@pytest.mark.asyncio
async def test_extra_fields() -> None:
    """hn_score and hn_comments present in extra."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1])
    respx.get(f"{HN_API}/item/1.json").respond(
        json=_story(item_id=1, score=99, descendants=15)
    )

    source = _make_source()
    articles = await source.fetch()
    assert articles[0].extra["hn_score"] == "99"
    assert articles[0].extra["hn_comments"] == "15"


@respx.mock
@pytest.mark.asyncio
async def test_timezone_aware_published_at() -> None:
    """published_at from unix timestamp has timezone info."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1])
    respx.get(f"{HN_API}/item/1.json").respond(json=_story(item_id=1, time=1704110400))

    source = _make_source()
    articles = await source.fetch()
    assert articles[0].published_at is not None
    assert articles[0].published_at.tzinfo is not None


@respx.mock
@pytest.mark.asyncio
async def test_default_config() -> None:
    """Empty config fetches topstories."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1])
    respx.get(f"{HN_API}/item/1.json").respond(json=_story(item_id=1))

    source = _make_source()
    articles = await source.fetch()
    assert len(articles) == 1


@respx.mock
@pytest.mark.asyncio
async def test_invalid_endpoint() -> None:
    """Invalid endpoint returns empty list."""
    source = _make_source({"endpoint": "nonexistent"})
    articles = await source.fetch()
    assert articles == []


@respx.mock
@pytest.mark.asyncio
async def test_html_stripped_from_text() -> None:
    """HTML tags removed from Ask HN body."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[1])
    respx.get(f"{HN_API}/item/1.json").respond(
        json=_story(item_id=1, url=None, text="<p>Hello</p><p>World &amp; stuff</p>")
    )

    source = _make_source()
    articles = await source.fetch()
    assert articles[0].content_snippet == "Hello World & stuff"


@respx.mock
@pytest.mark.asyncio
async def test_empty_story_list() -> None:
    """Empty story list returns empty."""
    respx.get(f"{HN_API}/topstories.json").respond(json=[])

    source = _make_source()
    articles = await source.fetch()
    assert articles == []
