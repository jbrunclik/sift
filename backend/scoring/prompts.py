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
- summary: 2-3 sentence summary capturing the key points of the article
- explanation: brief reason for the score
- tags: 2-5 lowercase English topic tags (always English, regardless of article or summary language)

Return a JSON array with one result per article, in the same order as presented."""

MAX_CONTENT_CHARS = 4000
HEAD_CHARS = 3000
TAIL_CHARS = 1000


LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "cs": "Czech",
}


def _build_vocabulary_instruction(approved_tags: list[str]) -> str:
    """Build the tag vocabulary constraint section for the prompt."""
    if not approved_tags:
        return ""
    tag_list = ", ".join(approved_tags)
    return (
        f"## Tag Vocabulary\n"
        f"Assign tags ONLY from this list: {tag_list}\n\n"
        f"If an article covers a topic not in this vocabulary, you may suggest ONE new tag "
        f'by prefixing it with "+": e.g. "+quantum-computing". '
        f"New tags must be in English and be durable topics "
        f"(not event names, years, or ephemeral terms)."
    )


def build_system_prompt(
    prose_profile: str,
    tag_weights_json: str,
    interests_json: str,
    summary_language: str = "en",
    approved_tags: list[str] | None = None,
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

    language_name = LANGUAGE_NAMES.get(summary_language, summary_language)
    language_instruction = (
        f"Write all summaries in {language_name}." if summary_language != "en" else ""
    )
    vocabulary_instruction = _build_vocabulary_instruction(approved_tags or [])

    if not prose_profile and not tag_weights and not interests:
        prompt = COLD_START_SYSTEM_PROMPT
        extra: list[str] = []
        if language_instruction:
            extra.append(language_instruction)
        if vocabulary_instruction:
            extra.append(vocabulary_instruction)
        if extra:
            prompt += "\n\n" + "\n\n".join(extra)
        return prompt

    parts = [
        "You are a relevance scoring assistant for a personal news aggregator called Sift.",
        "",
    ]

    # Tag vocabulary comes first (based on content, before scoring preferences)
    if vocabulary_instruction:
        parts.append(vocabulary_instruction)
        parts.append("")

    parts.append("## User Profile")

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

    instructions = """\
## Instructions

For each article:
1. Identify 2-5 topic tags based on article content (use vocabulary above)
2. Score relevance (0-10) considering user preferences above

For each article, provide:
- relevance_score: float 0-10 (10 = extremely relevant)
- summary: 2-3 sentence summary capturing the key points of the article
- explanation: brief reason for the score referencing the user's profile
- tags: 2-5 lowercase English topic tags \
(always English, regardless of article or summary language)"""
    if language_instruction:
        instructions += "\n" + language_instruction
    instructions += (
        "\n\nReturn a JSON array with one result per article, in the same order as presented."
    )
    parts.append(instructions)

    return "\n".join(parts)


def build_batch_prompt(articles: list[ArticlePromptData]) -> str:
    """Format a batch of articles into a single user message for scoring."""
    parts: list[str] = []
    for i, article in enumerate(articles, 1):
        content = article.content or ""
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:HEAD_CHARS] + "\n\n[...]\n\n" + content[-TAIL_CHARS:]

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
