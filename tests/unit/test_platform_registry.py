"""Tests for the platform source registry."""

from backend.sources import get_all_source_types, get_platform_source_types
from backend.sources.base import get_source_class


def test_hackernews_is_registered_and_platform() -> None:
    cls = get_source_class("hackernews")
    assert cls is not None
    assert cls.is_platform is True


def test_rss_is_not_platform() -> None:
    cls = get_source_class("rss")
    assert cls is not None
    assert cls.is_platform is False


def test_webpage_is_not_platform() -> None:
    cls = get_source_class("webpage")
    assert cls is not None
    assert cls.is_platform is False


def test_get_platform_source_types_includes_hackernews() -> None:
    platforms = get_platform_source_types()
    source_types = [cls.source_type for cls in platforms]
    assert "hackernews" in source_types
    assert "rss" not in source_types
    assert "webpage" not in source_types


def test_hackernews_in_all_source_types() -> None:
    all_types = get_all_source_types()
    assert "hackernews" in all_types
