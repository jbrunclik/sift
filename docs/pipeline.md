# Sift — Pipeline Architecture

This document describes how data flows through Sift: from RSS feeds to your curated inbox.

---

## Overview

```
RSS Feeds → Fetch → Store → Score (Gemini) → Curate (≥ 7.0) → Inbox
                                                    ↑
                                            Feedback Loop
                                        (tag weights, profile)
```

## 1. Fetch Pipeline

**Trigger:** APScheduler runs `fetch_all_sources()` every **30 minutes** (global schedule).

**Per-source adaptive intervals:** Each source has its own `fetch_interval_minutes` (default: 30) that adapts based on how many new articles it produces:

| Condition | Adjustment |
|---|---|
| 3+ consecutive empty fetches | Double interval (max 360 min / 6h) |
| Average > 5 new articles/fetch | Halve interval (min 10 min) |
| Average 0–2 new articles/fetch | Increase 50% (max 360 min) |

The average uses an **exponential moving average** (alpha = 0.3) for smooth adaptation.

**Process:**
1. For each enabled source, instantiate the source plugin (e.g., `RssSource`)
2. Fetch raw articles via `httpx.AsyncClient`
3. Normalize URLs (strip `www.`, tracking params, trailing slashes)
4. Insert into `articles` table (skip duplicates via `UNIQUE(url_normalized)`)
5. Update `fetch_logs` with timing, counts, and status
6. Update source's adaptive interval stats
7. Record run in `scheduler_runs` table

**Manual trigger:** `POST /api/jobs/fetch` or per-source `POST /api/sources/:id/fetch`

## 2. Scoring Pipeline

**Trigger:** APScheduler runs `score_unscored_articles()` every **5 minutes** (configurable via `SCORING_INTERVAL_MINUTES`).

**Process:**
1. Query unscored articles (no `relevance_score`, not hidden)
2. Deduplicate within batch (URL exact match + fuzzy title matching via `difflib`)
3. Load user profile: prose description, interests, tag weights
4. Load top 50 existing tags for consistency
5. Load `summary_language` preference
6. Build system prompt incorporating all of the above
7. Batch articles (up to 10 per Gemini call) and send to `gemini-3-flash-preview`
8. Parse structured JSON response: `{ scores: [{ url, score, tags, explanation, summary }] }`
9. Clamp scores to 0.0–10.0 range
10. Store scores, tags, summaries, and explanations
11. Log token usage and cost to `scoring_logs`

**Scoring criteria** (from system prompt):
- Relevance to user's stated interests and profile
- Recency and timeliness
- Technical depth and quality
- Tag weight adjustments from feedback history

**Cost tracking:** Each batch logs `tokens_in`, `tokens_out`, model name, and calculated `cost_usd` based on per-model pricing in `backend/scoring/pricing.py`.

**Manual trigger:** `POST /api/jobs/score`

## 3. Feedback Loop

**User actions → learning:**

| Action | Effect |
|---|---|
| Thumbs up (+1) | Boost tags on that article by +0.3 each |
| Thumbs down (-1) | Penalize tags by -0.3 each |
| "Missed" button | Same as thumbs up (strong signal for sub-threshold articles) |
| Remove vote (0) | Reverse the previous adjustment |

Tag weights are stored in `user_profile.tag_weights_json` and influence future scoring via the system prompt. Weights are clamped to [-5.0, +5.0] and zero-weight tags are pruned.

**Voting also marks articles as read** — this is the inbox exit behavior.

## 4. Curation

The default feed shows articles that are:
- **Unread** (`is_read = 0`)
- **Scored ≥ 7.0** (curated threshold)
- **Not hidden** (`is_hidden = 0`)

**Training mode** removes the score threshold, showing all scored articles for fine-tuning.

## 5. Cleanup

**Trigger:** APScheduler runs `run_cleanup()` every **24 hours**.

**Process:**
1. Delete articles older than 90 days (configurable via `ARTICLE_RETENTION_DAYS`), preserving articles with feedback
2. Prune orphaned tags (no article references)
3. Prune old fetch logs (> 30 days)
4. Prune old scoring logs (> 365 days)
5. `VACUUM` the database

**Manual trigger:** `POST /api/jobs/cleanup`

## 6. Schedule Summary

| Job | Interval | Configurable |
|---|---|---|
| Fetch all sources | 30 min (global) | Per-source adaptive |
| Score unscored | 5 min | `SCORING_INTERVAL_MINUTES` |
| Cleanup | 24 hours | `ARTICLE_RETENTION_DAYS` |

All jobs can be triggered manually from the Stats page in the UI.
