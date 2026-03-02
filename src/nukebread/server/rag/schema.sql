-- NukeBread Comp Pattern Library Schema
-- Requires: PostgreSQL 16+ with pgvector (or RuVector extension)

CREATE EXTENSION IF NOT EXISTS vector;

-- Core pattern metadata
CREATE TABLE comp_patterns (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    subcategory     TEXT,
    use_cases       TEXT[],
    prerequisites   TEXT[],
    node_classes    TEXT[] NOT NULL,
    node_count      INTEGER NOT NULL,
    source_script   TEXT,
    connections_summary TEXT,
    source_type     TEXT NOT NULL DEFAULT 'manual',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedup index: prevent re-importing the same script twice
CREATE UNIQUE INDEX idx_patterns_name_source ON comp_patterns (name, source_script)
    WHERE source_script IS NOT NULL;

-- Full node graph snapshots (separated to avoid bloating search queries)
CREATE TABLE pattern_graphs (
    id              SERIAL PRIMARY KEY,
    pattern_id      INTEGER NOT NULL REFERENCES comp_patterns(id) ON DELETE CASCADE,
    graph_json      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pattern_id)
);

-- Embedded text chunks for vector search
CREATE TABLE pattern_chunks (
    id              SERIAL PRIMARY KEY,
    pattern_id      INTEGER NOT NULL REFERENCES comp_patterns(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(768),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User ratings for learning what works
CREATE TABLE pattern_ratings (
    id              SERIAL PRIMARY KEY,
    pattern_id      INTEGER NOT NULL REFERENCES comp_patterns(id) ON DELETE CASCADE,
    success         BOOLEAN NOT NULL,
    score           INTEGER CHECK (score BETWEEN 1 AND 5),
    notes           TEXT,
    rated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Flexible tagging
CREATE TABLE pattern_tags (
    id              SERIAL PRIMARY KEY,
    pattern_id      INTEGER NOT NULL REFERENCES comp_patterns(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    UNIQUE (pattern_id, tag)
);

-- Vector index (HNSW for fast approximate nearest neighbor search)
CREATE INDEX idx_chunks_embedding ON pattern_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Filtering indexes
CREATE INDEX idx_patterns_category ON comp_patterns (category);
CREATE INDEX idx_patterns_node_classes ON comp_patterns USING GIN (node_classes);
CREATE INDEX idx_patterns_source_type ON comp_patterns (source_type);
CREATE INDEX idx_tags_tag ON pattern_tags (tag);
CREATE INDEX idx_chunks_pattern_id ON pattern_chunks (pattern_id);
CREATE INDEX idx_ratings_pattern_id ON pattern_ratings (pattern_id);
