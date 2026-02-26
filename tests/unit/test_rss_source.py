import httpx
import respx

from backend.sources.base import SourceConfig
from backend.sources.rss import RSSSource


@respx.mock
async def test_rss_fetch_parses_articles(sample_rss_xml: str) -> None:
    feed_url = "https://example.com/feed.xml"
    respx.get(feed_url).respond(200, text=sample_rss_xml)

    async with httpx.AsyncClient() as http:
        source = RSSSource(
            config=SourceConfig(f'{{"feed_url": "{feed_url}"}}'),
            http_client=http,
        )
        articles = await source.fetch()

    assert len(articles) == 2
    assert articles[0].title == "Test Article 1"
    assert articles[0].url == "https://example.com/article-1"
    assert articles[0].author == "Test Author"
    assert articles[0].content_snippet == "This is the first test article."
    assert articles[1].title == "Test Article 2"


@respx.mock
async def test_rss_fetch_empty_feed() -> None:
    feed_url = "https://example.com/empty.xml"
    empty_feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Empty</title></channel></rss>"""
    respx.get(feed_url).respond(200, text=empty_feed)

    async with httpx.AsyncClient() as http:
        source = RSSSource(
            config=SourceConfig(f'{{"feed_url": "{feed_url}"}}'),
            http_client=http,
        )
        articles = await source.fetch()

    assert len(articles) == 0


async def test_rss_fetch_missing_url() -> None:
    async with httpx.AsyncClient() as http:
        source = RSSSource(
            config=SourceConfig("{}"),
            http_client=http,
        )
        articles = await source.fetch()

    assert len(articles) == 0
