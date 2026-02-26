# Sift — Agent Context

## What This Is
Sift is a personal news aggregator that fetches articles from 8+ sources, scores relevance with Gemini Flash, and surfaces a curated feed. Feedback loop learns preferences over time.

## Architecture
- **Backend**: Python 3.14, FastAPI, SQLite (WAL + FTS5), APScheduler
- **Frontend**: Vite + vanilla TypeScript, hash-based SPA router
- **Scoring**: Gemini 3.0 Flash via `google-genai`, structured JSON output
- **MCP**: FastMCP server sharing SQLite DB with backend

## Key Commands
```bash
make install        # uv sync + npm install
make dev            # Backend dev server (port 8000, auto-reload)
make frontend-dev   # Frontend dev server (port 5173, proxies /api → 8000)
make test           # Run all tests
make test-unit      # Unit tests only
make lint           # ruff check + format check
make typecheck      # mypy --strict
make format         # Auto-fix lint + format
make migrate        # Run database migrations
```

## Conventions
- **Imports**: Use absolute imports from `backend.` (e.g., `from backend.models import Article`)
- **Async**: All I/O is async. Use `async def` for handlers, sources, DB operations
- **Types**: Strict mypy. All function signatures typed. Use Pydantic models for data
- **SQL**: Raw SQL via aiosqlite (no ORM). Parameterized queries only (`?` placeholders)
- **Tests**: pytest + pytest-asyncio. Unit tests mock external I/O. Integration tests use in-memory SQLite
- **Config**: All secrets/config via environment variables, loaded through `backend.config.Settings`
- **Error handling**: Let exceptions propagate. FastAPI exception handlers catch at boundary
- **Line length**: 100 chars (ruff)
- **Formatting**: ruff format (Black-compatible)

## Source Plugin Pattern
Add a new source by:
1. Create `backend/sources/my_source.py`
2. Subclass `BaseSource`, implement `async def fetch() -> list[RawArticle]`
3. Decorate class with `@register_source`
4. Add import in `backend/sources/__init__.py`

## Database
- SQLite at `data/news.db` (WAL mode for concurrent reads)
- Migrations in `backend/migrations/` (numbered SQL files, run in order)
- FTS5 index on articles for full-text search

## Project Layout
```
backend/           # Python backend
  main.py          # FastAPI app factory + lifespan
  config.py        # Pydantic Settings
  database.py      # SQLite connection + migrations
  models.py        # Pydantic models
  sources/         # Source plugins (RSS, HN, Reddit, YouTube, etc.)
  scoring/         # Gemini scoring pipeline
  preferences/     # User profile + feedback processing
  scheduler/       # APScheduler fetch/score jobs
  api/             # FastAPI route modules
  mcp/             # FastMCP server
frontend/          # Vite + vanilla TypeScript SPA
tests/             # pytest (unit/, integration/, e2e/, visual/)
deploy/            # systemd, Caddy, backup scripts
```
