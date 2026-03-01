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

### Managed tag vocabulary [DONE]
- [x] `backend/migrations/007_managed_tag_vocabulary.sql` — `is_approved` flag, `tag_candidates` table, bootstrap
- [x] `backend/preferences/tag_vocabulary.py` — vocabulary CRUD, fuzzy resolve, auto-promote, merge
- [x] Prompt restructured: hard vocabulary constraint + `+` prefix escape hatch (ADR-017, supersedes ADR-015)
- [x] Pipeline post-processing: resolve tags against vocabulary, track candidates
- [x] Scorer preserves `+` prefix through normalization
- [x] API endpoints: vocabulary CRUD, merge, candidates approve/reject
- [x] Frontend: vocabulary management UI in preferences (pills, add, merge, candidates)
- [x] Cleanup: stale candidate pruning, preserve approved tags when orphaned
- [x] Tests: 21 unit (tag_vocabulary), 4 prompt, 11 API integration — all passing

### Feedback loop [TODO — remaining]
- [ ] `backend/preferences/cold_start.py` + cold-start wizard frontend
- [ ] `POST /api/articles/submit-url` for manually submitting missed links
- [ ] Periodic prose profile synthesis from tag weights + feedback history

### Article content extraction [DONE]
- [x] Fetch actual article content (not just RSS summaries) for better LLM scoring
- [x] Content extractor using httpx + trafilatura to get clean article text
- [x] Worker pool with concurrency limits (asyncio.Semaphore) for parallel fetching
- [x] Store extracted text in `articles.content_full` column
- [x] Update scoring pipeline to prefer `content_full` over `content_snippet` when available
- [x] Rate-limit per domain (robots.txt intentionally skipped — see ADR-016)

## Phase 2.5: UX Overhaul + Operational Improvements [DONE]

Design decisions accepted (ADRs written). Implementation complete.

### Backend
- [x] Summary language support (migration 003, prompt changes, preferences API)
- [x] Source categories (migration 004, CRUD, autocomplete)
- [x] Adaptive fetch intervals (EMA tracking, auto-adjust 10–360 min)
- [x] LLM cost tracking (scoring_logs table, per-model pricing, monthly stats)
- [x] Tag consistency (top 50 existing tags seeded into LLM prompt)
- [x] Vote marks articles as read
- [x] Daily cleanup (articles > 90 days, orphan tags, old logs)
- [x] Scheduler run tracking (scheduler_runs table, per-job status/details)
- [x] Scoring failure tracking (score_attempts, error reasons, force-retry API)
- [x] Gemini 429 retry with exponential backoff (scorer.py)
- [x] Migration runner fix: statement-by-statement execution, trigger support

### Frontend
- [x] Inbox behavior: curated + unread default, training mode toggle
- [x] Card exit animation on vote/read/click
- [x] Undo toast on vote/read
- [x] Keyboard shortcuts (j/k/u/d/e/m/o/t/?)
- [x] Click-on-article = upvote
- [x] Custom modal dialogs (replaces browser confirm())
- [x] Premium stats page: overview cards, score distribution chart, source health, LLM costs, tag cloud
- [x] Background jobs table with next scheduled run, run buttons, detail pills
- [x] Scoring failures table with error details, force-retry
- [x] Nav badge for active issues
- [x] Tab title with unread count: `[N] Sift`
- [x] Source category editing with pencil icon + autocomplete
- [x] Score badge: subtle color-mix style
- [x] "Why?" button as info icon toggle
- [x] Tag weights table with visual bars
- [x] Summary language dropdown in preferences
- [x] SPA router cleanup (MutationObserver for event listener removal)
- [x] Consistent toolbar height (36px CSS variable)

## Phase 3: More Sources [IN PROGRESS]

- [x] `backend/sources/webpage.py` (generic web page with LLM-learned CSS extraction rules)
- [x] Per-source authentication with paywall truncation detection (ADR-019)
- [ ] `backend/sources/hackernews.py` (Firebase REST API)
- [ ] `backend/sources/youtube.py` (YouTube RSS feeds)
- [ ] `backend/sources/reddit.py` (httpx-based, asyncpraw has dep conflicts)
- [ ] `backend/sources/hncz.py` (RSS/scrape)
- [ ] `backend/sources/playwright_pool.py` (shared browser instance, if needed)

## Phase 4: MCP Server + Preference Refinement [TODO]

- [ ] `backend/mcp/server.py` (FastMCP with all tools + resources)
- [ ] `backend/preferences/profile_synthesizer.py` (scheduled every 6h)
- [ ] Preference decay, tag pruning, feedback-weighted rescoring
- [x] Frontend: stats page with fetch logs, source health details (done in Phase 2.5)
- [ ] MCP integration tests

## Phase 5: Polish + Deploy [TODO]

- [ ] Deploy scripts for Hetzner (nginx reverse proxy, user systemd units)
- [ ] Systemd timers for fetching (replace in-process APScheduler)
- [ ] Systemd timer for scoring/evaluation pipeline
- [ ] SQLite backup via systemd timer (daily, keep 7 days)
- [ ] E2E tests (Playwright browser flows)
- [x] Visual regression tests (Playwright screenshot tests for feed, stats, preferences, modals)
- [x] Error handling: Gemini 429 retry with exponential backoff, scoring failure visibility
- [x] Batch scoring: concurrent with semaphore (configurable max_concurrent)
- [ ] GitHub CI pipeline (lint, typecheck, test on push/PR)

### UI Polish
- [x] Counts in brackets use pill/badge styling (section-count class)
- [x] Visual tests for reviewing suggested tags (candidates approve/reject flow)
- [x] Empty feed "all caught up" state with SVG illustration

---

Architecture decisions are recorded in [`docs/adr/`](adr/README.md).
