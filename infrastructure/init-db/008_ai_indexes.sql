-- ============================================================
-- FILE: 008_ai_indexes.sql
-- ALL SCHEMAS
-- Contains: pgvector HNSW indexes, GIN text search, BM25 setup
-- ============================================================
-- MUST run AFTER all tables are created.
-- All indexes defined in one place for clarity.
-- Uses VECTOR(1024) for BGE-M3 embedding model.
-- ============================================================

-- ============================================================
-- KNOWLEDGE SCHEMA: Vector and Text Search Indexes
-- ============================================================

-- HNSW vector similarity search (cosine distance)
-- For embedding_vector VECTOR(1024) with BGE-M3 model
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON knowledge.chunks
    USING hnsw (embedding_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- NOTE: content_tsv columns already exist as GENERATED columns in:
--   - knowledge.chunks (003_knowledge.sql line 126)
--   - conversation.messages (004_conversation.sql line 45)
-- Indexes below are just recreating GIN indexes (dropped and recreated for clarity)

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv
    ON knowledge.chunks USING GIN (content_tsv);

-- Section path for GitLab Handbook hierarchical filtering
CREATE INDEX IF NOT EXISTS idx_chunks_section_path
    ON knowledge.chunks USING GIN (section_path);

-- ============================================================
-- KNOWLEDGE SCHEMA: ACL Filtering Indexes (GIN for arrays)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_chunks_allowed_roles
    ON knowledge.chunks USING GIN (allowed_roles);

CREATE INDEX IF NOT EXISTS idx_chunks_allowed_departments
    ON knowledge.chunks USING GIN (allowed_departments);

CREATE INDEX IF NOT EXISTS idx_chunks_allowed_users
    ON knowledge.chunks USING GIN (allowed_users);

-- ============================================================
-- KNOWLEDGE SCHEMA: Composite Indexes for Common Queries
-- ============================================================

-- Most common query pattern: latest child chunks for vector search
CREATE INDEX IF NOT EXISTS idx_chunks_search_filters
    ON knowledge.chunks (is_latest, chunk_type, document_id)
    WHERE is_latest = TRUE AND chunk_type = 'child';

-- Unique constraint for idempotent chunk insertion
CREATE UNIQUE INDEX IF NOT EXISTS uniq_chunk_per_version
    ON knowledge.chunks (document_version_id, chunk_index, chunk_type);

-- ============================================================
-- KNOWLEDGE SCHEMA: GIN indexes for JSONB metadata
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin
    ON knowledge.chunks USING GIN (metadata);

-- ============================================================
-- KNOWLEDGE SCHEMA: Document metadata join optimization
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_document_metadata_document
    ON metadata.document_metadata (document_id) WHERE deleted_at IS NULL;

-- ============================================================
-- CONVERSATION SCHEMA: Full-text search on messages
-- ============================================================

-- NOTE: content_tsv column already exists as GENERATED column in conversation.messages (004_conversation.sql line 45)
-- Index below is just recreating GIN index

CREATE INDEX IF NOT EXISTS idx_messages_content_tsv
    ON conversation.messages USING GIN (content_tsv);

-- ============================================================
-- METADATA SCHEMA: Text search indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_tags_name_search
    ON metadata.tags USING gin(to_tsvector('simple', name));

CREATE INDEX IF NOT EXISTS idx_metadata_title_search
    ON metadata.document_metadata USING gin(to_tsvector('simple', title));

CREATE INDEX IF NOT EXISTS idx_categories_name_search
    ON metadata.categories USING gin(to_tsvector('simple', name));

-- ============================================================
-- PERFORMANCE NOTES
-- ============================================================
-- HNSW index build time: ~5-10 min for 1M chunks (during maintenance)
-- GIN indexes: <1 min typically
-- Vector search p99 latency target: <50ms with HNSW (m=16, ef=64)
--
-- Index maintenance:
-- - HNSW: No periodic VACUUM needed, just ANALYZE
-- - GIN: Regular VACUUM ANALYZE recommended
-- - BM25 TSVECTOR: Auto-updated on INSERT/UPDATE, no extra maintenance
-- ============================================================