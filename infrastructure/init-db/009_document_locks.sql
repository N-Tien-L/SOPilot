-- ============================================================
-- FILE: 009_document_locks.sql
-- SCHEMA: KNOWLEDGE
-- Contains: Document edit locks for OnlyOffice integration
-- ============================================================
-- One lock per document. A lock records who is editing, which
-- version was locked, and when the lock expires (auto-release).
-- ============================================================


-- ============================================================
-- TABLE: knowledge.document_version_deletions
-- Track which version was deleted (for audit / rollback safety)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge.document_version_deletions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id      UUID NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    version_number   INT NOT NULL,
    deleted_by       UUID NOT NULL,
    deleted_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Snapshot of the deleted version for recovery
    file_key         VARCHAR(500),
    file_size_bytes  BIGINT,
    changelog        TEXT,
    extracted_text   TEXT,

    CONSTRAINT uq_version_deletion UNIQUE (document_id, version_number)
);

COMMENT ON TABLE knowledge.document_version_deletions IS 'Soft-delete archive for document versions — allows recovery of accidentally deleted versions';
