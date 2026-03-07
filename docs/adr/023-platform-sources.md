# ADR-023: Platform sources as singleton discoverable plugins

## Status

Accepted

## Context

Some sources — Hacker News, YouTube, Reddit — are well-known platforms rather than arbitrary user-provided URLs. They deserve a different UX: discoverable cards, singleton enforcement (one HN source, not multiple), structured config forms, and a hook for future OAuth flows.

Two approaches were considered:

1. **Separate platform registry** — a new class hierarchy and registry alongside the existing source system.
2. **Extend BaseSource** — add class-level attributes to the existing `BaseSource` so platform sources are just regular source plugins with extra metadata.

## Decision

Extend `BaseSource` with platform attributes (option 2):

- `is_platform: bool` — distinguishes platform from custom sources
- `platform_description: str` — short human-readable description for the UI card
- `config_fields: list[dict]` — simple form descriptor list for rendering config UI
- `auth_type: str | None` — hook for future OAuth (`None` for HN, `"oauth"` for YouTube)

### Singleton enforcement

Enforced at the API level: `POST /api/sources` returns 409 Conflict if a platform source of the same type already exists. No DB unique constraint needed — the check is simple and the API is the only writer.

### Platform discovery endpoint

`GET /api/sources/platforms` returns platform metadata merged with DB state. Each entry includes the class metadata (`config_fields`, `description`) plus the existing `Source` row if enabled, or `null` if not. This lets the frontend render enabled/disabled state without extra API calls.

### Config fields

A simple form descriptor list (not JSON Schema). Each field has `key`, `label`, `type` (text/number/select), and optional `options`, `min`, `max`, `default`. The frontend renders these into form elements.

### No DB migration needed

Platform sources are stored as regular rows in the existing `sources` table. The `source_type` column distinguishes them. No new tables or columns required.

## Consequences

- Adding a new platform source is just a new Python file with `is_platform = True` and `config_fields`
- The frontend platform grid scales automatically as new platform plugins are registered
- `auth_type` is a no-op for HN but prepares for YouTube OAuth without refactoring
- Singleton enforcement is soft (API-level) — manual DB inserts could bypass it, but that's acceptable for a personal tool
