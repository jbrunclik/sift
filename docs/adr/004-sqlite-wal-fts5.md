# ADR-004: SQLite with WAL mode and FTS5

## Status
Accepted

## Context
Need a database for articles, sources, feedback, and user profile. Options range from PostgreSQL to embedded databases.

## Decision
Use SQLite with WAL mode (concurrent reads) and FTS5 (full-text search). Raw SQL via aiosqlite, no ORM. Migrations are numbered `.sql` files run in order.

## Concurrency guidelines
WAL mode allows concurrent readers with a single writer. Key rules learned in practice:
- **`busy_timeout=15000`** — writers wait up to 15s for the lock instead of failing immediately
- **Never VACUUM in-process** — VACUUM requires an exclusive lock that blocks all readers and writers. Run it via a systemd timer when the app is idle (nightly)
- **Batch writes in a single transaction** — opening N connections for N concurrent writes causes lock contention even with WAL. Collect results in memory, then write them all on one connection in one transaction
- **Retry on `database is locked`** — user-facing API endpoints retry with backoff (3 attempts) for transient lock contention from background jobs

## Consequences
- Zero infrastructure — just a file on disk
- WAL allows the web server to read while the scheduler writes
- FTS5 gives fast full-text search without an external service
- No ORM means writing SQL directly, but keeps things simple and explicit
- Backup is just copying a file (via systemd timer, planned)
