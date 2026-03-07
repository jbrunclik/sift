"""Local file cache for extraction results.

Prevents re-fetching from sources when DB writes fail. Results are
written to disk immediately after extraction and removed only after
a successful DB commit.
"""

import json
import logging
import time
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

CACHE_DIR = Path(settings.database_path).parent / "extraction_cache"


def _cache_path(article_id: int) -> Path:
    return CACHE_DIR / f"{article_id}.json"


def ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def read_cached(article_id: int) -> dict[str, object] | None:
    """Read a cached extraction result. Returns None if not cached."""
    path = _cache_path(article_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return dict(data)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt cache file for article %d, removing", article_id)
        path.unlink(missing_ok=True)
        return None


def write_cached(article_id: int, status: str, content: str | None) -> None:
    """Write an extraction result to the cache."""
    ensure_cache_dir()
    data = {
        "status": status,
        "content": content,
        "cached_at": time.time(),
    }
    try:
        _cache_path(article_id).write_text(json.dumps(data))
    except OSError:
        logger.warning("Failed to write cache for article %d", article_id)


def remove_cached(article_id: int) -> None:
    """Remove a cache file after successful DB commit."""
    _cache_path(article_id).unlink(missing_ok=True)


def cleanup_stale(max_age_seconds: int = 7 * 24 * 3600) -> int:
    """Remove cache files older than max_age_seconds. Returns count removed."""
    if not CACHE_DIR.exists():
        return 0
    now = time.time()
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            if now - path.stat().st_mtime > max_age_seconds:
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed
