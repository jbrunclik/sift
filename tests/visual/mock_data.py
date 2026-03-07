"""Mock API data for visual tests.

Provides deterministic, synthetic data matching the TypeScript interfaces
in frontend/src/types.ts.  Used by Playwright route interception so visual
tests never touch the real backend database.
"""

from __future__ import annotations

import copy
import json
import re
from urllib.parse import urlparse

from playwright.async_api import Page, Route

# ── Static mock data ──────────────────────────────────────────

ARTICLES: list[dict] = [
    {
        "id": 1,
        "source_id": 1,
        "external_id": "ext-001",
        "url": "https://blog.example.com/distributed-consensus",
        "url_normalized": "blog.example.com/distributed-consensus",
        "title": "Understanding Distributed Consensus Algorithms",
        "author": "Alice Chen",
        "content_snippet": "A deep dive into Raft, Paxos, and modern consensus protocols for distributed systems.",
        "content_full": None,
        "published_at": "2026-03-01T10:00:00Z",
        "fetched_at": "2026-03-01T12:00:00Z",
        "relevance_score": 8.5,
        "score_explanation": "Highly relevant to distributed systems interests.",
        "summary": "Explores consensus algorithms including Raft and Paxos with practical implementation examples.",
        "scored_at": "2026-03-01T12:05:00Z",
        "language": "en",
        "image_url": None,
        "is_read": False,
        "is_hidden": False,
        "created_at": "2026-03-01T12:00:00Z",
        "source_name": "Tech Blog Digest",
        "source_slug": "tech-blog",
        "tags": ["distributed-systems", "rust"],
        "feedback": None,
    },
    {
        "id": 2,
        "source_id": 2,
        "external_id": "ext-002",
        "url": "https://ai-research.example.com/neural-arch-search",
        "url_normalized": "ai-research.example.com/neural-arch-search",
        "title": "Advances in Neural Architecture Search",
        "author": "Bob Martinez",
        "content_snippet": "Recent breakthroughs in automated neural network design using evolutionary strategies.",
        "content_full": None,
        "published_at": "2026-02-28T14:30:00Z",
        "fetched_at": "2026-02-28T16:00:00Z",
        "relevance_score": 6.2,
        "score_explanation": "Moderately relevant to machine learning interests.",
        "summary": "Reviews evolutionary strategies and differentiable approaches to neural architecture search.",
        "scored_at": "2026-02-28T16:10:00Z",
        "language": "en",
        "image_url": None,
        "is_read": True,
        "is_hidden": False,
        "created_at": "2026-02-28T16:00:00Z",
        "source_name": "AI Research News",
        "source_slug": "ai-research",
        "tags": ["machine-learning", "python"],
        "feedback": 1,
    },
    {
        "id": 3,
        "source_id": 1,
        "external_id": "ext-003",
        "url": "https://blog.example.com/kubernetes-operators",
        "url_normalized": "blog.example.com/kubernetes-operators",
        "title": "Getting Started with Kubernetes Operators",
        "author": "Carol Liu",
        "content_snippet": "Build custom Kubernetes operators to manage complex stateful applications.",
        "content_full": None,
        "published_at": "2026-02-27T09:00:00Z",
        "fetched_at": "2026-02-27T11:00:00Z",
        "relevance_score": 3.1,
        "score_explanation": "Low relevance, peripheral to core interests.",
        "summary": "Introduction to the Kubernetes Operator pattern with a hands-on Go example.",
        "scored_at": "2026-02-27T11:05:00Z",
        "language": "en",
        "image_url": None,
        "is_read": False,
        "is_hidden": False,
        "created_at": "2026-02-27T11:00:00Z",
        "source_name": "Tech Blog Digest",
        "source_slug": "tech-blog",
        "tags": ["kubernetes", "open-source"],
        "feedback": -1,
    },
    {
        "id": 4,
        "source_id": 3,
        "external_id": "ext-004",
        "url": "https://startup.example.com/wasm-beyond-browser",
        "url_normalized": "startup.example.com/wasm-beyond-browser",
        "title": "WebAssembly Beyond the Browser: A New Era",
        "author": "Dan Park",
        "content_snippet": "How WASI and component model are reshaping server-side and edge computing.",
        "content_full": None,
        "published_at": "2026-02-26T16:00:00Z",
        "fetched_at": "2026-02-26T18:00:00Z",
        "relevance_score": 7.8,
        "score_explanation": "Strong match for web-assembly and systems programming interests.",
        "summary": "Covers WASI, the component model, and real-world WASM use-cases outside the browser.",
        "scored_at": "2026-02-26T18:10:00Z",
        "language": "en",
        "image_url": "https://startup.example.com/images/wasm-hero.jpg",
        "is_read": False,
        "is_hidden": False,
        "created_at": "2026-02-26T18:00:00Z",
        "source_name": "Startup Weekly",
        "source_slug": "startup-weekly",
        "tags": ["machine-learning", "web-assembly"],
        "feedback": None,
    },
    {
        "id": 5,
        "source_id": 2,
        "external_id": "ext-005",
        "url": "https://ai-research.example.com/quantum-computing-future",
        "url_normalized": "ai-research.example.com/quantum-computing-future",
        "title": "The Future of Quantum Computing",
        "author": "Eve Nakamura",
        "content_snippet": "What recent quantum supremacy claims mean for practical computing applications.",
        "content_full": None,
        "published_at": "2026-02-25T11:00:00Z",
        "fetched_at": "2026-02-25T13:00:00Z",
        "relevance_score": None,
        "score_explanation": None,
        "summary": None,
        "scored_at": None,
        "language": "en",
        "image_url": None,
        "is_read": False,
        "is_hidden": False,
        "created_at": "2026-02-25T13:00:00Z",
        "source_name": "AI Research News",
        "source_slug": "ai-research",
        "tags": [],
        "feedback": None,
    },
    {
        "id": 6,
        "source_id": 1,
        "external_id": "ext-006",
        "url": "https://blog.example.com/python-type-hints",
        "url_normalized": "blog.example.com/python-type-hints",
        "title": "Python Type Hints Best Practices",
        "author": "Frank Gomez",
        "content_snippet": "Practical patterns for using type hints effectively in large Python codebases.",
        "content_full": None,
        "published_at": "2026-02-24T08:00:00Z",
        "fetched_at": "2026-02-24T10:00:00Z",
        "relevance_score": 5.0,
        "score_explanation": "Moderate relevance.",
        "summary": "Guide to Python type annotations with mypy and pyright examples.",
        "scored_at": "2026-02-24T10:05:00Z",
        "language": "en",
        "image_url": None,
        "is_read": False,
        "is_hidden": True,
        "created_at": "2026-02-24T10:00:00Z",
        "source_name": "Tech Blog Digest",
        "source_slug": "tech-blog",
        "tags": ["python"],
        "feedback": None,
    },
]

SOURCES: list[dict] = [
    {
        "id": 1,
        "name": "Tech Blog Digest",
        "slug": "tech-blog",
        "source_type": "rss",
        "config_json": json.dumps({"feed_url": "https://blog.example.com/feed.xml"}),
        "enabled": True,
        "fetch_interval_minutes": 60,
        "last_fetched_at": "2026-03-02T08:00:00Z",
        "created_at": "2026-01-15T10:00:00Z",
        "updated_at": "2026-03-02T08:00:00Z",
        "category": "Technology",
        "starred": False,
    },
    {
        "id": 2,
        "name": "AI Research News",
        "slug": "ai-research",
        "source_type": "webpage",
        "config_json": json.dumps({
            "page_url": "https://ai-research.example.com",
            "extraction_rules": {
                "item_selector": "article.post",
                "title": {"selector": "h2.headline", "attribute": None},
                "url": {"selector": "a.read-more", "attribute": "href"},
                "description": {"selector": "div.summary", "attribute": None},
            },
            "_rules_learned_at": "2026-02-20T10:00:00Z",
            "auth_cookie": "",
        }),
        "enabled": True,
        "fetch_interval_minutes": 120,
        "last_fetched_at": "2026-03-02T07:30:00Z",
        "created_at": "2026-01-20T14:00:00Z",
        "updated_at": "2026-03-02T07:30:00Z",
        "category": "AI",
        "starred": False,
    },
    {
        "id": 3,
        "name": "Startup Weekly",
        "slug": "startup-weekly",
        "source_type": "rss",
        "config_json": json.dumps({"feed_url": "https://startup.example.com/rss"}),
        "enabled": True,
        "fetch_interval_minutes": 180,
        "last_fetched_at": "2026-03-01T20:00:00Z",
        "created_at": "2026-02-01T09:00:00Z",
        "updated_at": "2026-03-01T20:00:00Z",
        "category": "Business",
        "starred": True,
    },
]

PREFERENCES: dict = {
    "prose_profile": "Senior software engineer interested in distributed systems, machine learning, and open source.",
    "interests": ["distributed systems", "machine learning", "rust", "open source"],
    "tag_weights": {"distributed-systems": 1.5, "machine-learning": 1.3},
    "profile_version": 1,
    "summary_language": "en",
}

PREFERENCES_COLD_START: dict = {
    "prose_profile": "",
    "interests": [],
    "tag_weights": {},
    "profile_version": 0,
    "summary_language": "en",
}

TAG_WEIGHTS: list[dict] = [
    {"name": "distributed-systems", "weight": 1.5},
    {"name": "machine-learning", "weight": 1.3},
    {"name": "kubernetes", "weight": 1.1},
    {"name": "python", "weight": 1.0},
    {"name": "open-source", "weight": 0.9},
    {"name": "rust", "weight": 0.8},
    {"name": "web-assembly", "weight": 0.7},
]

VOCABULARY: list[dict] = [
    {"id": 1, "name": "distributed-systems", "article_count": 12},
    {"id": 2, "name": "machine-learning", "article_count": 8},
    {"id": 3, "name": "rust", "article_count": 5},
    {"id": 4, "name": "kubernetes", "article_count": 7},
    {"id": 5, "name": "open-source", "article_count": 3},
]

VOCABULARY_CANDIDATES: list[dict] = [
    {"id": 101, "name": "web-assembly", "occurrences": 4},
    {"id": 102, "name": "edge-computing", "occurrences": 3},
]

TAG_QUALITY: list[dict] = [
    {
        "tag_id": 1,
        "name": "distributed-systems",
        "positive_votes": 8,
        "negative_votes": 4,
        "total_votes": 12,
        "disagreement_ratio": 0.33,
    },
    {
        "tag_id": 6,
        "name": "python",
        "positive_votes": 3,
        "negative_votes": 5,
        "total_votes": 8,
        "disagreement_ratio": 0.625,
    },
]

STATS: dict = {
    "total_articles": 156,
    "scored_articles": 142,
    "average_score": 6.3,
    "total_feedback": 45,
    "positive_feedback": 30,
    "negative_feedback": 15,
    "sources": [
        {"name": "Tech Blog Digest", "slug": "tech-blog", "article_count": 78, "avg_score": 6.5},
        {"name": "AI Research News", "slug": "ai-research", "article_count": 45, "avg_score": 7.1},
        {"name": "Startup Weekly", "slug": "startup-weekly", "article_count": 33, "avg_score": 5.8},
    ],
    "score_distribution": [2, 5, 8, 12, 18, 25, 30, 22, 14, 6],
    "inbox_count": 23,
    "scheduler_jobs": [
        {
            "job_name": "fetch",
            "last_run_at": "2026-03-02T08:00:00Z",
            "last_status": "ok",
            "last_details": "Fetched 12 new articles",
            "last_error": None,
            "interval_minutes": 60,
            "next_run_at": "2026-03-02T09:00:00Z",
        },
        {
            "job_name": "score",
            "last_run_at": "2026-03-02T08:05:00Z",
            "last_status": "ok",
            "last_details": "Scored 8 articles",
            "last_error": None,
            "interval_minutes": 30,
            "next_run_at": "2026-03-02T08:35:00Z",
        },
        {
            "job_name": "cleanup",
            "last_run_at": "2026-03-02T06:00:00Z",
            "last_status": "ok",
            "last_details": "Removed 3 old articles",
            "last_error": None,
            "interval_minutes": 1440,
            "next_run_at": "2026-03-03T06:00:00Z",
        },
    ],
}

COSTS: list[dict] = [
    {
        "month": "2026-03",
        "model": "claude-sonnet-4-20250514",
        "tokens_in": 125000,
        "tokens_out": 45000,
        "cost_usd": 0.85,
        "batches": 12,
    },
    {
        "month": "2026-02",
        "model": "claude-sonnet-4-20250514",
        "tokens_in": 980000,
        "tokens_out": 320000,
        "cost_usd": 6.20,
        "batches": 89,
    },
]

ISSUES: dict = {
    "fetch_errors": 2,
    "scoring_errors": 1,
    "unscored": 14,
    "auth_truncations": 1,
}

ISSUE_DETAILS: dict = {
    "fetch_errors": 2,
    "scoring_failures": 1,
    "scoring_retryable": 0,
    "unscored": 14,
    "auth_truncations": 1,
}

SCORING_FAILURES: list[dict] = [
    {
        "id": 99,
        "title": "Understanding WebGPU Compute Shaders",
        "url": "https://blog.example.com/webgpu-compute",
        "source_name": "Tech Blog Digest",
        "score_attempts": 3,
        "scored_at": None,
        "error": "Rate limit exceeded",
    },
]

AUTH_ISSUES: list[dict] = [
    {
        "source_id": 2,
        "source_name": "AI Research News",
        "truncated_count": 3,
        "latest_article_title": "Advances in Neural Architecture Search",
    },
]

PLATFORMS: list[dict] = [
    {
        "source_type": "hackernews",
        "display_name": "Hacker News",
        "description": "Top stories, Show HN, Ask HN from Hacker News",
        "icon": "hackernews",
        "config_fields": [
            {
                "key": "endpoint", "label": "Story type",
                "type": "select",
                "options": ["top", "new", "best", "ask", "show"],
                "default": "top",
            },
            {
                "key": "limit", "label": "Max stories",
                "type": "number", "min": 5, "max": 100, "default": 30,
            },
            {
                "key": "min_score", "label": "Min score",
                "type": "number", "min": 0, "max": 1000, "default": 0,
            },
        ],
        "auth_type": None,
        "source": {
            "id": 10,
            "name": "Hacker News",
            "slug": "hackernews",
            "source_type": "hackernews",
            "config_json": json.dumps({"endpoint": "top", "limit": 30, "min_score": 0}),
            "enabled": True,
            "fetch_interval_minutes": 30,
            "last_fetched_at": "2026-03-02T09:00:00Z",
            "created_at": "2026-02-15T10:00:00Z",
            "updated_at": "2026-03-02T09:00:00Z",
            "category": "",
            "starred": False,
        },
    },
]

HEALTH: dict = {
    "status": "ok",
    "database": "connected",
    "sources_count": 3,
    "articles_count": 156,
    "unscored_count": 14,
}


# ── MockState ─────────────────────────────────────────────────


class MockState:
    """Mutable deep-copy of mock data so stateful tests work correctly."""

    def __init__(self, *, cold_start: bool = False) -> None:
        self.articles: list[dict] = copy.deepcopy(ARTICLES)
        self.sources: list[dict] = copy.deepcopy(SOURCES)
        self.preferences: dict = copy.deepcopy(
            PREFERENCES_COLD_START if cold_start else PREFERENCES
        )
        self.tag_weights: list[dict] = copy.deepcopy(TAG_WEIGHTS)
        self.vocabulary: list[dict] = copy.deepcopy(VOCABULARY)
        self.vocabulary_candidates: list[dict] = copy.deepcopy(VOCABULARY_CANDIDATES)
        self.tag_quality: list[dict] = copy.deepcopy(TAG_QUALITY)
        self.stats: dict = copy.deepcopy(STATS)
        self._next_vocab_id: int = 200

    def get_articles(self) -> list[dict]:
        return [a for a in self.articles if not a["is_hidden"]]

    def handle_feedback(self, body: dict) -> dict:
        article_id = body.get("article_id")
        rating = body.get("rating", 0)
        for a in self.articles:
            if a["id"] == article_id:
                a["feedback"] = rating
                break
        return {
            "id": 1,
            "article_id": article_id,
            "rating": rating,
            "created_at": "2026-03-02T12:00:00Z",
        }

    def mark_read(self, article_id: int) -> None:
        for a in self.articles:
            if a["id"] == article_id:
                a["is_read"] = True
                break

    def mark_unread(self, article_id: int) -> None:
        for a in self.articles:
            if a["id"] == article_id:
                a["is_read"] = False
                break

    def hide_article(self, article_id: int) -> None:
        for a in self.articles:
            if a["id"] == article_id:
                a["is_hidden"] = True
                break

    def add_vocabulary(self, body: dict) -> dict:
        name = body.get("name", "unknown")
        tag = {"id": self._next_vocab_id, "name": name, "article_count": 0}
        self._next_vocab_id += 1
        self.vocabulary.append(tag)
        return tag

    def remove_vocabulary(self, tag_id: int) -> None:
        self.vocabulary = [v for v in self.vocabulary if v["id"] != tag_id]


# ── Route installer ───────────────────────────────────────────


async def install_mock_routes(
    page: Page, *, cold_start: bool = False
) -> MockState:
    """Intercept all /api/ requests and serve mock data.

    Returns the MockState instance so tests can inspect or mutate it.
    """
    state = MockState(cold_start=cold_start)

    async def handler(route: Route) -> None:
        url = route.request.url
        method = route.request.method
        path = urlparse(url).path

        body: str | None = None

        # ── GET ───────────────────────────────────────────
        if method == "GET":
            if path == "/api/articles":
                body = json.dumps(state.get_articles())
            elif re.match(r"/api/articles/\d+$", path):
                aid = int(path.rsplit("/", 1)[-1])
                article = next((a for a in state.articles if a["id"] == aid), None)
                body = json.dumps(article or {})
            elif path == "/api/sources/platforms":
                body = json.dumps(PLATFORMS)
            elif path == "/api/sources":
                body = json.dumps(state.sources)
            elif path == "/api/preferences":
                body = json.dumps(state.preferences)
            elif path == "/api/preferences/tags":
                body = json.dumps(state.tag_weights)
            elif path == "/api/preferences/vocabulary/candidates":
                body = json.dumps(state.vocabulary_candidates)
            elif path == "/api/preferences/vocabulary/quality":
                body = json.dumps(state.tag_quality)
            elif path == "/api/preferences/vocabulary":
                body = json.dumps(state.vocabulary)
            elif path == "/api/stats/costs":
                body = json.dumps(COSTS)
            elif path == "/api/stats/issues":
                body = json.dumps(ISSUES)
            elif path == "/api/stats/issue-details":
                body = json.dumps(ISSUE_DETAILS)
            elif path == "/api/stats/scoring-failures":
                body = json.dumps(SCORING_FAILURES)
            elif path == "/api/stats/auth-issues":
                body = json.dumps(AUTH_ISSUES)
            elif path == "/api/stats":
                body = json.dumps(state.stats)
            elif path == "/api/health":
                body = json.dumps(HEALTH)
            else:
                body = "[]"

        # ── POST ──────────────────────────────────────────
        elif method == "POST":
            post_data = route.request.post_data or "{}"
            m = re.match(r"/api/articles/(\d+)/read$", path)
            if m:
                state.mark_read(int(m.group(1)))
                body = json.dumps({"status": "ok"})
            elif (m := re.match(r"/api/articles/(\d+)/unread$", path)):
                state.mark_unread(int(m.group(1)))
                body = json.dumps({"status": "ok"})
            elif (m := re.match(r"/api/articles/(\d+)/hide$", path)):
                state.hide_article(int(m.group(1)))
                body = json.dumps({"status": "ok"})
            elif path == "/api/feedback":
                result = state.handle_feedback(json.loads(post_data))
                body = json.dumps(result)
            elif path == "/api/preferences/vocabulary/merge":
                body = json.dumps({"status": "ok"})
            elif re.match(r"/api/preferences/vocabulary/candidates/\d+/approve$", path):
                body = json.dumps({"status": "ok"})
            elif path == "/api/preferences/vocabulary":
                tag = state.add_vocabulary(json.loads(post_data))
                body = json.dumps(tag)
            elif path == "/api/sources":
                body = json.dumps(state.sources[0])  # echo back first source as stub
            elif re.match(r"/api/sources/\d+/fetch$", path):
                body = json.dumps({
                    "id": 1, "source_id": 1,
                    "started_at": "2026-03-02T12:00:00Z",
                    "finished_at": "2026-03-02T12:00:05Z",
                    "status": "ok", "items_found": 5, "items_new": 2,
                    "error_message": None, "duration_ms": 5000,
                })
            elif re.match(r"/api/sources/\d+/test-auth$", path):
                body = json.dumps({
                    "status": "ok",
                    "content_length": 4500,
                    "message": "Content fetched successfully",
                })
            elif re.match(r"/api/jobs/", path):
                body = json.dumps({"status": "ok", "message": "Job triggered"})
            elif path == "/api/onboarding":
                body = json.dumps({"profile_version": 1, "tags_seeded": 5})
            else:
                body = json.dumps({"status": "ok"})

        # ── PUT ───────────────────────────────────────────
        elif method == "PUT":
            if path == "/api/preferences":
                post_data = route.request.post_data or "{}"
                state.preferences.update(json.loads(post_data))
                body = json.dumps(state.preferences)
            else:
                body = json.dumps({"status": "ok"})

        # ── PATCH ─────────────────────────────────────────
        elif method == "PATCH":
            m = re.match(r"/api/sources/(\d+)$", path)
            if m:
                sid = int(m.group(1))
                post_data = route.request.post_data or "{}"
                updates = json.loads(post_data)
                for s in state.sources:
                    if s["id"] == sid:
                        s.update(updates)
                        body = json.dumps(s)
                        break
                else:
                    body = json.dumps({"status": "ok"})
            else:
                body = json.dumps({"status": "ok"})

        # ── DELETE ────────────────────────────────────────
        elif method == "DELETE":
            if re.match(r"/api/preferences/vocabulary/candidates/\d+$", path):
                body = json.dumps({"status": "ok"})
            elif (m := re.match(r"/api/preferences/vocabulary/(\d+)$", path)):
                state.remove_vocabulary(int(m.group(1)))
                body = json.dumps({"status": "ok"})
            elif re.match(r"/api/preferences/tags/", path):
                body = json.dumps({"status": "ok"})
            elif re.match(r"/api/sources/\d+$", path):
                body = json.dumps({"status": "ok"})
            else:
                body = json.dumps({"status": "ok"})

        # ── Fallback ──────────────────────────────────────
        else:
            body = json.dumps({"status": "ok"})

        await route.fulfill(
            status=200,
            content_type="application/json",
            body=body,
        )

    await page.route("**/api/**", handler)
    return state
