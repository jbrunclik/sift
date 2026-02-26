CREATE TABLE sources (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    slug                    TEXT NOT NULL UNIQUE,
    source_type             TEXT NOT NULL,
    config_json             TEXT NOT NULL DEFAULT '{}',
    enabled                 INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes  INTEGER NOT NULL DEFAULT 30,
    last_fetched_at         TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE articles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id       TEXT,
    url               TEXT NOT NULL,
    url_normalized    TEXT NOT NULL,
    title             TEXT NOT NULL,
    author            TEXT,
    content_snippet   TEXT,
    content_full      TEXT,
    published_at      TEXT,
    fetched_at        TEXT NOT NULL DEFAULT (datetime('now')),
    relevance_score   REAL,
    score_explanation  TEXT,
    summary           TEXT,
    scored_at         TEXT,
    language          TEXT DEFAULT 'en',
    image_url         TEXT,
    extra_json        TEXT DEFAULT '{}',
    is_read           INTEGER NOT NULL DEFAULT 0,
    is_hidden         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id, url_normalized)
);

CREATE INDEX idx_articles_score ON articles(relevance_score DESC);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_url_norm ON articles(url_normalized);

CREATE TABLE feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    confidence REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (article_id, tag_id)
);

CREATE TABLE user_profile (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    tag_weights_json TEXT NOT NULL DEFAULT '{}',
    prose_profile    TEXT NOT NULL DEFAULT '',
    interests_json   TEXT NOT NULL DEFAULT '[]',
    profile_version  INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO user_profile (id) VALUES (1);

CREATE TABLE fetch_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at   TEXT,
    status        TEXT NOT NULL DEFAULT 'running',
    items_found   INTEGER DEFAULT 0,
    items_new     INTEGER DEFAULT 0,
    error_message TEXT,
    duration_ms   INTEGER
);
