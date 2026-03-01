import logging
import re
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


def _split_sql(sql: str) -> list[str]:
    """Split a SQL script into individual statements.

    Handles semicolons inside string literals, CREATE TRIGGER BEGIN...END blocks,
    and skips comment-only/blank lines.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    quote_char = ""
    in_trigger = False

    for char in sql:
        if in_string:
            current.append(char)
            if char == quote_char:
                in_string = False
        elif char in ("'", '"'):
            in_string = True
            quote_char = char
            current.append(char)
        elif char == ";":
            current.append(char)
            text_so_far = "".join(current)
            # Check if this END; closes a trigger block
            if in_trigger and re.search(r"\bEND\s*;$", text_so_far, re.IGNORECASE):
                in_trigger = False
                stmt = text_so_far.strip()
                stmt = re.sub(r"--[^\n]*", "", stmt).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            elif not in_trigger:
                stmt = text_so_far.strip()
                stmt = re.sub(r"--[^\n]*", "", stmt).strip()
                if stmt:
                    # Check if we just started a trigger (has BEGIN but no END yet)
                    if re.search(r"\bBEGIN\b", stmt, re.IGNORECASE) and re.search(
                        r"CREATE\s+TRIGGER\b", stmt, re.IGNORECASE
                    ):
                        in_trigger = True
                    else:
                        # Remove trailing semicolon for db.execute()
                        if stmt.endswith(";"):
                            stmt = stmt[:-1].strip()
                        if stmt:
                            statements.append(stmt)
                        current = []
                else:
                    current = []
        else:
            current.append(char)

    # Handle final statement without trailing semicolon
    stmt = "".join(current).strip()
    stmt = re.sub(r"--[^\n]*", "", stmt).strip()
    if stmt:
        statements.append(stmt)

    return statements


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Run all pending SQL migrations in order.

    Executes each statement individually (not via executescript) so errors
    propagate correctly through aiosqlite's threading layer.
    """
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
            for statement in _split_sql(sql):
                await db.execute(statement)
            await db.commit()
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
