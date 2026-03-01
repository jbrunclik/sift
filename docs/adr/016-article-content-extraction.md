# ADR-016: Article content extraction via trafilatura

## Status
Accepted

## Context
Sift scores articles using RSS feed snippets (`content_snippet`), which are often truncated summaries or just the first paragraph. The LLM needs richer context to produce accurate relevance scores and meaningful summaries. Fetching the full article text from the original URL would significantly improve scoring quality.

The database schema already has a `content_full` column (migration 001), and the scoring pipeline already prefers it over snippets (`content_full or content_snippet or ""` in pipeline.py). We just need to populate it.

## Decision
Use **trafilatura** for article content extraction. It is purpose-built for web article extraction, handling boilerplate removal, encoding detection, and fallback strategies out of the box.

Key design choices:
- **Separate background job** rather than inline in RSS fetch: decoupled, independently retryable, and backfills existing articles
- **Per-domain rate limiting** (2-second cooldown between requests to the same domain) to be a good citizen
- **No robots.txt checking**: overkill for a single-user personal aggregator; rate limiting is sufficient
- **`asyncio.to_thread()`** for trafilatura calls: the library is CPU-bound/synchronous and would block the event loop
- **Head+tail truncation** for LLM input: news articles front-load key information; the conclusion provides scoring context; the middle is often filler. For articles > 4000 chars, take first 3000 + last 1000 chars

Extraction tracking columns (`extraction_status`, `extraction_attempted_at`) enable retry logic and monitoring without re-fetching already-processed articles.

## Consequences
- Better scoring quality: LLM sees full article context instead of truncated RSS snippets
- ~15s latency per article extraction (fetch + parse), handled asynchronously in background
- Marginal cost increase from larger prompts (~$0.0001/article with Gemini Flash)
- Extraction failures gracefully fall back to existing `content_snippet` — no regression
- Articles already scored keep their scores; only new articles benefit from richer content
- New "extract" job visible in Stats page with run/trigger support
