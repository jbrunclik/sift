# ADR-013: Adaptive fetch intervals

## Status
Accepted

## Context
Fixed fetch intervals waste resources on quiet sources and miss updates on active ones. A source that publishes twice a week does not need 15-minute polling. Conversely, a high-volume feed may warrant more frequent checks.

## Decision
Each source tracks an exponential moving average (EMA) of new articles per fetch. The fetch interval adjusts based on this signal:

- **3 consecutive empty fetches**: double the interval (source is quiet)
- **EMA > 5 articles per fetch**: halve the interval (source is active)
- **EMA between 1 and 5**: increase interval by 50% (sparse but not dead)
- **Hard caps**: minimum 10 minutes, maximum 360 minutes (6 hours)

State is stored in the `sources` table: `fetch_interval_minutes` (current interval), `empty_fetch_streak` (consecutive zeros), `articles_per_fetch_ema` (smoothed average, alpha=0.3).

The scheduler reads each source's interval and schedules accordingly. Manual "Fetch now" resets the empty streak to zero.

## Consequences
- Quiet sources are polled less often, reducing unnecessary network and DB load
- Active sources get faster pickup without manual tuning
- EMA smooths out spikes (e.g., a one-time bulk publish does not permanently halve the interval)
- The 10-minute floor prevents hammering any source
- The 6-hour ceiling ensures no source is effectively abandoned
- Adds three columns to the sources table; straightforward migration
