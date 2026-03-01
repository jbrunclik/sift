-- Track article content extraction status
ALTER TABLE articles ADD COLUMN extraction_status TEXT DEFAULT NULL;
-- NULL = not attempted, 'success', 'failed', 'skipped'
ALTER TABLE articles ADD COLUMN extraction_attempted_at TEXT DEFAULT NULL;

CREATE INDEX idx_articles_extraction ON articles(extraction_status)
    WHERE content_full IS NULL;
