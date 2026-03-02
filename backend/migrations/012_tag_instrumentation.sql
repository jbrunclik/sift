CREATE TABLE IF NOT EXISTS tag_feedback_stats (
    tag_id INTEGER PRIMARY KEY REFERENCES tags(id) ON DELETE CASCADE,
    positive_votes INTEGER NOT NULL DEFAULT 0,
    negative_votes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
