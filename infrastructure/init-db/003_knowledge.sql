-- ============================================================
-- FILE: 003_knowledge.sql
-- SCHEMA: KNOWLEDGE
-- Contains: Documents, Chunks, Processing jobs
-- ============================================================
-- Single source of truth for knowledge schema.
-- All columns defined upfront - no ALTER statements needed.
-- Uses VECTOR(1024) for BGE-M3 embedding model.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE knowledge.file_type AS ENUM ('PDF', 'DOCX', 'XLSX', 'DOC', 'XLS', 'TXT', 'PNG', 'JPG', 'JPEG', 'MD', 'UNKNOWN');

CREATE TYPE knowledge.processing_status AS ENUM (
    'STAGING', 'UPLOADED', 'PARSING', 'PARSED', 'CHUNKING', 'CHUNKED',
    'EMBEDDING', 'EMBEDDED', 'INDEXING', 'INDEXED', 'READY', 'FAILED'
);

CREATE TYPE knowledge.processing_step AS ENUM ('UPLOAD', 'PARSE', 'CHUNK', 'EMBED', 'INDEX');

CREATE TYPE knowledge.chunking_strategy AS ENUM ('RECURSIVE', 'SEMANTIC', 'FIXED_SIZE', 'SENTENCE');

CREATE TYPE knowledge.embedding_model AS ENUM ('TEXT_EMBEDDING_3_SMALL', 'TEXT_EMBEDDING_3_LARGE', 'MULTILINGUAL_E5_LARGE', 'BGE_M3');

CREATE TYPE knowledge.chunk_type AS ENUM ('parent', 'child');

CREATE TYPE knowledge.content_quality AS ENUM ('HIGH', 'MEDIUM', 'LOW', 'REDIRECT');

-- ============================================================
-- TABLE: knowledge.documents
-- ============================================================
CREATE TABLE knowledge.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    original_filename VARCHAR(500) NOT NULL,
    file_type knowledge.file_type NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(255) NOT NULL,

    file_key VARCHAR(500) NOT NULL,
    bucket_name VARCHAR(100) NOT NULL DEFAULT 'poliwise-documents',

    status knowledge.processing_status NOT NULL DEFAULT 'UPLOADED',
    current_version INT NOT NULL DEFAULT 1,

    extracted_text TEXT,
    page_count INT,
    word_count INT,
    language VARCHAR(10),

    domain VARCHAR(50),
    content_quality knowledge.content_quality,

    ocr_required BOOLEAN DEFAULT FALSE,
    ocr_confidence DECIMAL(5,4),

    chunking_strategy knowledge.chunking_strategy DEFAULT 'RECURSIVE',
    chunk_size INT DEFAULT 1000,
    chunk_overlap INT DEFAULT 200,
    embedding_model knowledge.embedding_model DEFAULT 'BGE_M3',

    uploaded_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    trace_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT chk_file_size CHECK (file_size_bytes > 0 AND file_size_bytes <= 52428800),
    CONSTRAINT chk_version CHECK (current_version >= 1)
);

-- ============================================================
-- TABLE: knowledge.document_versions
-- ============================================================
CREATE TABLE knowledge.document_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    version_number INT NOT NULL,

    file_key VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    document_type VARCHAR(50),  -- Added for ingestion-service compatibility
    changelog TEXT,
    extracted_text TEXT,
    is_current BOOLEAN DEFAULT FALSE,

    -- Redundancy detection fields (V2 additions baked in)
    file_checksum VARCHAR(64),
    content_hash VARCHAR(64),
    similarity_to_previous FLOAT,
    fingerprint_embedding VECTOR(1024),

    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,
    deleted_by UUID,
    deletion_reason TEXT,

    CONSTRAINT uq_document_version UNIQUE (document_id, version_number),
    CONSTRAINT chk_version_number CHECK (version_number >= 1)
);

-- ============================================================
-- TABLE: knowledge.chunks
-- ============================================================
CREATE TABLE knowledge.chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    document_version_id UUID REFERENCES knowledge.document_versions(id) ON DELETE CASCADE,
    document_version INT NOT NULL,

    chunk_index INT NOT NULL,
    chunk_type knowledge.chunk_type DEFAULT 'parent',

    content TEXT NOT NULL,
    content_length INT NOT NULL,
    content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    token_count INT,

    page_number INT,
    start_char_index INT,
    end_char_index INT,

    embedding_model knowledge.embedding_model,
    embedding_dimension INT,
    vector_indexed BOOLEAN DEFAULT FALSE,
    vector_id VARCHAR(100),
    embedding_vector VECTOR(1024),

    -- Denormalized metadata for filtering
    department_id UUID,
    document_type VARCHAR(50),
    effective_date DATE,
    expiry_date DATE,

    -- GitLab Handbook hierarchical section metadata (V2 additions baked in)
    section_title VARCHAR(500),
    section_level INT,
    section_path TEXT[],
    parent_chunk_id UUID REFERENCES knowledge.chunks(id) ON DELETE SET NULL,

    -- Access control (pre-flattened for fast vector search)
    allowed_roles core.user_role[],
    allowed_departments UUID[],
    allowed_users UUID[],
    access_level VARCHAR(20) DEFAULT 'PUBLIC',

    is_latest BOOLEAN DEFAULT TRUE,

    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_chunk_index CHECK (chunk_index >= 0),
    CONSTRAINT chk_content_length CHECK (content_length > 0)
);

-- ============================================================
-- TABLE: knowledge.processing_jobs
-- ============================================================
CREATE TABLE knowledge.processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    document_version_id UUID REFERENCES knowledge.document_versions(id) ON DELETE SET NULL,

    job_type knowledge.processing_step NOT NULL,
    status knowledge.processing_status NOT NULL DEFAULT 'UPLOADED',

    progress_percent INT DEFAULT 0 CHECK (progress_percent >= 0 AND progress_percent <= 100),

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    success BOOLEAN,
    error_message TEXT,
    error_details JSONB,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,

    output_metrics JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- TABLE: knowledge.document_audit_logs
-- ============================================================
CREATE TABLE knowledge.document_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID,
    action VARCHAR(100) NOT NULL,
    actor_id UUID,
    actor_username VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_document_audit_logs_document_id ON knowledge.document_audit_logs(document_id);
CREATE INDEX idx_document_audit_logs_actor_id ON knowledge.document_audit_logs(actor_id);
CREATE INDEX idx_document_audit_logs_action ON knowledge.document_audit_logs(action);
CREATE INDEX idx_document_audit_logs_created_at ON knowledge.document_audit_logs(created_at DESC);

COMMENT ON TABLE knowledge.document_audit_logs IS 'Audit trail for document operations including OnlyOffice editing and conflict resolution';

-- ============================================================
-- TABLE: knowledge.embedding_cache
-- ============================================================
CREATE TABLE knowledge.embedding_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    text_hash VARCHAR(64) NOT NULL,
    text_length INT NOT NULL,

    embedding_model knowledge.embedding_model NOT NULL,
    embedding_dimension INT NOT NULL,
    embedding_vector VECTOR(1024) NOT NULL,

    usage_count INT DEFAULT 1,
    last_used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_embedding_cache UNIQUE (text_hash, embedding_model)
);

-- ============================================================
-- INDEXES: Knowledge schema (basic non-AI indexes only)
-- ============================================================
CREATE INDEX idx_knowledge_documents_status ON knowledge.documents(status);
CREATE INDEX idx_knowledge_documents_file_type ON knowledge.documents(file_type);
CREATE INDEX idx_knowledge_documents_uploaded_by ON knowledge.documents(uploaded_by);
CREATE INDEX idx_knowledge_documents_deleted_at ON knowledge.documents(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_knowledge_documents_trace_id ON knowledge.documents(trace_id);
CREATE INDEX idx_knowledge_documents_domain ON knowledge.documents(domain);
CREATE INDEX idx_knowledge_documents_content_quality ON knowledge.documents(content_quality);
CREATE INDEX idx_knowledge_documents_expires_at ON knowledge.documents(expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX idx_knowledge_document_versions_document_id ON knowledge.document_versions(document_id);
CREATE INDEX idx_knowledge_document_versions_is_current ON knowledge.document_versions(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_knowledge_document_versions_deleted_at ON knowledge.document_versions(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_versions_file_checksum ON knowledge.document_versions(file_checksum) WHERE file_checksum IS NOT NULL;
CREATE INDEX idx_versions_content_hash ON knowledge.document_versions(content_hash) WHERE content_hash IS NOT NULL;

CREATE INDEX idx_knowledge_chunks_document_id ON knowledge.chunks(document_id);
CREATE INDEX idx_knowledge_chunks_document_version_id ON knowledge.chunks(document_version_id);
CREATE INDEX idx_knowledge_chunks_vector_indexed ON knowledge.chunks(vector_indexed) WHERE vector_indexed = TRUE;
CREATE INDEX idx_knowledge_chunks_vector_id ON knowledge.chunks(vector_id) WHERE vector_id IS NOT NULL;
CREATE INDEX idx_knowledge_chunks_department_id ON knowledge.chunks(department_id);
CREATE INDEX idx_knowledge_chunks_is_latest ON knowledge.chunks(is_latest) WHERE is_latest = TRUE;
CREATE INDEX idx_knowledge_chunks_deleted_at ON knowledge.chunks(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_knowledge_chunks_chunk_type ON knowledge.chunks(chunk_type);
CREATE INDEX idx_knowledge_chunks_section_level ON knowledge.chunks(section_level);
CREATE INDEX idx_chunks_content_tsv ON knowledge.chunks USING GIN (content_tsv);

CREATE INDEX idx_knowledge_processing_jobs_document_id ON knowledge.processing_jobs(document_id);
CREATE INDEX idx_knowledge_processing_jobs_document_version_id ON knowledge.processing_jobs(document_version_id);
CREATE INDEX idx_knowledge_processing_jobs_status ON knowledge.processing_jobs(status);
CREATE INDEX idx_knowledge_processing_jobs_deleted_at ON knowledge.processing_jobs(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_knowledge_embedding_cache_hash ON knowledge.embedding_cache(text_hash);
CREATE INDEX idx_knowledge_embedding_cache_last_used ON knowledge.embedding_cache(last_used_at DESC);

-- ============================================================
-- COMMENTS
-- ============================================================
COMMENT ON TABLE knowledge.documents IS 'Master document storage with MinIO reference';
COMMENT ON TABLE knowledge.document_versions IS 'Immutable version history with redundancy detection';
COMMENT ON TABLE knowledge.chunks IS 'Text chunks with VECTOR(1024) embeddings for RAG';
COMMENT ON TABLE knowledge.processing_jobs IS 'ETL pipeline job tracking';
COMMENT ON TABLE knowledge.embedding_cache IS 'Cache for embedding vectors to reduce API costs';
