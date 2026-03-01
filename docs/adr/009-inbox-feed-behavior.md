# ADR-009: Inbox feed behavior

## Status
Accepted

## Context
The curated feed (ADR-001) shows high-relevance articles, but it behaves like a static list. Users see articles they have already acted on, which adds cognitive load. The feed should behave like an inbox: surface what needs attention, then get out of the way.

## Decision
The feed defaults to showing **unread + curated** articles. Articles exit the feed when the user votes (thumbs up/down), marks as read, or hides them. Exits are animated (slide-out) to give a satisfying "clearing the deck" feel.

Key behaviors:
- **Default view**: unread articles with score >= threshold (curated). No voted or read articles.
- **Vote/read/hide** removes the card with a CSS slide-out animation (~200ms).
- **Undo toast**: every exit action shows an undo toast (3 seconds) that reverses the action.
- **Training mode toggle**: switches to "Show all" mode where sub-threshold articles appear with "Missed" buttons. Training mode is sticky per session but not persisted.

## Consequences
- The feed naturally empties as the user works through it, giving a clear "done" state
- Undo support prevents accidental dismissals from being frustrating
- Animation makes bulk triage feel responsive rather than jarring
- "Training mode" keeps the fine-tuning workflow separate from daily reading
- The read/unread state becomes load-bearing; bugs there affect the entire UX
