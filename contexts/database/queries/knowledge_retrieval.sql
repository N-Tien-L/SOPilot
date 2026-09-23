-- ============================================================
-- KNOWLEDGE SCHEMA RETRIEVAL SCRIPTS
-- Purpose: Querying documents, chunks, and vector similarity
-- ============================================================

-- 1. Check document processing status
SELECT 
    original_filename, 
    status, 
    current_version, 
    chunking_strategy,
    created_at
FROM knowledge.documents
ORDER BY created_at DESC;

-- 2. Find latest version of a document
-- Replace :doc_id with actual UUID
SELECT * 
FROM knowledge.document_versions
WHERE document_id = 'REPLACE_WITH_UUID'
ORDER BY version_number DESC
LIMIT 1;

-- 3. Vector Similarity Search (pgvector)
-- Note: Replace the array with your actual embedding vector
SELECT 
    id, 
    content, 
    chunk_index,
    embedding_vector <=> '[0.1, 0.2, ...]'::vector as distance
FROM knowledge.chunks
WHERE is_latest = TRUE
ORDER BY distance ASC
LIMIT 5;

-- 4. Keyword search (Full-text searching)
SELECT 
    id, 
    content, 
    ts_rank(content_tsv, websearch_to_tsquery('english', 'policy resignation')) as rank
FROM knowledge.chunks
WHERE content_tsv @@ websearch_to_tsquery('english', 'policy resignation')
  AND is_latest = TRUE
ORDER BY rank DESC;

-- 5. List all chunks for a specific document version
SELECT chunk_index, content
FROM knowledge.chunks
WHERE document_id = 'REPLACE_WITH_UUID' AND is_latest = TRUE
ORDER BY chunk_index ASC;

-- 6. Check pending ingestion jobs
SELECT * FROM knowledge.processing_jobs 
WHERE status NOT IN ('READY', 'FAILED')
ORDER BY created_at DESC;
