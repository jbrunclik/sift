from backend.models import ArticleListParams, FeedbackCreate, RawArticle, SourceCreate


def test_raw_article_defaults() -> None:
    a = RawArticle(url="https://example.com", title="Test")
    assert a.language == "en"
    assert a.extra == {}
    assert a.author is None


def test_source_create() -> None:
    s = SourceCreate(name="Test", slug="test", source_type="rss")
    assert s.config_json == "{}"
    assert s.enabled is True
    assert s.fetch_interval_minutes == 30


def test_feedback_create_validation() -> None:
    f = FeedbackCreate(article_id=1, rating=1)
    assert f.rating == 1

    f = FeedbackCreate(article_id=1, rating=-1)
    assert f.rating == -1


def test_article_list_params_defaults() -> None:
    p = ArticleListParams()
    assert p.limit == 50
    assert p.offset == 0
    assert p.min_score is None
    assert p.unread is False
