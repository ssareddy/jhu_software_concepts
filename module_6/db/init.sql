-- db/init.sql
-- Initializes schema on first stack start.

CREATE TABLE IF NOT EXISTS applicants (
    p_id                  SERIAL PRIMARY KEY,
    content_hash          TEXT UNIQUE,
    program               TEXT,
    comments              TEXT,
    date_added            DATE,
    url                   TEXT UNIQUE,
    status                TEXT,
    term                  TEXT,
    us_or_international   TEXT,
    gpa                   FLOAT,
    gre                   FLOAT,
    gre_v                 FLOAT,
    gre_aw                FLOAT,
    degree                TEXT,
    llm_generated_program     TEXT,
    llm_generated_university  TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_watermarks (
    source      TEXT PRIMARY KEY,
    last_seen   TEXT,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Analytics cache table updated by worker after recompute_analytics task
CREATE TABLE IF NOT EXISTS analytics_cache (
    key         TEXT PRIMARY KEY,
    computed_at TIMESTAMPTZ DEFAULT now()
);