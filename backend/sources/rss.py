import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast

import feedparser

from backend.models import RawArticle
from backend.sources.base import BaseSource, register_source

logger = logging.getLogger(__name__)


def _parse_date(entry: dict[str, Any]) -> datetime | None:
    """Try to parse a date from various feed entry fields."""
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if value:
            try:
                return cast(datetime, parsedate_to_datetime(value))
            except ValueError, TypeError:
                pass
    # feedparser sometimes provides a parsed struct
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(
                    parsed[0],
                    parsed[1],
                    parsed[2],
                    parsed[3],
                    parsed[4],
                    parsed[5],
                    tzinfo=UTC,
                )
            except ValueError, TypeError:
                pass
    return None


def _extract_content(entry: dict[str, Any]) -> str | None:
    """Extract content/summary text from a feed entry."""
    # Try content first, then summary
    if (content_list := entry.get("content")) and isinstance(content_list, list):
        return str(content_list[0].get("value", ""))
    if summary := entry.get("summary"):
        return str(summary)
    return None


def _extract_image(entry: dict[str, Any]) -> str | None:
    """Try to find an image URL from media content or enclosures."""
    # media_content
    for media in entry.get("media_content", []):
        if "image" in media.get("type", ""):
            return str(media["url"])
    # media_thumbnail
    for thumb in entry.get("media_thumbnail", []):
        if url := thumb.get("url"):
            return str(url)
    # enclosures
    for enc in entry.get("enclosures", []):
        if "image" in enc.get("type", ""):
            return str(enc.get("href", ""))
    return None


@register_source
class RSSSource(BaseSource):
    """Generic RSS/Atom feed source. Works for Feedly exports, iDNES, any standard feed."""

    source_type = "rss"
    display_name = "RSS/Atom Feed"

    async def fetch(self) -> list[RawArticle]:
        feed_url = self.config.get("feed_url", "")
        if not feed_url:
            logger.error("RSS source missing feed_url in config")
            return []

        response = await self.http.get(feed_url, follow_redirects=True, timeout=30)
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        articles: list[RawArticle] = []

        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            articles.append(
                RawArticle(
                    external_id=entry.get("id", url),
                    url=url,
                    title=title,
                    author=entry.get("author"),
                    content_snippet=_extract_content(entry),
                    published_at=_parse_date(entry),
                    image_url=_extract_image(entry),
                )
            )

        logger.info("RSS feed %s: fetched %d articles", feed_url, len(articles))
        return articles
