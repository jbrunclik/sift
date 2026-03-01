# Agent Conventions

Rules for AI agents (Claude Code, Copilot, etc.) contributing to this codebase.

## Documentation-alongside-code rule

Every code change must include relevant documentation updates in the same PR. Specifically:

1. **ADRs**: If the change introduces a new architectural decision or reverses an existing one, create or update an ADR in `docs/adr/` and add it to `docs/adr/README.md`.
2. **Roadmap**: If the change completes a roadmap item, check it off in `docs/roadmap.md`. If it adds new planned work, add the item.
3. **CLAUDE.md**: If the change alters conventions, commands, project layout, or the source plugin pattern, update `CLAUDE.md` to match.
4. **MEMORY.md**: Update status lines in `.claude/projects/*/memory/MEMORY.md` when phases are completed or project state changes materially.

## Why

Documentation drift is the #1 cause of agent confusion on subsequent sessions. Keeping docs in sync with code means the next agent (or human) starts with accurate context instead of stale assumptions.

## Checklist for PRs

Before marking a PR ready for review, verify:

- [ ] `docs/roadmap.md` reflects any completed or newly planned items
- [ ] New architectural decisions have an ADR
- [ ] `docs/adr/README.md` index is up to date
- [ ] `CLAUDE.md` matches current conventions and commands
- [ ] No dead documentation referencing removed features
