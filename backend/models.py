from datetime import datetime

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: int
    name: str
    slug: str
    source_type: str
    config_json: str = "{}"
    enabled: bool = True
    fetch_interval_minutes: int = 30
    last_fetched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SourceCreate(BaseModel):
    name: str
    slug: str
    source_type: str
    config_json: str = "{}"
    enabled: bool = True
    fetch_interval_minutes: int = 30


class Article(BaseModel):
    id: int
    source_id: int
    external_id: str | None = None
    url: str
    url_normalized: str
    title: str
    author: str | None = None
    content_snippet: str | None = None
    content_full: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    relevance_score: float | None = None
    score_explanation: str | None = None
    summary: str | None = None
    scored_at: datetime | None = None
    language: str = "en"
    image_url: str | None = None
    extra_json: str = "{}"
    is_read: bool = False
    is_hidden: bool = False
    created_at: datetime
    # Joined fields
    source_name: str | None = None
    source_slug: str | None = None
    tags: list[str] = Field(default_factory=list)
    feedback: int | None = None


class RawArticle(BaseModel):
    """Article data as returned by a source plugin before storage."""

    external_id: str | None = None
    url: str
    title: str
    author: str | None = None
    content_snippet: str | None = None
    content_full: str | None = None
    published_at: datetime | None = None
    language: str = "en"
    image_url: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class Feedback(BaseModel):
    id: int
    article_id: int
    rating: int
    created_at: datetime


class FeedbackCreate(BaseModel):
    article_id: int
    rating: int = Field(ge=-1, le=1)


class Tag(BaseModel):
    id: int
    name: str


class UserProfile(BaseModel):
    id: int = 1
    tag_weights_json: str = "{}"
    prose_profile: str = ""
    interests_json: str = "[]"
    profile_version: int = 0
    updated_at: datetime | None = None


class FetchLog(BaseModel):
    id: int
    source_id: int
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    items_found: int = 0
    items_new: int = 0
    error_message: str | None = None
    duration_ms: int | None = None


class ArticleListParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    min_score: float | None = None
    source_slug: str | None = None
    search: str | None = None
    show_all: bool = False
    unread: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "ok"
    sources_count: int = 0
    articles_count: int = 0
    unscored_count: int = 0


class StatsResponse(BaseModel):
    total_articles: int = 0
    scored_articles: int = 0
    average_score: float | None = None
    total_feedback: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    sources: list[dict[str, object]] = Field(default_factory=list)
