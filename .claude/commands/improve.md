Analyze this entire conversation and learn from every correction the user made.

Go through the full session history and identify every instance where the user:
- Corrected a mistake or wrong assumption
- Pushed back on a decision or approach
- Expressed a preference (explicit or implicit)
- Asked for something to be removed, changed, or done differently
- Clarified the product vision or intent

For each correction found, determine the underlying lesson — not just the surface fix, but the general principle. For example:
- "Remove dead code" → principle: don't keep unused code around for hypothetical future use
- "I just want to enter a URL, not JSON" → principle: optimize for human UX, not developer convenience
- "I only want cream of the crop" → principle: the product filters FOR the user, not shows everything

Then persist these lessons by updating the appropriate files:
- **`CLAUDE.md`** — coding conventions, architectural principles, workflow preferences
- **`.claude/agents/*.md`** — agent instructions that should reflect these lessons
- **`.claude/commands/*.md`** — skill definitions that should be adjusted
- **`docs/product-spec.md`** — product vision and design principles
- **Auto-memory `MEMORY.md`** — user preferences and working style

Also check: are there any corrections from this session that were applied to specific code but NOT yet captured in the docs/config? If so, codify them now.

Finally, summarize: list each lesson learned and where it was saved.
