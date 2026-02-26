import logging
from pathlib import Path

import aiosqlite

from backend.config import settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Override for testing: set to a temp file path
_db_path_override: str | None = None


def set_db_path(path: str | None) -> None:
    """Override the database path (used for testing)."""
    global _db_path_override
    _db_path_override = path


def _get_db_path() -> str:
    if _db_path_override is not None:
        return _db_path_override
    return settings.database_path


async def get_db() -> aiosqlite.Connection:
    """Create a new database connection with WAL mode and foreign keys."""
    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Run all pending SQL migrations in order."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS _migrations ("
        "  filename TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    await db.commit()

    applied_rows = await db.execute_fetchall("SELECT filename FROM _migrations")
    applied = {row[0] for row in applied_rows}

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for migration_file in migration_files:
        if migration_file.name not in applied:
            logger.info("Applying migration: %s", migration_file.name)
            sql = migration_file.read_text()
            await db.executescript(sql)
            await db.execute(
                "INSERT INTO _migrations (filename) VALUES (?)", (migration_file.name,)
            )
            await db.commit()
            logger.info("Applied migration: %s", migration_file.name)


async def init_db() -> aiosqlite.Connection:
    """Initialize the database: create it, run migrations, return connection."""
    db = await get_db()
    await run_migrations(db)
    return db


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        db = await init_db()
        await db.close()
        print("Migrations applied successfully.")

    asyncio.run(main())
