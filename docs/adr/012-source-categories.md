# ADR-012: Free-text source categories

## Status
Accepted

## Context
As the number of sources grows, users need a way to organize them. Rigid preset categories ("Tech", "News", "Finance") never match everyone's mental model. Categories should emerge from use, not be imposed.

## Decision
Add a nullable `category` column to the `sources` table. Categories are free-text strings assigned by the user. The frontend provides autocomplete suggestions drawn from existing categories (`SELECT DISTINCT category FROM sources WHERE category IS NOT NULL`). No preset list, no enum, no validation beyond max length.

The feed page gets a category filter dropdown populated from the same distinct query.

## Consequences
- Zero-config: users who don't care about categories are unaffected (column is nullable)
- Autocomplete encourages reuse without enforcing it
- Typos can create duplicate categories (e.g., "Tech" vs "tech") -- mitigated by case-insensitive autocomplete matching
- No migration needed beyond adding the column with a default of NULL
- Category renames require updating all matching sources (simple UPDATE query)
