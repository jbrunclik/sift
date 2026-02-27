import contextlib
import json
from dataclasses import dataclass


@dataclass
class ArticlePromptData:
    title: str
    source_name: str
    author: str | None
    published_at: str | None
    url: str
    content: str


COLD_START_SYSTEM_PROMPT = """\
You are a relevance scoring assistant for a personal news aggregator called Sift.

The user has not yet established preferences. Score articles based on general \
quality signals:
- Well-written, informative content scores higher
- Original reporting and analysis scores higher than aggregation
- Clickbait, low-effort, or purely promotional content scores lower
- Technical depth and actionable insights score higher

For each article, provide:
- relevance_score: float 0-10 (10 = extremely relevant/high-quality)
- summary: 1-2 sentence summary of the article
- explanation: brief reason for the score
- tags: 2-5 lowercase topic tags

Return a JSON array with one result per article, in the same order as presented."""

MAX_CONTENT_CHARS = 2000


def build_system_prompt(
    prose_profile: str,
    tag_weights_json: str,
    interests_json: str,
) -> str:
    """Build the system prompt incorporating the user profile.

    Falls back to a generic cold-start prompt when the profile is empty.
    """
    tag_weights: dict[str, float] = {}
    interests: list[str] = []
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        tag_weights = json.loads(tag_weights_json) if tag_weights_json else {}
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        interests = json.loads(interests_json) if interests_json else []

    if not prose_profile and not tag_weights and not interests:
        return COLD_START_SYSTEM_PROMPT

    parts = [
        "You are a relevance scoring assistant for a personal news aggregator called Sift.",
        "",
        "## User Profile",
    ]

    if prose_profile:
        parts.append(prose_profile)
        parts.append("")

    if interests:
        parts.append(f"**Interests**: {', '.join(interests)}")
        parts.append("")

    if tag_weights:
        parts.append("**Topic weights** (higher = more relevant):")
        sorted_tags = sorted(tag_weights.items(), key=lambda x: x[1], reverse=True)[:20]
        for tag, weight in sorted_tags:
            parts.append(f"- {tag}: {weight:.1f}")
        parts.append("")

    parts.append(
        """\
## Instructions

Score each article based on how relevant it is to this user's interests and \
preferences. Consider both the topic match and content quality.

For each article, provide:
- relevance_score: float 0-10 (10 = extremely relevant)
- summary: 1-2 sentence summary of the article
- explanation: brief reason for the score referencing the user's profile
- tags: 2-5 lowercase topic tags

Return a JSON array with one result per article, in the same order as presented."""
    )

    return "\n".join(parts)


def build_batch_prompt(articles: list[ArticlePromptData]) -> str:
    """Format a batch of articles into a single user message for scoring."""
    parts: list[str] = []
    for i, article in enumerate(articles, 1):
        content = article.content or ""
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "..."

        section = [f"## Article {i}", f"**Title**: {article.title}"]
        section.append(f"**Source**: {article.source_name}")
        if article.author:
            section.append(f"**Author**: {article.author}")
        if article.published_at:
            section.append(f"**Published**: {article.published_at}")
        section.append(f"**URL**: {article.url}")
        section.append("")
        section.append(content if content else "(no content available)")

        parts.append("\n".join(section))

    return "\n\n".join(parts)
