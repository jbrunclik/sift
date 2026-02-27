import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

FUZZY_TITLE_THRESHOLD = 0.80
FUZZY_TIME_WINDOW = timedelta(hours=48)


@dataclass
class ArticleForScoring:
    id: int
    source_id: int
    url_normalized: str
    title: str
    author: str | None
    content_snippet: str | None
    content_full: str | None
    published_at: str | None
    source_name: str


@dataclass
class DeduplicatedGroup:
    primary: ArticleForScoring
    duplicates: list[ArticleForScoring] = field(default_factory=list)

    @property
    def all_ids(self) -> list[int]:
        return [self.primary.id] + [d.id for d in self.duplicates]


def find_duplicate_groups(articles: list[ArticleForScoring]) -> list[DeduplicatedGroup]:
    """Group articles by deduplication, returning one group per unique article.

    Two-pass approach:
    1. Exact match on url_normalized
    2. Fuzzy title match (threshold 0.80, within 48h window)
    """
    if not articles:
        return []

    # Pass 1: group by exact URL
    url_groups: dict[str, list[ArticleForScoring]] = {}
    for article in articles:
        url_groups.setdefault(article.url_normalized, []).append(article)

    groups: list[DeduplicatedGroup] = []
    for url_articles in url_groups.values():
        primary = _pick_primary(url_articles)
        duplicates = [a for a in url_articles if a.id != primary.id]
        groups.append(DeduplicatedGroup(primary=primary, duplicates=duplicates))

    # Pass 2: fuzzy title match across groups
    merged = _merge_by_fuzzy_title(groups)
    return merged


def _pick_primary(articles: list[ArticleForScoring]) -> ArticleForScoring:
    """Pick the article with the most content as the primary."""
    return max(articles, key=lambda a: len(a.content_full or a.content_snippet or ""))


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison."""
    return re.sub(r"\s+", " ", title.lower().strip())


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _within_time_window(a: ArticleForScoring, b: ArticleForScoring) -> bool:
    """Check if two articles were published within the fuzzy time window."""
    dt_a = _parse_published_at(a.published_at)
    dt_b = _parse_published_at(b.published_at)
    if dt_a is None or dt_b is None:
        # If either has no date, allow the match (can't disprove proximity)
        return True
    return abs(dt_a - dt_b) <= FUZZY_TIME_WINDOW


def _merge_by_fuzzy_title(groups: list[DeduplicatedGroup]) -> list[DeduplicatedGroup]:
    """Merge groups whose primary articles have similar titles within time window."""
    if len(groups) <= 1:
        return groups

    merged: list[DeduplicatedGroup] = []
    consumed: set[int] = set()

    for i, group_a in enumerate(groups):
        if i in consumed:
            continue

        title_a = _normalize_title(group_a.primary.title)

        for j in range(i + 1, len(groups)):
            if j in consumed:
                continue

            group_b = groups[j]
            title_b = _normalize_title(group_b.primary.title)

            if SequenceMatcher(
                None, title_a, title_b
            ).ratio() >= FUZZY_TITLE_THRESHOLD and _within_time_window(
                group_a.primary, group_b.primary
            ):
                # Merge group_b into group_a
                all_articles = [
                    group_a.primary,
                    *group_a.duplicates,
                    group_b.primary,
                    *group_b.duplicates,
                ]
                primary = _pick_primary(all_articles)
                duplicates = [a for a in all_articles if a.id != primary.id]
                group_a = DeduplicatedGroup(primary=primary, duplicates=duplicates)
                consumed.add(j)

        merged.append(group_a)

    return merged
