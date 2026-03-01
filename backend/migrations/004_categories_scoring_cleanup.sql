-- Source categories + adaptive fetch stats
ALTER TABLE sources ADD COLUMN category TEXT NOT NULL DEFAULT '';
ALTER TABLE sources ADD COLUMN avg_articles_per_fetch REAL DEFAULT 0;
ALTER TABLE sources ADD COLUMN consecutive_empty_fetches INTEGER DEFAULT 0;

-- Scoring cost tracking
CREATE TABLE IF NOT EXISTS scoring_logs (
    id INTEGER PRIMARY KEY,
    batch_size INTEGER NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    model TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    scored_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Scheduler run tracking
CREATE TABLE IF NOT EXISTS scheduler_runs (
    id INTEGER PRIMARY KEY,
    job_name TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    details TEXT DEFAULT '',
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_scheduler_runs_job ON scheduler_runs (job_name, started_at DESC);
