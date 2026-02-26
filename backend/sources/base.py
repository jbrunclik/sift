import json
from abc import ABC, abstractmethod
from typing import Any

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


class BaseSource(ABC):
    """Abstract base class for all source plugins."""

    source_type: str = ""
    display_name: str = ""
    requires_playwright: bool = False

    def __init__(
        self,
        config: SourceConfig,
        http_client: httpx.AsyncClient,
        playwright_context: Any | None = None,
    ) -> None:
        self.config = config
        self.http: httpx.AsyncClient = http_client
        self.playwright_context = playwright_context

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
