CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title,
    content_snippet,
    summary,
    content='articles',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER articles_fts_insert AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, content_snippet, summary)
    VALUES (new.id, new.title, new.content_snippet, new.summary);
END;

CREATE TRIGGER articles_fts_update AFTER UPDATE OF title, content_snippet, summary ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_snippet, summary)
    VALUES ('delete', old.id, old.title, old.content_snippet, old.summary);
    INSERT INTO articles_fts(rowid, title, content_snippet, summary)
    VALUES (new.id, new.title, new.content_snippet, new.summary);
END;

CREATE TRIGGER articles_fts_delete AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_snippet, summary)
    VALUES ('delete', old.id, old.title, old.content_snippet, old.summary);
END;
