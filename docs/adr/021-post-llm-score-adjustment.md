# ADR-021: Post-LLM Score Adjustment

## Status
Accepted

## Context
The LLM scoring prompt included user tag weights as context, but the model's interpretation of these weights was inconsistent. Additionally, only positive weights were shown in the prompt — negative weights (topics the user wants to avoid) were invisible to the model. We needed a deterministic mechanism to ensure user preferences have a predictable, immediate effect on article scores.

## Decision
- Split the prompt's tag weights section into **"Strongly prefer"** (top 15 positive) and **"Seen enough / avoid"** (top 10 negative) to give the LLM both positive and negative signals
- Add a deterministic post-LLM score adjustment: `adjusted = raw + Σ(weight × confidence × 0.3)`, clamped to ±1.5 and final score to [0, 10]
- Store `raw_llm_score` alongside the adjusted `relevance_score` (new column via migration 010)
- Add borderline article rescoring: when `profile_version` advances by 5+, recompute adjusted scores for articles with `raw_llm_score` in [5.0, 8.0] published within 7 days (migration 011 for `last_rescore_version`)

## Consequences
- User corrections now have immediate, predictable impact on scores
- The ±1.5 cap prevents weight manipulation from overwhelming LLM judgment
- `raw_llm_score` preservation enables rescoring without re-calling the LLM
- Borderline articles can cross the curated threshold (7.0) when user preferences shift
