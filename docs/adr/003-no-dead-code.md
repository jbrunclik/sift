# ADR-003: No dead code — delete and reimplement

## Status
Accepted

## Context
Early implementation created source plugins for Hacker News and YouTube before they were needed. They were importable but unused, creating maintenance burden and false confidence in the roadmap.

## Decision
Don't keep code for features that aren't active. Delete it. When the feature is needed, reimplement it — it'll be better the second time anyway.

## Consequences
- Codebase stays honest about what actually works
- Roadmap and docs stay accurate
- Slightly more work when enabling a source later, but cleaner in the meantime
