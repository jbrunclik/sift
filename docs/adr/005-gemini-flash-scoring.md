# ADR-005: Gemini Flash for article scoring

## Status
Accepted

## Context
Each article needs a relevance score, summary, explanation, and tags. This requires an LLM. Options: OpenAI, Claude, Gemini, local models.

## Decision
Use Gemini 3 Flash Preview (`gemini-3-flash-preview`) via the `google-genai` SDK. Model is configurable via `GEMINI_MODEL` env var.

## Consequences
- Cheap and fast — important since we score every article individually
- Structured JSON output for reliable parsing
- Model-agnostic config makes it easy to swap later
- Requires a `GEMINI_API_KEY` in `.env`
