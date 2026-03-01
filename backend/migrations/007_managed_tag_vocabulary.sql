-- Managed tag vocabulary: approved tags form the LLM constraint set,
-- candidates auto-promote after appearing in 3+ distinct articles.

ALTER TABLE tags ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0;

CREATE TABLE tag_candidates (
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    PRIMARY KEY (tag_id, article_id)
);

-- Bootstrap: auto-approve tags already used in 3+ articles
UPDATE tags SET is_approved = 1
WHERE id IN (
    SELECT tag_id FROM article_tags GROUP BY tag_id HAVING COUNT(DISTINCT article_id) >= 3
);
