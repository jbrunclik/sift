from backend.api.routes_sources import _normalize_url


def test_normalize_strips_utm_params() -> None:
    url = "https://example.com/article?utm_source=twitter&utm_medium=social&id=42"
    result = _normalize_url(url)
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "id=42" in result


def test_normalize_strips_www() -> None:
    url = "https://www.example.com/article"
    result = _normalize_url(url)
    assert "www." not in result
    assert "example.com" in result


def test_normalize_strips_trailing_slash() -> None:
    url = "https://example.com/article/"
    result = _normalize_url(url)
    assert result.endswith("/article")


def test_normalize_forces_https() -> None:
    url = "http://example.com/article"
    result = _normalize_url(url)
    assert result.startswith("https://")


def test_normalize_consistent() -> None:
    urls = [
        "https://www.example.com/article/?utm_source=rss",
        "http://example.com/article",
        "https://example.com/article/",
    ]
    normalized = {_normalize_url(u) for u in urls}
    assert len(normalized) == 1
