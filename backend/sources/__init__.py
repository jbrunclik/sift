# Import all source modules to trigger @register_source decorators
from backend.sources import rss as _rss  # noqa: F401

# Add more sources here as they are implemented
from backend.sources.base import (
    BaseSource,
    SourceConfig,
    get_all_source_types,
    get_source_class,
    register_source,
)

__all__ = [
    "BaseSource",
    "SourceConfig",
    "get_all_source_types",
    "get_source_class",
    "register_source",
]
