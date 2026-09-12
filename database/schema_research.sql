-- =====================================================
-- Research Papers Table
-- =====================================================
-- Stores arXiv papers with AI-generated analysis.
-- Run this in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS research_papers (
    id BIGSERIAL PRIMARY KEY,
    arxiv_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    authors TEXT[],                      -- Array of author names
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    pdf_url TEXT,
    abs_url TEXT,
    primary_category TEXT,              -- e.g., 'cs.AI'
    category_name TEXT,                 -- e.g., 'Artificial Intelligence'
    priority INTEGER DEFAULT 3,         -- 1=AI/ML, 2=Core Tech, 3=Broader
    all_categories TEXT[],              -- All arXiv tags
    analysis JSONB DEFAULT '{}'::jsonb, -- Gemini-generated analysis
    is_analyzed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_papers_category ON research_papers(primary_category);
CREATE INDEX IF NOT EXISTS idx_papers_priority ON research_papers(priority);
CREATE INDEX IF NOT EXISTS idx_papers_published ON research_papers(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_analyzed ON research_papers(is_analyzed);

-- RLS Policies (required for anon key access)
ALTER TABLE research_papers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all on research_papers" ON research_papers
    FOR ALL USING (true) WITH CHECK (true);
