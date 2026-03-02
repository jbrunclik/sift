# Sift — Feedback Loop

How Sift learns from user feedback to improve article scoring over time.

## Overview

Sift's scoring pipeline uses Gemini Flash to assign each article a relevance score (0-10). The feedback loop closes the gap between what the model thinks you want and what you actually want. Every thumbs up, thumbs down, or "Missed" click adjusts your profile, and the next scoring run uses that updated profile to score new articles more accurately.

```
User feedback → Tag weight adjustment → Updated user profile → Better scoring prompts → More relevant feed
```

## How It Works

### 1. Scoring assigns tags with confidence

When Gemini scores an article, it extracts topic tags with confidence values (0.0-1.0) indicating how strongly each tag applies. Tags are returned as `{"name": "tag", "confidence": 0.8}` objects. These are stored in the `article_tags` table.

### 2. Post-LLM score adjustment

After the LLM returns a raw score, a deterministic adjustment is applied based on the user's tag weights:

```
adjustment = Σ(weight × confidence × 0.3)  # clamped to ±1.5
final_score = clamp(raw_llm_score + adjustment, 0, 10)
```

Both `raw_llm_score` and the adjusted `relevance_score` are stored. The raw score enables rescoring without re-calling the LLM when preferences change.

### 3. Dual-section prompt

The scoring prompt shows tag weights in two sections:
- **Strongly prefer** — top 15 positive weights (topics the user likes)
- **Seen enough / avoid** — top 10 negative weights (topics to deprioritize)

This ensures the LLM sees both positive and negative signals.

### 4. Feedback adjusts tag weights

When you give feedback on an article, Sift looks up that article's tags and adjusts your tag weights accordingly:

| Action | Condition | Delta per tag | Signal strength |
|--------|-----------|---------------|-----------------|
| Thumbs up | Article score >= 7.0 | +0.1 * confidence | Normal positive |
| Thumbs up ("Missed") | Article score < 7.0 | +0.2 * confidence | Strong positive |
| Thumbs down | Any | -0.1 * confidence | Normal negative |
| Undo (rating = 0) | Any | No change | No-op |

The **confidence** multiplier means that if Gemini was only 50% sure an article was about "rust", a thumbs up adds +0.05 instead of +0.1 to the "rust" weight.

### 5. Weights are bounded and pruned

- **Clamped** to [-5.0, 10.0] — prevents any single tag from dominating
- **Pruned** — tags with absolute weight below 0.01 are removed to keep the profile clean

### 6. Borderline rescoring

When the profile version advances by 5+ since the last rescore, the pipeline re-computes adjusted scores for unread borderline articles (raw score in [5.0, 8.0], published within 24 hours). This can promote previously-filtered articles above the curated threshold when preferences change, without wasting work on already-read or stale articles.

### 7. Weight decay and profile synthesis

Every 6 hours (configurable via `profile_synthesis_interval_hours`):
1. All tag weights are multiplied by 0.995 (decay factor), pruning those below ±0.01
2. Recent feedback is summarized and sent to Gemini to generate a prose profile
3. Profile version is bumped

This ensures stale preferences gradually fade and the prose profile stays current.

### 8. Tag quality instrumentation

Each feedback event updates `tag_feedback_stats` (positive/negative vote counts per tag). The `GET /api/preferences/vocabulary/quality` endpoint exposes tags with high disagreement ratios — tags that correlate with both positive and negative feedback — indicating they may be too broad or ambiguous.

### 9. Continuous learning

Every piece of feedback immediately updates the profile (same database transaction as the feedback itself). There's no batch processing delay — the next scoring run will use your latest preferences.

Over time, the tag weights naturally converge to reflect your actual interests:
- Topics you consistently engage with accumulate positive weight
- Topics you consistently reject accumulate negative weight
- Topics you're indifferent to stay near zero and get pruned

## Data Flow

```
1. Article fetched → stored in articles table
2. Scoring pipeline runs:
   a. Reads user_profile (tag_weights, prose_profile, interests)
   b. Builds personalized system prompt (positive + negative weight sections)
   c. Gemini scores article → raw_llm_score + tags with confidence + explanation
   d. Tags stored in article_tags with confidence
   e. Post-LLM adjustment applied → relevance_score = raw + adjustment
   f. Borderline articles rescored if profile changed enough
3. User sees article in feed
4. User gives feedback (thumbs up/down/missed)
5. Feedback processor:
   a. Looks up article's tags + confidence
   b. Determines delta (positive/missed/negative)
   c. Adjusts tag_weights in user_profile
   d. Updates tag_feedback_stats
   e. Bumps profile_version
6. Next scoring run uses updated profile → better scores
7. Profile synthesizer (every 6h):
   a. Applies weight decay
   b. Generates prose profile from weights + recent feedback
   c. Bumps profile_version
```

## Cold-Start Onboarding

New users (profile_version == 0) can seed their profile via `POST /api/onboarding` with a list of interest topics. Each interest is added as a tag weight at +1.0.

## Manual Profile Editing

Users can also directly edit their profile via the Preferences page:

- **Prose profile**: Free-text description of interests
- **Interests**: Comma-separated topic list passed to the scoring model
- **Tag weights**: Read-only view of learned weights, with per-tag "Reset" button

Manual edits take effect on the next scoring run.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/preferences` | GET | Current profile (parsed, not raw JSON) |
| `/api/preferences` | PUT | Update prose_profile and/or interests |
| `/api/preferences/tags` | GET | Tag weights sorted by weight descending |
| `/api/preferences/tags/{name}` | DELETE | Remove a specific tag weight |
| `/api/preferences/vocabulary/quality` | GET | Tag quality report (disagreement ratios) |
| `/api/onboarding` | POST | Seed initial profile from interests |

## Database Tables

- `user_profile` — single row (id=1), stores `tag_weights_json`, `prose_profile`, `interests_json`, `profile_version`, `last_rescore_version`
- `articles` — includes `raw_llm_score` and adjusted `relevance_score`
- `tags` — unique tag names (case-insensitive)
- `article_tags` — many-to-many with confidence values
- `feedback` — one rating per article (upsert)
- `tag_feedback_stats` — positive/negative vote counts per tag
