# Sift — Feedback Loop

How Sift learns from user feedback to improve article scoring over time.

## Overview

Sift's scoring pipeline uses Gemini Flash to assign each article a relevance score (0-10). The feedback loop closes the gap between what the model thinks you want and what you actually want. Every thumbs up, thumbs down, or "Missed" click adjusts your profile, and the next scoring run uses that updated profile to score new articles more accurately.

```
User feedback → Tag weight adjustment → Updated user profile → Better scoring prompts → More relevant feed
```

## How It Works

### 1. Scoring assigns tags

When Gemini scores an article, it also extracts topic tags (e.g., `rust`, `distributed-systems`, `linux-kernel`). These tags are stored in the `article_tags` table with a confidence value (0.0-1.0) indicating how strongly the tag applies.

### 2. Feedback adjusts tag weights

When you give feedback on an article, Sift looks up that article's tags and adjusts your tag weights accordingly:

| Action | Condition | Delta per tag | Signal strength |
|--------|-----------|---------------|-----------------|
| Thumbs up | Article score >= 7.0 | +0.1 * confidence | Normal positive |
| Thumbs up ("Missed") | Article score < 7.0 | +0.2 * confidence | Strong positive |
| Thumbs down | Any | -0.1 * confidence | Normal negative |
| Undo (rating = 0) | Any | No change | No-op |

The **confidence** multiplier means that if Gemini was only 50% sure an article was about "rust", a thumbs up adds +0.05 instead of +0.1 to the "rust" weight.

The **"Missed" signal** is intentionally twice as strong as a normal positive. When you find a below-threshold article in "Show all" mode and mark it as missed, you're telling Sift: "This should have been in my curated feed." That's a stronger learning signal than simply liking an article that was already surfaced.

### 3. Weights are bounded and pruned

- **Clamped** to [-5.0, 10.0] — prevents any single tag from dominating
- **Pruned** — tags with absolute weight below 0.01 are removed to keep the profile clean

### 4. Profile feeds back into scoring

The scoring pipeline reads the user profile (tag weights + prose profile + interests) and includes them in the system prompt sent to Gemini. This means:

- Tags with high positive weights bias the model toward scoring those topics higher
- Tags with negative weights signal "I've seen enough of this"
- The prose profile and interests list provide additional natural-language context

### 5. Continuous learning

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
   b. Builds personalized system prompt
   c. Gemini scores article → relevance_score + tags + explanation
   d. Tags stored in article_tags with confidence
3. User sees article in feed
4. User gives feedback (thumbs up/down/missed)
5. Feedback processor:
   a. Looks up article's tags + confidence
   b. Determines delta (positive/missed/negative)
   c. Adjusts tag_weights in user_profile
   d. Bumps profile_version
6. Next scoring run uses updated profile → better scores
```

## Manual Profile Editing

Users can also directly edit their profile via the Preferences page:

- **Prose profile**: Free-text description of interests (e.g., "I'm a backend engineer interested in distributed systems and database internals")
- **Interests**: Comma-separated topic list passed to the scoring model
- **Tag weights**: Read-only view of learned weights, with per-tag "Reset" button

Manual edits to prose profile and interests take effect on the next scoring run. Tag weights can only be reset (removed), not manually set — they're meant to be learned from behavior.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/preferences` | GET | Current profile (parsed, not raw JSON) |
| `/api/preferences` | PUT | Update prose_profile and/or interests |
| `/api/preferences/tags` | GET | Tag weights sorted by weight descending |
| `/api/preferences/tags/{name}` | DELETE | Remove a specific tag weight |

## Database Tables

- `user_profile` — single row (id=1), stores `tag_weights_json`, `prose_profile`, `interests_json`, `profile_version`
- `tags` — unique tag names (case-insensitive)
- `article_tags` — many-to-many with confidence values
- `feedback` — one rating per article (upsert)
