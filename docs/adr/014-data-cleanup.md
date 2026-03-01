# ADR-014: Daily data cleanup

## Status
Accepted

## Context
SQLite databases grow without bound unless old data is pruned. Articles accumulate at 50-200 per day across all sources. After a few months, the DB contains tens of thousands of stale rows that the user will never revisit.

## Decision
Run a daily cleanup job (via APScheduler, default 03:00 local time) that:

1. **Deletes articles older than 90 days** -- except articles with any feedback (thumbs up/down, "Missed"). Those are retained indefinitely as training signal.
2. **Prunes orphaned tags** -- tags no longer referenced by any article_tags row.
3. **Deletes old scoring logs** -- scoring_logs entries older than 180 days.
4. **Runs VACUUM** -- reclaims freed pages and defragments the database file.

The retention period (90 days) and scoring log retention (180 days) are configurable via `CLEANUP_ARTICLE_DAYS` and `CLEANUP_LOG_DAYS` environment variables.

## Consequences
- DB size stays bounded even with heavy use (estimated steady state: ~50 MB)
- Feedback-bearing articles are never lost, preserving the training corpus
- VACUUM briefly locks the DB for writes; acceptable at 03:00
- Orphan tag pruning keeps autocomplete suggestions relevant
- If a user wants to revisit old articles, they are gone -- the 90-day window is a trade-off
