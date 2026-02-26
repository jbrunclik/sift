# Sift

Personal news filter. Fetches articles from RSS feeds, scores relevance with Gemini Flash, and shows you only what matters. The default feed is a short curated list — not a firehose. A feedback loop (thumbs up/down + "Missed" corrections) teaches Sift your interests over time.

## Setup

```bash
# Install dependencies
make install

# Copy and fill in environment variables
cp .env.example .env

# Run database migrations
make migrate

# Start dev server (backend + frontend)
make dev
```

## How It Works

1. **Add RSS feeds** — enter a name and feed URL in the Sources page
2. **Sift fetches** — articles are pulled every 30 minutes (or manually via "Fetch now")
3. **Gemini scores** — each article gets a 0-10 relevance score based on your profile
4. **You see the cream** — only articles scoring >= 7.0 appear in the default feed
5. **You give feedback** — thumbs up/down refines future scoring
6. **"Show all" mode** — browse everything and mark articles Sift missed

## Sources

Currently RSS only. More sources planned.

| Source | Type | Status |
|--------|------|--------|
| RSS feeds (Feedly, iDNES, etc.) | RSS/Atom | Implemented |
| Hacker News | Firebase API | Planned |
| YouTube channels | RSS | Planned |
| Reddit | httpx | Planned |
| HN.cz | RSS/scrape | Planned |
| mczlicin.cz/dp | Scrape | Planned |

## Development

```bash
make dev        # Run backend + frontend (concurrently)
make test       # Run all tests
make lint       # ruff check + format check
make typecheck  # mypy --strict
make format     # Auto-fix lint + formatting
make migrate    # Apply database migrations
make serve      # Production server (PORT env var)
```

## Claude Code Skills

| Skill | Description |
|-------|-------------|
| `/feature <desc>` | Plan and implement a new feature |
| `/bug <desc>` | Investigate and fix a bug |
| `/commit` | Run checks and commit with Conventional Commits |
| `/improve` | Analyze session, learn from corrections, update docs |

## Tech Stack

- **Backend**: Python 3.14, FastAPI, SQLite (WAL + FTS5), APScheduler
- **Frontend**: Vite + vanilla TypeScript
- **Scoring**: Gemini Flash via `google-genai`
- **Package management**: `uv` (Python), `npm` (frontend)
- **Linting**: `ruff` (lint + format), `mypy` (strict)
- **Testing**: `pytest` + `pytest-asyncio` + `respx`
