from backend.scoring.deduplicator import (
    ArticleForScoring,
    DeduplicatedGroup,
    find_duplicate_groups,
)


def _make_article(
    id: int = 1,
    source_id: int = 1,
    url_normalized: str = "https://example.com/article",
    title: str = "Test Article",
    content_full: str | None = "Some content here",
    content_snippet: str | None = None,
    published_at: str | None = "2024-01-15T12:00:00",
    source_name: str = "Test Source",
    author: str | None = None,
) -> ArticleForScoring:
    return ArticleForScoring(
        id=id,
        source_id=source_id,
        url_normalized=url_normalized,
        title=title,
        author=author,
        content_snippet=content_snippet,
        content_full=content_full,
        published_at=published_at,
        source_name=source_name,
    )


class TestFindDuplicateGroups:
    def test_empty_input(self) -> None:
        assert find_duplicate_groups([]) == []

    def test_single_article(self) -> None:
        articles = [_make_article(id=1)]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 1
        assert groups[0].primary.id == 1
        assert groups[0].duplicates == []

    def test_no_duplicates(self) -> None:
        articles = [
            _make_article(id=1, url_normalized="https://a.com/1", title="First Article"),
            _make_article(id=2, url_normalized="https://b.com/2", title="Second Article"),
            _make_article(id=3, url_normalized="https://c.com/3", title="Third Article"),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 3

    def test_url_exact_match_groups_together(self) -> None:
        articles = [
            _make_article(id=1, source_id=1, url_normalized="https://example.com/article"),
            _make_article(id=2, source_id=2, url_normalized="https://example.com/article"),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 1
        assert sorted(groups[0].all_ids) == [1, 2]

    def test_fuzzy_title_match_groups_together(self) -> None:
        articles = [
            _make_article(
                id=1,
                url_normalized="https://a.com/1",
                title="Python 3.14 Released with Major Performance Improvements",
                published_at="2024-01-15T12:00:00",
            ),
            _make_article(
                id=2,
                url_normalized="https://b.com/2",
                title="Python 3.14 Released With Major Performance Improvements",
                published_at="2024-01-15T14:00:00",
            ),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 1
        assert sorted(groups[0].all_ids) == [1, 2]

    def test_fuzzy_title_below_threshold_stays_separate(self) -> None:
        articles = [
            _make_article(
                id=1,
                url_normalized="https://a.com/1",
                title="Python 3.14 Released",
            ),
            _make_article(
                id=2,
                url_normalized="https://b.com/2",
                title="Rust 2.0 Announced with Breaking Changes",
            ),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 2

    def test_fuzzy_title_outside_time_window_stays_separate(self) -> None:
        articles = [
            _make_article(
                id=1,
                url_normalized="https://a.com/1",
                title="Weekly Tech Roundup",
                published_at="2024-01-01T12:00:00",
            ),
            _make_article(
                id=2,
                url_normalized="https://b.com/2",
                title="Weekly Tech Roundup",
                published_at="2024-01-10T12:00:00",  # 9 days apart
            ),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 2

    def test_primary_prefers_most_content(self) -> None:
        articles = [
            _make_article(
                id=1,
                url_normalized="https://example.com/article",
                content_full=None,
                content_snippet="Short",
            ),
            _make_article(
                id=2,
                url_normalized="https://example.com/article",
                content_full="This is a much longer article with full content",
                content_snippet=None,
            ),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 1
        assert groups[0].primary.id == 2

    def test_all_ids_property(self) -> None:
        group = DeduplicatedGroup(
            primary=_make_article(id=1),
            duplicates=[_make_article(id=2), _make_article(id=3)],
        )
        assert sorted(group.all_ids) == [1, 2, 3]

    def test_mixed_url_and_fuzzy_dedup(self) -> None:
        articles = [
            _make_article(
                id=1,
                source_id=1,
                url_normalized="https://a.com/story",
                title="Breaking: Major Security Vulnerability Found in OpenSSL",
            ),
            _make_article(
                id=2,
                source_id=2,
                url_normalized="https://a.com/story",  # same URL as id=1
                title="Breaking: Major Security Vulnerability Found in OpenSSL",
            ),
            _make_article(
                id=3,
                source_id=3,
                url_normalized="https://b.com/openssl-vuln",
                title="Breaking: Major Security Vulnerability Found In OpenSSL",  # fuzzy match
            ),
        ]
        groups = find_duplicate_groups(articles)
        assert len(groups) == 1
        assert sorted(groups[0].all_ids) == [1, 2, 3]
