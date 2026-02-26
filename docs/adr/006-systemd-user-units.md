# ADR-006: User systemd units for deployment

## Status
Accepted

## Context
The Hetzner server already has nginx as a reverse proxy. Need a way to run the Sift backend, and later scheduled tasks (fetching, scoring, backup).

## Decision
Use user-level systemd units (`systemctl --user`). The web server runs as a service. Fetching, scoring, and backup will run as systemd timers (replacing the in-process APScheduler).

## Consequences
- No root access needed
- Timers are more reliable than in-process schedulers (survive crashes)
- Visible via standard `systemctl` and `journalctl` commands
- Port and host are read from `.env` via `EnvironmentFile`
