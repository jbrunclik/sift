# ADR-019: Per-source authentication with truncation detection

## Status

Accepted

## Context

Some news sources (e.g., HN.cz / Hospodářské noviny) provide public RSS feeds but paywall their article pages. Users with valid subscriptions need a way to pass session cookies so the content extractor fetches full article text instead of truncated previews.

The tricky part: paywalled sites often don't return 401/403 — they silently serve truncated content when cookies are missing or expired.

## Decision

### Cookie storage

Store a raw `Cookie` header string in the source's `config_json` as `"auth_cookie"`. This is the exact value from browser DevTools (Network tab → Cookie header), trivially copy-pasteable. No parsing, no structured cookie objects.

### Two HTTP paths need cookies

1. **Feed fetcher** (`worker.py`) — for sources where the feed itself needs auth
2. **Content extractor** (`extractor.py`) — the main path; articles are grouped by source and each auth source gets its own httpx client with cookies

### Truncation detection

3-signal heuristic applied only to auth-configured sources:
- `content_full` shorter than 80% of `content_snippet` from RSS
- `content_full` < 300 chars
- Content length < 30% of source's historical EMA average

Truncated articles get `extraction_status = 'truncated'` (new status alongside success/failed/skipped).

### Test endpoint

`POST /api/sources/{id}/test-auth` gives immediate feedback when users paste new cookies — fetches a recent article and reports ok/truncated/error.

### Alerting

Auth truncations surface in:
- Stats page issues banner (with per-source detail table)
- Nav badge red dot (included in issue count polling)

## Consequences

- Generic feature: any source can use auth, not just RSS
- No schema change for `config_json` — just a convention for the `auth_cookie` key
- Single new column: `sources.avg_content_length` (EMA for truncation signal)
- Truncation detection has false-positive risk for legitimately short articles, but the 300-char and 30% thresholds are conservative and only apply to auth sources
