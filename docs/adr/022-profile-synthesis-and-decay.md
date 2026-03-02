# ADR-022: Profile Synthesis and Decay

## Status
Accepted

## Context
Tag weights accumulated indefinitely with no natural attenuation. The prose profile was manually maintained and never automatically updated. Cold-start users had no way to seed initial preferences. Tag quality was unmeasured — there was no way to identify tags that correlate with both positive and negative feedback (noisy tags).

## Decision

### Weight Decay
- Apply multiplicative decay (factor=0.995) to all tag weights during synthesis
- Prune weights below ±0.01 absolute value
- Pure function in `backend/preferences/decay.py`

### Profile Synthesis
- Scheduled every `profile_synthesis_interval_hours` (default: 6h)
- Applies decay → fetches recent feedback (50 items, 7 days) → calls Gemini to generate a 2-3 sentence interest description → saves with version bump
- If LLM call fails, existing prose is preserved but decay still applies

### Cold-Start Onboarding
- `POST /api/onboarding` accepts interest list + optional prose profile
- Seeds tag weights at +1.0 per interest tag
- Only works when `profile_version == 0`

### Tag Quality Instrumentation
- `tag_feedback_stats` table tracks positive/negative vote counts per tag
- Noisy tag detection: tags with high disagreement ratio (both positive and negative votes)
- `GET /api/preferences/vocabulary/quality` exposes tag quality report

## Consequences
- Stale preferences naturally fade, keeping the profile responsive to current interests
- Prose profile automatically stays in sync with learned weights
- New users get a functioning profile immediately after onboarding
- Tag quality metrics enable vocabulary curation (removing or splitting ambiguous tags)
