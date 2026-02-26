# ADR-004: SQLite with WAL mode and FTS5

## Status
Accepted

## Context
Need a database for articles, sources, feedback, and user profile. Options range from PostgreSQL to embedded databases.

## Decision
Use SQLite with WAL mode (concurrent reads) and FTS5 (full-text search). Raw SQL via aiosqlite, no ORM. Migrations are numbered `.sql` files run in order.

## Consequences
- Zero infrastructure — just a file on disk
- WAL allows the web server to read while the scheduler writes
- FTS5 gives fast full-text search without an external service
- No ORM means writing SQL directly, but keeps things simple and explicit
- Backup is just copying a file (via systemd timer, planned)
