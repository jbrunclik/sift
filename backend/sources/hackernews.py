import asyncio
import html
import logging
import re
from datetime import UTC, datetime
from typing import ClassVar

from backend.models import RawArticle
from backend.sources.base import BaseSource, register_source

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")

ENDPOINTS: dict[str, str] = {
    "top": "topstories",
    "new": "newstories",
    "best": "beststories",
    "ask": "askstories",
    "show": "showstories",
}

HN_API = "https://hacker-news.firebaseio.com/v0"


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from text."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


@register_source
class HackerNewsSource(BaseSource):
    """Hacker News source via Firebase REST API."""

    source_type = "hackernews"
    display_name = "Hacker News"

    is_platform = True
    platform_description = "Top stories, Show HN, Ask HN from Hacker News"
    config_fields: ClassVar[list[dict[str, object]]] = [
        {
            "key": "endpoint",
            "label": "Story type",
            "type": "select",
            "options": ["top", "new", "best", "ask", "show"],
            "default": "top",
        },
        {
            "key": "limit",
            "label": "Max stories",
            "type": "number",
            "min": 5,
            "max": 100,
            "default": 30,
        },
        {
            "key": "min_score",
            "label": "Min score",
            "type": "number",
            "min": 0,
            "max": 1000,
            "default": 0,
        },
    ]
    auth_type = None

    async def fetch(self) -> list[RawArticle]:
        endpoint_key = str(self.config.get("endpoint", "top"))
        api_path = ENDPOINTS.get(endpoint_key)
        if not api_path:
            logger.warning("HN: invalid endpoint %r, returning empty", endpoint_key)
            return []

        limit = int(self.config.get("limit", 30))
        min_score = int(self.config.get("min_score", 0))

        # Fetch story IDs
        resp = await self.http.get(f"{HN_API}/{api_path}.json", timeout=15)
        resp.raise_for_status()
        story_ids: list[int] = resp.json()[:limit]

        if not story_ids:
            return []

        # Fetch items concurrently with semaphore
        sem = asyncio.Semaphore(10)
        articles: list[RawArticle] = []

        async def fetch_item(item_id: int) -> RawArticle | None:
            async with sem:
                try:
                    r = await self.http.get(
                        f"{HN_API}/item/{item_id}.json", timeout=10
                    )
                    r.raise_for_status()
                    item = r.json()
                except Exception:
                    logger.warning("HN: failed to fetch item %d", item_id, exc_info=True)
                    return None

            if not item:
                return None

            # Filter non-story, dead, deleted
            if item.get("type") != "story":
                return None
            if item.get("dead") or item.get("deleted"):
                return None

            score = int(item.get("score", 0))
            if score < min_score:
                return None

            title = html.unescape(str(item.get("title", "")))
            if not title:
                return None

            # URL: external link or HN discussion page for Ask HN
            url = item.get("url")
            item_id_val = item.get("id", item_id)
            if not url:
                url = f"https://news.ycombinator.com/item?id={item_id_val}"

            # Content snippet: use text field for Ask HN / Show HN posts
            content_snippet = None
            raw_text = item.get("text")
            if raw_text:
                content_snippet = _strip_html(str(raw_text))

            # Timestamp
            published_at = None
            ts = item.get("time")
            if ts:
                published_at = datetime.fromtimestamp(int(ts), tz=UTC)

            return RawArticle(
                external_id=str(item_id_val),
                url=str(url),
                title=title,
                author=item.get("by"),
                content_snippet=content_snippet,
                published_at=published_at,
                extra={
                    "hn_score": str(score),
                    "hn_comments": str(item.get("descendants", 0)),
                },
            )

        tasks = [fetch_item(sid) for sid in story_ids]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result is not None:
                articles.append(result)

        logger.info("HN %s: fetched %d articles", endpoint_key, len(articles))
        return articles
