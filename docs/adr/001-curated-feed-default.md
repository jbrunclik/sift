# ADR-001: Curated feed as default view

## Status
Accepted

## Context
The whole point of Sift is to eliminate the 15-minute daily scanning ritual. Showing all fetched articles defeats the purpose — it's just another firehose.

## Decision
The default feed shows only articles with a relevance score >= 7.0. Everything else is filtered out. Users can toggle "Show all" to explore and fine-tune, and mark articles as "Missed" to correct the filter.

## Consequences
- The feed is empty until the scoring pipeline is running
- The "Missed" button becomes a critical feedback mechanism for training
- The threshold (7.0) is hardcoded for now but could become configurable per user
