# Sift — Implementation Roadmap

This file serves as a memory bank for agents: it tracks what's been done, what's in progress, and what's next. Update after each phase.

---

## Phase 0: Documentation + Scaffolding [DONE]

- [x] `pyproject.toml` (uv, ruff, mypy, pytest config, all dependencies)
- [x] `.python-version` (3.14)
- [x] `.gitignore` (Python, Node, data/, .env, etc.)
- [x] `.env.example`
- [x] `Makefile` (dev with concurrently, test, lint, typecheck, serve, migrate)
- [x] `CLAUDE.md` (agent context: architecture, conventions, commands)
- [x] `README.md` (project overview, setup guide, skills table)
- [x] `docs/product-spec.md` (product specification)
- [x] `docs/roadmap.md` (this file)
- [x] `.claude/agents/implementer.md`, `reviewer.md`, `tester.md`
- [x] `.claude/commands/feature.md`, `bug.md`, `commit.md`, `improve.md`
- [x] Directory skeleton: all `__init__.py` files, `frontend/package.json`, `frontend/tsconfig.json`

## Phase 1: Foundation + RSS Source + Basic UI [DONE]

- [x] `backend/config.py` (Pydantic Settings, .env loading, gemini-3-flash-preview default)
- [x] `backend/database.py` (aiosqlite, WAL mode, migration runner, test override)
- [x] `backend/migrations/001_initial_schema.sql` + `002_fts5_indexes.sql`
- [x] `backend/models.py` (Pydantic models for all entities)
- [x] `backend/sources/base.py` + `backend/sources/__init__.py` (plugin registry)
- [x] `backend/sources/rss.py` (generic RSS — covers Feedly imports, iDNES, any feed)
- [x] `backend/scheduler/worker.py` (APScheduler with fetch jobs)
- [x] `backend/api/routes_articles.py` (curated feed default >= 7.0, show_all, get, read/unread, hide)
- [x] `backend/api/routes_sources.py` (CRUD + trigger fetch)
- [x] `backend/api/routes_feedback.py` (thumbs up/down, upsert)
- [x] `backend/api/routes_health.py` (health + stats)
- [x] `backend/main.py` (app factory + lifespan + scheduler)
- [x] Frontend: Vite setup, router, api.ts, state.ts, types.ts, utils.ts
- [x] Frontend: curated feed page (default: only scored >= 7.0, "Show all" to explore)
- [x] Frontend: article cards with "Missed" button for sub-threshold articles
- [x] Frontend: infinite scroll, search bar, source filter, unread toggle
- [x] Frontend: source manager — add by name + feed URL (no JSON)
- [x] Frontend: stats page, nav bar, toast notifications
- [x] Frontend: CSS with dark mode support (prefers-color-scheme)
- [x] Unit tests: RSS parser, deduplicator, models (11 passing)
- [x] Integration tests: article API, health, stats, feedback (4 passing)
- [x] All checks pass: ruff, mypy --strict, pytest (16/16), tsc
- [x] Deploy: systemd service file (reads HOST/PORT from .env)

## Phase 2: Scoring + Feedback Loop [IN PROGRESS]

### Scoring pipeline [DONE]
- [x] `backend/scoring/prompts.py` — system + batch prompt templates (cold-start fallback)
- [x] `backend/scoring/deduplicator.py` — URL exact + fuzzy title matching (difflib)
- [x] `backend/scoring/scorer.py` — Gemini batched scoring (structured JSON, score clamping)
- [x] `backend/scoring/pipeline.py` — orchestrate: dedupe → batch → score → store (concurrent)
- [x] `backend/scoring/__init__.py` — exports run_scoring_pipeline
- [x] `backend/scheduler/worker.py` — score_unscored_articles job
- [x] `backend/main.py` — scoring schedule (every 5 min default)
- [x] Gemini integration (google-genai, structured JSON output, BatchScoringResponse schema)
- [x] Tests: prompts (10), deduplicator (10), scorer (10), pipeline (7) — 37 new tests
- [x] All checks pass: ruff, mypy --strict, pytest (53/53)

### Feedback loop [DONE]
- [x] `backend/preferences/tag_weights.py` — pure functions: clamp, adjust_weights, prune_zero_weights
- [x] `backend/preferences/feedback_processor.py` — process_feedback wired into feedback API
- [x] `backend/preferences/__init__.py` — public API exports
- [x] `backend/api/routes_preferences.py` — GET/PUT preferences, GET/DELETE tag weights
- [x] `backend/api/routes_articles.py` — fixed: tags now populated from article_tags/tags join
- [x] `backend/api/routes_feedback.py` — wired to feedback processor (same transaction)
- [x] Frontend: preferences page (prose profile, interests, learned tag weights)
- [x] Frontend: "Why?" button on article cards (score explanation toggle)
- [x] Frontend: score badge tooltip with explanation
- [x] Tests: tag_weights (18), feedback_processor (7), integration (3) — 28 new tests
- [x] All checks pass: ruff, mypy --strict, pytest (81/81)
- See [`docs/feedback-loop.md`](feedback-loop.md) for detailed explanation

### Feedback loop [TODO — remaining]
- [ ] `backend/preferences/cold_start.py` + cold-start wizard frontend
- [ ] `POST /api/articles/submit-url` for manually submitting missed links
- [ ] Periodic prose profile synthesis from tag weights + feedback history

## Phase 3: More Sources [TODO]

- [ ] `backend/sources/hackernews.py` (Firebase REST API)
- [ ] `backend/sources/youtube.py` (YouTube RSS feeds)
- [ ] `backend/sources/reddit.py` (httpx-based, asyncpraw has dep conflicts)
- [ ] `backend/sources/hncz.py` (RSS/scrape)
- [ ] `backend/sources/mczlicin.py` (httpx or Playwright)
- [ ] `backend/sources/playwright_pool.py` (shared browser instance, if needed)

## Phase 4: MCP Server + Preference Refinement [TODO]

- [ ] `backend/mcp/server.py` (FastMCP with all tools + resources)
- [ ] `backend/preferences/profile_synthesizer.py` (scheduled every 6h)
- [ ] Preference decay, tag pruning, feedback-weighted rescoring
- [ ] Frontend: stats page with fetch logs, source health details
- [ ] MCP integration tests

## Phase 5: Polish + Deploy [TODO]

- [ ] Deploy scripts for Hetzner (nginx reverse proxy, user systemd units)
- [ ] Systemd timers for fetching (replace in-process APScheduler)
- [ ] Systemd timer for scoring/evaluation pipeline
- [ ] SQLite backup via systemd timer (daily, keep 7 days)
- [ ] E2E tests (Playwright browser flows)
- [ ] Visual regression tests (screenshot baselines)
- [ ] Error handling: graceful Gemini degradation, retry logic, rate limiting
- [ ] Batch scoring optimization (concurrent Gemini calls)

---

Architecture decisions are recorded in [`docs/adr/`](adr/README.md).
