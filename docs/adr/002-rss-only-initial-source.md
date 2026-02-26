# ADR-002: RSS as the only initial source

## Status
Accepted

## Context
The plan lists 8+ sources (HN, Reddit, YouTube, etc.) but each has different APIs and quirks. Implementing them all upfront delays getting a working system.

## Decision
Ship with RSS only. Add more sources incrementally in Phase 3. Don't keep unfinished source code around — delete and reimplement when the time comes.

## Consequences
- Faster path to a working end-to-end pipeline
- RSS covers many sources already (Feedly, iDNES, any feed)
- Other sources will be added as separate, focused efforts
