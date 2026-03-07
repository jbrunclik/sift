# ADR-014: Daily data cleanup

## Status
Accepted

## Context
SQLite databases grow without bound unless old data is pruned. Articles accumulate at 50-200 per day across all sources. After a few months, the DB contains tens of thousands of stale rows that the user will never revisit.

## Decision
Run a daily cleanup job (via APScheduler) that:

1. **Deletes articles older than 90 days** -- except articles with any feedback (thumbs up/down, "Missed"). Those are retained indefinitely as training signal.
2. **Prunes orphaned tags** -- tags no longer referenced by any article_tags row.
3. **Deletes old scoring logs** -- scoring_logs entries older than 365 days.
4. **Runs `PRAGMA optimize`** -- updates query planner statistics (lightweight, no lock).
5. **Cleans extraction cache** -- removes stale cache files older than 7 days from `data/extraction_cache/`.

The retention period (90 days) is configurable via `ARTICLE_RETENTION_DAYS`.

**VACUUM** is intentionally excluded from in-process cleanup. It requires an exclusive database lock that blocks all readers and writers for its entire duration, causing API request failures. VACUUM should be run via a systemd timer when the app is idle (see Phase 5 roadmap).

## Consequences
- DB size stays bounded even with heavy use (estimated steady state: ~50 MB)
- Feedback-bearing articles are never lost, preserving the training corpus
- No exclusive locks during cleanup — API stays responsive
- Orphan tag pruning keeps autocomplete suggestions relevant
- If a user wants to revisit old articles, they are gone -- the 90-day window is a trade-off
