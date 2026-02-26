# Sift — Product Specification

## Vision

You follow 8+ news sources but only a few articles per day are actually worth reading. Sift eliminates the scanning: it fetches everything in the background, uses an LLM to filter for *your* interests, and shows you only the cream of the crop. The default feed is not "all articles sorted by score" — it's a short, curated list of things the system believes you'll want to read. Everything else is silently filtered out.

A feedback loop teaches Sift what you care about. Over time, it gets better at separating signal from noise.

## Core Principle

**The feed should feel like a personal briefing, not a firehose.** If the LLM isn't confident you'd want to read something, it doesn't show up. You should open Sift, see 5-15 articles worth reading, and be done.

## User Stories

1. **As a user**, I open Sift and see only articles the system thinks I'll care about — no noise.
2. **As a user**, I thumbs up/down articles so the system refines what it surfaces for me.
3. **As a user**, I can mark articles that were missed — "Sift should have shown me this" — to correct the filter.
4. **As a user**, I can toggle "Show all" to browse everything and manually check what Sift filtered out.
5. **As a user**, I can search through everything (including filtered-out articles) by keyword.
6. **As a user**, I can mark articles as read to track what I've seen.
7. **As a user**, I can add RSS feeds by entering just a name and URL.
8. **As a user**, I can manually trigger a fetch and see system health stats.
9. **As a user**, I can submit URLs the system missed (treated as positive signal).
10. **As a user**, I can interact with Sift through Claude via MCP tools.

## Data Sources

Starting with RSS only. More sources will be added incrementally.

| Source | Method | Status |
|--------|--------|--------|
| RSS feeds (Feedly, iDNES, etc.) | feedparser | Implemented |
| Hacker News | Firebase REST API | Planned |
| YouTube channels | RSS feeds | Planned |
| Reddit subreddits | httpx | Planned |
| HN.cz | RSS or scraping | Planned |
| mczlicin.cz/dp | httpx or Playwright | Planned |

## Scoring & Filtering

Each fetched article gets a 0-10 relevance score from Gemini Flash:
- **7-10**: Shown in the default curated feed (high confidence you'll want this)
- **4-6.9**: Not shown by default, accessible via "Show all" or search
- **0-3.9**: Noise — only accessible via explicit search

Along with the score, the LLM produces:
- A one-sentence summary
- An explanation of why it scored this way
- Extracted topic tags

Scoring uses the user's prose profile (synthesized from feedback) and top tag weights.

## Feedback & Preference Learning

### Feedback mechanisms
- **Thumbs up**: "This is interesting" — standard positive signal
- **Thumbs down**: "Not interesting" — negative signal
- **"Missed" button**: Shown on articles below the curated threshold in "Show all" mode — a strong positive signal meaning "Sift should have surfaced this"
- **Implicit**: Submitting a URL = positive; clicking through = mild positive

### Learning
- **Immediate**: Thumbs up/down adjusts tag weights (+/- 0.1 * confidence). "Missed" is an extra-strong positive signal.
- **Periodic**: Every 6 hours, synthesize a prose profile from recent feedback + tag weights
- **Decay**: Tag weights decay by 0.995 per synthesis cycle (interests evolve)
- **Cold start**: Onboarding wizard with interest categories + free text

## UX

- **Default view**: Curated feed — only articles scoring >= 7.0, sorted by score then recency
- **"Show all" toggle**: Drops the threshold, shows everything (for exploration / fine-tuning)
- **"Missed" button**: Appears on sub-threshold articles in "Show all" mode
- **Search**: Full-text search across all articles regardless of score
- **Adding sources**: Just name + feed URL (no JSON config)
- Clean, minimal one-column card layout
- Dark mode (follows system preference)
- Score badge on each card (color-coded: green >= 7, yellow >= 4, gray < 4)
- Toast notifications for actions

## Deployment

- Hetzner server with existing nginx reverse proxy
- User systemd unit (no root needed)
- Configurable port via `PORT` env var
- Credentials via `.env` file
- SQLite backup via daily cron
