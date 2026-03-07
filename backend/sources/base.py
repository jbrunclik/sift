import json
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from backend.models import RawArticle


class SourceConfig:
    """Configuration for a source instance, parsed from config_json."""

    def __init__(self, config_json: str = "{}") -> None:
        self.data: dict[str, Any] = json.loads(config_json)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def has_auth(self) -> bool:
        """Check if this source has authentication configured."""
        return bool(self.data.get("auth_cookie") or self.data.get("auth_headers"))

    def get_auth_headers(self) -> dict[str, str]:
        """Return HTTP headers for authenticated requests."""
        headers: dict[str, str] = {}
        cookie = self.data.get("auth_cookie")
        if cookie:
            headers["Cookie"] = str(cookie)
        extra = self.data.get("auth_headers")
        if isinstance(extra, dict):
            for k, v in extra.items():
                headers[str(k)] = str(v)
        return headers


class BaseSource(ABC):
    """Abstract base class for all source plugins."""

    source_type: str = ""
    display_name: str = ""
    requires_playwright: bool = False

    # Platform sources (HN, YouTube, Reddit) are singletons with discoverable UI
    is_platform: bool = False
    platform_description: str = ""
    config_fields: ClassVar[list[dict[str, object]]] = []
    auth_type: str | None = None  # None | "api_key" | "oauth" — for future use

    def __init__(
        self,
        config: SourceConfig,
        http_client: httpx.AsyncClient,
        playwright_context: Any | None = None,
        source_id: int | None = None,
    ) -> None:
        self.config = config
        self.http: httpx.AsyncClient = http_client
        self.playwright_context = playwright_context
        self.source_id = source_id

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from this source. Returns raw article data."""
        ...


# Source registry
_source_registry: dict[str, type[BaseSource]] = {}


def register_source(cls: type[BaseSource]) -> type[BaseSource]:
    """Decorator to register a source plugin class."""
    if cls.source_type:
        _source_registry[cls.source_type] = cls
    return cls


def get_source_class(source_type: str) -> type[BaseSource] | None:
    """Look up a registered source class by type string."""
    return _source_registry.get(source_type)


def get_all_source_types() -> list[str]:
    """Return all registered source type strings."""
    return list(_source_registry.keys())


def get_platform_source_types() -> list[type[BaseSource]]:
    """Return all registered platform source classes."""
    return [cls for cls in _source_registry.values() if cls.is_platform]
