# ADR-011: LLM cost tracking

## Status
Accepted

## Context
Gemini Flash is cheap but not free. Without visibility into token usage, costs can silently grow as more sources are added or batch sizes increase. We need per-batch cost tracking to catch surprises early.

## Decision
Track LLM costs in a `scoring_logs` table with columns: `id`, `scored_at`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `batch_size`, `duration_ms`.

Token counts come from `response.usage_metadata` returned by the `google-genai` SDK. Cost is computed by multiplying token counts against per-model pricing defined in `backend/scoring/pricing.py`. This file contains a simple dict mapping model names to per-token input/output rates, updated manually when pricing changes.

The stats API and frontend stats page surface cumulative and per-day cost breakdowns.

## Consequences
- Full visibility into daily/weekly LLM spend with no external tooling
- `pricing.py` must be updated when Google changes pricing or we switch models
- Token metadata is always available in Gemini responses, so no extra API calls needed
- The `scoring_logs` table grows linearly with scoring batches (one row per batch) -- negligible storage
- Cost data enables informed decisions about batch size tuning and model selection
