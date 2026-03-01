# Sift

**Personal news aggregator with AI-powered relevance scoring.**

Sift fetches articles from your RSS feeds, scores each one for relevance using Gemini Flash, and surfaces only what matters. Your curated inbox shows high-relevance articles — not a firehose. A feedback loop learns your preferences over time through thumbs up/down voting and "Missed" corrections.

---

## How It Works

```
RSS Feeds → Fetch → Gemini Scoring → Curated Inbox (score ≥ 7.0)
                                            ↑
                                      Feedback Loop
                                   (tag weights + profile)
```

1. **Add RSS feeds** — enter a name and feed URL in the Sources page
2. **Sift fetches automatically** — adaptive intervals (10 min–6 hours) based on feed activity
3. **Gemini scores every article** — 0–10 relevance score based on your profile, interests, and feedback history
4. **Your inbox shows only the best** — articles scoring ≥ 7.0 appear by default
5. **Give feedback** — thumbs up/down teaches Sift what you care about
6. **Training mode** — browse everything, mark articles Sift missed for rapid calibration

## Features

- **Curated inbox** — read-and-archive semantics; voted/read articles exit with undo support
- **AI scoring** — Gemini Flash rates every article with explanation and auto-generated summary
- **Adaptive fetch** — feed intervals adjust automatically based on new article frequency
- **Feedback loop** — tag weight learning from votes; weights influence future scoring
- **Multilingual summaries** — configurable summary language (English, Czech, etc.)
- **Keyboard shortcuts** — vim-style navigation (j/k/u/d/e/o/?/t)
- **Source categories** — free-text categorization with autocomplete
- **LLM cost tracking** — per-model token usage and cost breakdown
- **Dark mode** — follows system preference
- **Pipeline visibility** — background job triggers, source health, error tracking from the UI

## Quick Start

```bash
# Install dependencies (requires uv + node)
make install

# Copy and configure environment variables
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY

# Apply database migrations
make migrate

# Start development server (backend:8000 + frontend:5173)
make dev
```

Open [http://localhost:5173](http://localhost:5173) and add your first RSS feed.

## Configuration

Key environment variables (see `.env.example` for all options):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google AI API key (required for scoring) |
| `DATABASE_PATH` | `data/news.db` | SQLite database location |
| `PORT` | `8000` | Backend server port |
| `SCORING_INTERVAL_MINUTES` | `5` | How often to score new articles |
| `ARTICLE_RETENTION_DAYS` | `90` | Days to keep articles before cleanup |

## Architecture

```
backend/               Python 3.14 + FastAPI
  api/                 REST endpoints (articles, sources, feedback, preferences, stats)
  scoring/             Gemini pipeline (batched scoring, cost tracking, deduplication)
  preferences/         Feedback processor, tag weight learning
  scheduler/           APScheduler jobs (fetch, score, cleanup)
  sources/             Source plugins (RSS, extensible)
  migrations/          Numbered SQL migrations

frontend/              Vite + vanilla TypeScript SPA
  src/pages/           Feed, sources, stats, preferences
  src/components/      Article cards, nav, search, toast
  src/styles/          CSS design system (light + dark)

tests/                 pytest (unit, integration, visual)
docs/                  Product spec, ADRs, pipeline docs
```

## Development

```bash
make dev              # Backend + frontend concurrently
make test             # All tests (all passing)
make test-unit        # Unit tests only
make lint             # ruff check + format check
make typecheck        # mypy --strict
make format           # Auto-fix lint + formatting
make migrate          # Apply database migrations
```

## Pipeline

See [docs/pipeline.md](docs/pipeline.md) for detailed data flow documentation.

**Schedule summary:**

| Job | Interval | Notes |
|-----|----------|-------|
| Fetch sources | 30 min (global) | Per-source adaptive intervals |
| Score articles | 5 min | Configurable via env |
| Cleanup | 24 hours | Respects feedback, configurable retention |

All jobs can be triggered manually from the Stats page.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `j` / `k` | Navigate down / up |
| `o` / `Enter` | Open article in new tab |
| `u` | Upvote (more like this) |
| `d` | Downvote (less like this) |
| `e` / `m` | Mark as read |
| `t` | Toggle training mode |
| `?` | Show help overlay |

## Tech Stack

- **Backend**: Python 3.14, FastAPI, SQLite (WAL + FTS5), APScheduler
- **Frontend**: Vite + vanilla TypeScript (no framework)
- **Scoring**: Gemini 3.0 Flash via `google-genai`, structured JSON output
- **Package management**: `uv` (Python), `npm` (frontend)
- **Linting**: `ruff` (lint + format), `mypy --strict`
- **Testing**: `pytest` + `pytest-asyncio` + `respx` (pytest)

## License

Private project.
