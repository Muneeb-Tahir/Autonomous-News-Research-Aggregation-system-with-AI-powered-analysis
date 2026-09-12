-- ============================================================
-- News Intelligence Agent — Database Schema
-- Run this in Supabase SQL Editor (https://supabase.com/dashboard)
-- ============================================================

-- Main articles table
CREATE TABLE IF NOT EXISTS articles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    content TEXT DEFAULT '',
    source_name TEXT NOT NULL,
    source_quality INTEGER DEFAULT 5 CHECK (source_quality BETWEEN 1 AND 10),
    author TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    category TEXT NOT NULL,
    image_url TEXT,
    language TEXT DEFAULT 'en',

    -- Scores (0-100)
    importance_score REAL DEFAULT 0,
    urgency_score REAL DEFAULT 0,
    recency_score REAL DEFAULT 0,
    credibility_score REAL DEFAULT 0,
    final_score REAL DEFAULT 0,

    -- Story grouping
    story_group_id TEXT,
    additional_sources JSONB DEFAULT '[]'::jsonb,

    -- Flags
    is_breaking BOOLEAN DEFAULT FALSE,
    is_processed BOOLEAN DEFAULT FALSE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_articles_collected_at ON articles(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_final_score ON articles(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_is_processed ON articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_articles_story_group ON articles(story_group_id);
CREATE INDEX IF NOT EXISTS idx_articles_is_breaking ON articles(is_breaking);

-- Full-text search index on title + description
CREATE INDEX IF NOT EXISTS idx_articles_search ON articles
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));


-- System status tracking (single row)
CREATE TABLE IF NOT EXISTS system_status (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_collection TIMESTAMPTZ,
    articles_collected INTEGER DEFAULT 0,
    total_articles INTEGER DEFAULT 0,
    sources_checked INTEGER DEFAULT 0,
    sources_failed JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'initializing',
    newsapi_requests_today INTEGER DEFAULT 0,
    newsapi_last_reset DATE DEFAULT CURRENT_DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert initial status row
INSERT INTO system_status (id, status)
VALUES (1, 'initializing')
ON CONFLICT (id) DO NOTHING;


-- Breaking news alert log (prevents duplicate alerts)
CREATE TABLE IF NOT EXISTS alert_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    story_group_id TEXT NOT NULL,
    alerted_at TIMESTAMPTZ DEFAULT NOW(),
    article_title TEXT
);

CREATE INDEX IF NOT EXISTS idx_alert_log_story ON alert_log(story_group_id);
CREATE INDEX IF NOT EXISTS idx_alert_log_time ON alert_log(alerted_at DESC);


-- ============================================================
-- Row Level Security (RLS) Policies
-- Allow the anon key full access (this is a single-user app)
-- ============================================================

-- Articles table
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on articles" ON articles
    FOR ALL USING (true) WITH CHECK (true);

-- System status table
ALTER TABLE system_status ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on system_status" ON system_status
    FOR ALL USING (true) WITH CHECK (true);

-- Alert log table
ALTER TABLE alert_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all on alert_log" ON alert_log
    FOR ALL USING (true) WITH CHECK (true);

-- Re-seed the status row (in case the original INSERT was blocked by RLS)
INSERT INTO system_status (id, status)
VALUES (1, 'initializing')
ON CONFLICT (id) DO NOTHING;
