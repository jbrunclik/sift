# ADR-020: Tag Confidence End-to-End

## Status
Accepted

## Context
The scoring pipeline extracted topic tags from articles but stored them with a fixed confidence of 1.0. The `article_tags.confidence` column existed in the schema but was never populated with real values. This meant the feedback loop's confidence-weighted adjustments had no actual gradation — every tag was treated equally regardless of how well it fit the article.

## Decision
- Add a `TagScore` model (name + confidence) to the scorer, replacing flat string tags
- Update LLM prompts to request confidence values (0.0–1.0) per tag
- Add a `model_validator` on `ScoringResult` to gracefully handle Gemini returning flat strings as fallback (coerced to confidence=1.0)
- Store real confidence values in `article_tags.confidence` via the pipeline
- Clamp confidence to [0.0, 1.0] during normalization

## Consequences
- Tag weights in the feedback loop now properly scale by confidence (e.g., a 0.5-confidence tag contributes half the delta)
- Existing data retains confidence=1.0 (no migration needed — the column already has DEFAULT 1.0)
- The scoring prompt is slightly larger, but Gemini handles the structured output well
