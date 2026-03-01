# ADR-015: Tag consistency via LLM prompt seeding

## Status
Accepted

## Context
Gemini generates tags for each article independently. Without guidance, it invents synonyms and variations: "machine-learning" vs "ML" vs "machine learning", "javascript" vs "JS" vs "JavaScript". This fragments tag weights and weakens the feedback loop.

## Decision
Before each scoring batch, query the top 50 tags by frequency (`SELECT tag, COUNT(*) ... ORDER BY cnt DESC LIMIT 50`). Include this list in the Gemini scoring prompt with an instruction: "Prefer reusing these existing tags when applicable. Only create new tags when no existing tag fits."

The tag list is refreshed per batch, so it evolves naturally as the corpus grows. No hard enforcement -- the LLM can still create new tags when genuinely needed.

## Consequences
- Tag reuse improves dramatically, making tag weights more meaningful for scoring adjustments
- The feedback loop converges faster because votes on "python" apply to all Python articles, not split across variants
- Adds one lightweight query per scoring batch (top 50 tags) -- negligible cost
- Prompt grows by ~200 tokens for the tag list -- well within Gemini context limits
- New topics still get new tags; the system is not locked to a fixed vocabulary
- Over time the tag vocabulary stabilizes, but the 50-tag window naturally adapts as interests shift
