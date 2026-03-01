-- Backfill: articles with non-zero feedback should be marked as read.
-- This covers articles rated before the vote-marks-as-read feature was added.
UPDATE articles SET is_read = 1
WHERE id IN (SELECT article_id FROM feedback WHERE rating != 0)
  AND is_read = 0;

-- Track scoring retry attempts to avoid infinite retry loops.
ALTER TABLE articles ADD COLUMN score_attempts INTEGER NOT NULL DEFAULT 0;
