# ADR-008: Conventional Commits

## Status
Accepted

## Context
Need a consistent commit message format, especially since both humans and AI agents will be committing.

## Decision
Use [Conventional Commits](https://www.conventionalcommits.org/). Format: `<type>(<scope>): <description>`. Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`, `perf`, `style`.

## Consequences
- Consistent, parseable commit history
- Easy to generate changelogs later if needed
- The `/commit` Claude skill enforces this format
