"""Generic web page source with LLM-learned CSS extraction rules.

On the first fetch, sends cleaned HTML to Gemini to learn CSS selectors.
On subsequent fetches, uses BeautifulSoup with stored rules — no LLM call.
If extraction returns 0 items and rules are stale, re-learns automatically.
"""

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.config import settings
from backend.database import get_db
from backend.models import RawArticle
from backend.scoring.pricing import calculate_cost
from backend.sources.base import BaseSource, register_source

logger = logging.getLogger(__name__)

MAX_HTML_CHARS = 20_000
RULES_MIN_AGE_HOURS = 24
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


# ---- Pydantic models for LLM structured output ----


class FieldRule(BaseModel):
    selector: str
    attribute: str | None = None  # None = .get_text(), "href" = ["href"]


class ExtractionRules(BaseModel):
    item_selector: str
    title: FieldRule
    url: FieldRule
    date: FieldRule | None = None
    description: FieldRule | None = None
    date_format: str | None = None  # strftime format, e.g. "%d.%m.%Y"


class LLMExtractionResponse(BaseModel):
    """Wrapper for the Gemini structured output."""

    extraction_rules: ExtractionRules


# ---- HTML cleaning ----


def _clean_html(raw_html: str) -> str:
    """Remove scripts, styles, SVGs, and truncate for LLM context."""
    soup = BeautifulSoup(raw_html, "lxml")
    for tag_name in ("script", "style", "svg", "noscript", "iframe"):
        for tag in soup.find_all(tag_name):
            tag.decompose()
    # Remove comments
    from bs4 import Comment

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    text = str(soup)
    if len(text) > MAX_HTML_CHARS:
        text = text[:MAX_HTML_CHARS]
    return text


# ---- Field extraction helpers ----


def _extract_field(item: Tag, rule: FieldRule) -> str:
    """Extract a text/attribute value from an item using a FieldRule."""
    el = item.select_one(rule.selector)
    if el is None:
        return ""
    if rule.attribute:
        val = el.get(rule.attribute, "")
        return str(val) if isinstance(val, str) else str(val[0]) if val else ""
    return el.get_text(strip=True)


_MULTI_SPACE_RE = re.compile(r"\s+")


def _parse_date(date_str: str, date_format: str | None) -> datetime | None:
    """Parse a date string using the learned format, with fallbacks."""
    if not date_str.strip():
        return None
    # Try learned format first
    if date_format:
        try:
            return datetime.strptime(date_str.strip(), date_format).replace(tzinfo=UTC)
        except ValueError:
            pass
    # Fallback: ISO format
    try:
        return datetime.fromisoformat(date_str.strip()).replace(tzinfo=UTC)
    except ValueError:
        pass
    return None


# ---- Core extraction ----


def extract_with_rules(
    html: str, rules: ExtractionRules, base_url: str
) -> list[RawArticle]:
    """Extract articles from HTML using learned CSS selectors."""
    soup = BeautifulSoup(html, "lxml")
    items = soup.select(rules.item_selector)
    articles: list[RawArticle] = []

    for item in items:
        title = _extract_field(item, rules.title).strip()
        raw_url = _extract_field(item, rules.url).strip()
        if not title or not raw_url:
            continue

        url = urljoin(base_url, raw_url)

        published_at: datetime | None = None
        if rules.date:
            date_str = _extract_field(item, rules.date)
            published_at = _parse_date(date_str, rules.date_format)

        description: str | None = None
        if rules.description:
            description = _extract_field(item, rules.description).strip() or None

        articles.append(
            RawArticle(
                external_id=url,
                url=url,
                title=title,
                content_snippet=description,
                published_at=published_at,
            )
        )

    return articles


# ---- LLM learning ----

_LEARN_PROMPT = """\
You are an expert web scraper. Analyze this HTML page and identify CSS selectors \
to extract a list of news/document items.

The page URL is: {page_url}

Find:
1. `item_selector`: A CSS selector for the repeating container element of each item.
2. `title`: Within each item, the selector for the title text.
3. `url`: Within each item, the selector and attribute for the link URL \
(usually an <a> tag with href).
4. `date` (optional): Within each item, the selector for the date, \
and the strftime format string.
5. `description` (optional): Within each item, the selector for a summary/description.

Rules for selectors:
- All selectors except `item_selector` are RELATIVE to the item container.
- Use standard CSS selectors (tag names, classes, IDs, attributes).
- For `url`, set attribute to "href". For `title`, leave attribute as null to get text content.
- For `date_format`, use Python strftime codes \
(e.g. "%d.%m.%Y" for "01.03.2026", "%Y-%m-%d" for ISO).
- If you cannot identify a field, omit it (set to null).

Here is the cleaned HTML:

{html}
"""


async def _learn_extraction_rules(
    page_url: str, html: str, source_id: int | None
) -> ExtractionRules:
    """Ask Gemini to generate CSS extraction rules from a page's HTML."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured — cannot learn extraction rules")

    client = genai.Client(api_key=settings.gemini_api_key)
    cleaned = _clean_html(html)
    prompt = _LEARN_PROMPT.format(page_url=page_url, html=cleaned)

    last_error: Exception | None = None
    response = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    response_schema=LLMExtractionResponse,
                ),
            )
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            is_retryable = "429" in error_str or "quota" in error_str.lower()
            if is_retryable and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Gemini rate limited learning rules (attempt %d/%d), retry in %.1fs",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            raise

    if response is None:
        raise RuntimeError(f"Failed to learn rules after {MAX_RETRIES} retries: {last_error}")

    # Track token usage
    tokens_in = 0
    tokens_out = 0
    if response.usage_metadata:
        tokens_in = response.usage_metadata.prompt_token_count or 0
        tokens_out = response.usage_metadata.candidates_token_count or 0

    # Log cost
    cost = calculate_cost(settings.gemini_model, tokens_in, tokens_out)
    logger.info(
        "Learned extraction rules for %s: %d tokens in, %d tokens out, $%.6f",
        page_url,
        tokens_in,
        tokens_out,
        cost,
    )

    # Store cost in scoring_logs
    if source_id is not None:
        try:
            db = await get_db()
            try:
                await db.execute(
                    """
                    INSERT INTO scoring_logs (batch_size, tokens_in, tokens_out, model, cost_usd)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (0, tokens_in, tokens_out, settings.gemini_model, cost),
                )
                await db.commit()
            finally:
                await db.close()
        except Exception:
            logger.warning("Failed to log extraction rule learning cost", exc_info=True)

    # Check finish reason — truncated responses produce invalid JSON
    finish_reason = None
    if response.candidates:
        finish_reason = response.candidates[0].finish_reason
    if finish_reason and str(finish_reason) not in (
        "STOP", "FinishReason.STOP",
    ):
        raise RuntimeError(
            f"Gemini response truncated (finish_reason={finish_reason})"
        )

    # Parse structured output
    rules: ExtractionRules | None = None
    if response.parsed is not None:
        parsed = response.parsed
        if isinstance(parsed, LLMExtractionResponse):
            rules = parsed.extraction_rules
        elif isinstance(parsed, dict):
            # Some versions return a dict instead of the Pydantic model
            if "extraction_rules" in parsed:
                rules = ExtractionRules.model_validate(
                    parsed["extraction_rules"]
                )
            else:
                rules = ExtractionRules.model_validate(parsed)

    # Fallback: parse from text
    if rules is None:
        text = response.text or ""
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        text = re.sub(r"\n?```\s*$", "", text.strip())
        if not text:
            raise RuntimeError(
                "Empty response from Gemini when learning extraction rules"
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse Gemini response as JSON: {e}\n"
                f"Response preview: {text[:300]}"
            ) from e
        if "extraction_rules" in data:
            rules = ExtractionRules.model_validate(
                data["extraction_rules"]
            )
        else:
            rules = ExtractionRules.model_validate(data)

    return rules


# ---- Persist rules back to DB ----


async def _save_rules_to_db(
    source_id: int, rules: ExtractionRules, config_data: dict[str, object]
) -> None:
    """Persist learned extraction rules into the source's config_json."""
    config_data["extraction_rules"] = rules.model_dump()
    config_data["_rules_learned_at"] = datetime.now(UTC).isoformat()
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sources SET config_json = ? WHERE id = ?",
            (json.dumps(config_data), source_id),
        )
        await db.commit()
    finally:
        await db.close()


# ---- Source plugin ----


@register_source
class WebPageSource(BaseSource):
    """Generic web page source that uses LLM-learned CSS selectors to extract items."""

    source_type = "webpage"
    display_name = "Web Page"

    async def fetch(self) -> list[RawArticle]:
        page_url = self.config.get("page_url", "")
        if not page_url:
            logger.error("WebPage source missing page_url in config")
            return []

        # Fetch the page
        response = await self.http.get(page_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        html = response.text

        # Check for existing rules
        config_data: dict[str, object] = dict(self.config.data)
        rules_data = config_data.get("extraction_rules")

        if rules_data:
            rules = ExtractionRules.model_validate(rules_data)
            articles = extract_with_rules(html, rules, page_url)

            # If 0 items and page has content and rules are old enough, re-learn
            if not articles and len(html) > 500:
                learned_at = config_data.get("_rules_learned_at", "")
                should_relearn = False
                if learned_at:
                    try:
                        learned_dt = datetime.fromisoformat(str(learned_at))
                        age_hours = (datetime.now(UTC) - learned_dt).total_seconds() / 3600
                        should_relearn = age_hours >= RULES_MIN_AGE_HOURS
                    except ValueError:
                        should_relearn = True
                else:
                    should_relearn = True

                if should_relearn:
                    logger.info(
                        "WebPage source %s: 0 items with existing rules, re-learning",
                        page_url,
                    )
                    rules = await _learn_extraction_rules(page_url, html, self.source_id)
                    if self.source_id is not None:
                        await _save_rules_to_db(self.source_id, rules, config_data)
                    articles = extract_with_rules(html, rules, page_url)
        else:
            # No rules — learn them
            logger.info("WebPage source %s: learning extraction rules via LLM", page_url)
            rules = await _learn_extraction_rules(page_url, html, self.source_id)
            if self.source_id is not None:
                await _save_rules_to_db(self.source_id, rules, config_data)
            articles = extract_with_rules(html, rules, page_url)

        logger.info("WebPage %s: extracted %d articles", page_url, len(articles))
        return articles
