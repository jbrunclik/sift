# ADR-017: Managed tag vocabulary for scoring

## Status
Accepted (supersedes ADR-015)

## Context
ADR-015 introduced soft prompt seeding: the top 50 tags by frequency are included in the LLM prompt as a hint. This improved tag reuse but left a fundamental weakness: synonym fragmentation. "machine-learning", "ml", and "deep-learning" remain separate tags. A user upvoting an ML article only boosts one of them, scattering the weight vector across ~200 tags instead of concentrating it on ~50 real topics. The feedback loop converges slowly.

## Decision
Replace soft hints with a **managed vocabulary**:

1. **`is_approved` flag on `tags` table**: Approved tags form the vocabulary. The LLM prompt instructs: "Assign tags ONLY from this list."
2. **New-tag escape hatch**: The LLM can suggest one new tag by prefixing it with `+` (e.g., `+quantum-computing`). These are tracked as candidates.
3. **Auto-promotion**: Candidates appearing in 3+ distinct articles automatically promote to vocabulary.
4. **Fuzzy matching**: `difflib.SequenceMatcher` (threshold 0.85) catches near-misses, mapping them to the closest vocabulary tag.
5. **Manual management**: Users can add, remove, and merge tags via the preferences UI.
6. **Merge operation**: Repoints `article_tags`, transfers tag weight in user profile, deletes source tag.

### Why not alternatives
- **Gemini enum schema enforcement**: Dynamic vocabulary with escape hatch doesn't fit rigid enums.
- **Embedding-based similarity**: Overkill for <200 tags. SequenceMatcher handles it fine.
- **Separate tagging API call**: Doubles cost for marginal improvement.

## Consequences
- Tag weights concentrate on canonical terms; feedback loop converges faster
- Vocabulary section in preferences gives users direct control over their tag space
- Prompt now has a hard constraint ("ONLY from this list") instead of a soft hint
- Tagging instruction comes before scoring instruction to reduce confirmation bias
- New topics still emerge organically via the `+` prefix and auto-promotion
- Migration bootstraps: tags already used in 3+ articles are auto-approved
- Cleanup scheduler preserves approved tags even when orphaned (they are part of the vocabulary)
