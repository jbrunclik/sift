# Import all source modules to trigger @register_source decorators
from backend.sources import rss as _rss  # noqa: F401
from backend.sources import webpage as _webpage  # noqa: F401
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
