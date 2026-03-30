CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    url_hash CHAR(32) NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    source VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    language VARCHAR(10) NOT NULL,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_summary_ja TEXT,
    llm_summary_zh TEXT,
    embedding VECTOR(1536),
    CONSTRAINT chk_news_articles_category
        CHECK (category IN ('immigration', 'ai_tech', 'language_learning')),
    CONSTRAINT chk_news_articles_language
        CHECK (language IN ('en', 'ja'))
);

CREATE TABLE IF NOT EXISTS etl_run_log (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    category VARCHAR(50) NOT NULL,
    source VARCHAR(100) NOT NULL,
    fetched_count INT NOT NULL DEFAULT 0,
    inserted_count INT NOT NULL DEFAULT 0,
    updated_count INT NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_news_articles_url_hash
    ON news_articles (url_hash);

CREATE INDEX IF NOT EXISTS idx_news_articles_category_published_at
    ON news_articles (category, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_articles_published_at
    ON news_articles (published_at DESC);
