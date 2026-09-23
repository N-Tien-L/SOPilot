---
title: Knowledge Schema Tables
description: Database tables for the knowledge schema (knowledge-service and ingestion-service ownership)
schema: knowledge
owner: knowledge-service, ingestion-service
---

# Knowledge Schema Tables

**Owner Services**: `knowledge-service` (reads), `ingestion-service` (writes)  
**Purpose**: Document storage, versioning, chunking, and vector embeddings for AI search

---

## Critical Design Notes

**Chunk Table Design Pattern**: `knowledge.chunks` uses a **Read-Optimized** strategy. Access control fields (`allowed_roles`, `allowed_departments`, `allowed_users`, `access_level`) are **pre-flattened** for fast AI vector search. Source of truth is `metadata.document_access_rules`. See `contexts/authorization/dual-strategy.md`.

**Versioning Strategy**:
- `knowledge.documents`: Master document record (immutable file reference)
- `knowledge.document_versions`: Immutable version history
- `knowledge.chunks`: Versioned with `document_version_id` and `is_latest` flag
- On re-ingestion: old chunks marked `is_latest = false`, new chunks inserted

---

## Table of Contents

- [knowledge.documents](#documents)
- [knowledge.document_versions](#document-versions)
- [knowledge.document_locks](#document-locks)
- [knowledge.document_version_deletions](#document-version-deletions)
- [knowledge.chunks](#chunks)
- [knowledge.processing_jobs](#processing-jobs)
- [knowledge.embedding_cache](#embedding-cache)

---

## documents

**Description**: Master record for each uploaded document file. Stores file metadata and processing status.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Document unique identifier |
| `original_filename` | VARCHAR(500) | NOT NULL | Original filename as uploaded |
| `status` | VARCHAR(50) | DEFAULT 'PENDING' | Processing status |
| `current_version` | INT | DEFAULT 1 | Current version number |
| `language` | VARCHAR(10) | DEFAULT 'en' | Detected language |
| `chunking_strategy` | VARCHAR(50) | DEFAULT 'parent_child' | Strategy used |
| `chunk_size` | INT | NULLABLE | Chunk size |
| `chunk_overlap` | INT | NULLABLE | Overlap between chunks |
| `uploaded_by` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Who uploaded |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Upload timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Indexes

- `idx_documents_status` on `status`
- `idx_documents_uploaded_by` on `uploaded_by`
- `idx_documents_created_at` on `created_at` DESC

### Notes

- **Normalized File Storage**: File-specific metadata (file_key, size) has been moved to `document_versions` to support cleaner versioning.
- **GitLab Handbook Alignment**: This table serves as the root container. The actual hierarchical grouping will rely on category metadata and section chunking.

### Indexes

- `idx_documents_file_key` on `file_key` (unique)
- `idx_documents_status` on `status`
- `idx_documents_uploaded_by` on `uploaded_by`
- `idx_documents_created_at` on `created_at` DESC

### Notes

- **Immutable File Reference**: `file_key` and `bucket_name` never change after creation. New versions create new `document_versions` rows but reuse same `documents` row.
- **Status Lifecycle**:
  - `PENDING`: Record created, waiting for ingestion processing
  - `PROCESSING`: Ingestion-service actively processing
  - `COMPLETED`: Chunks created, document searchable
  - `FAILED`: Ingestion failed, see `knowledge.processing_jobs` for error
- **One-to-One with metadata**: Every document must have exactly one corresponding `metadata.document_metadata` row (enforced by application)

---

## document_versions

**Description**: Immutable version history of document files. Each time a document is re-uploaded or re-processed, a new version is created.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Version unique identifier |
| `document_id` | UUID | NOT NULL, FOREIGN KEY → knowledge.documents(id) | Parent document |
| `version_number` | INT | NOT NULL | Sequential version (starts at 1) |
| `file_key` | VARCHAR(500) | NOT NULL | MinIO key for this version's file |
| `file_size_bytes` | BIGINT | NOT NULL | File size at this version |
| `bucket_name` | VARCHAR(100) | NOT NULL | MinIO bucket |
| `file_checksum` | VARCHAR(64) | NULLABLE | SHA256 of raw file bytes (for exact duplicate detection) |
| `content_hash` | VARCHAR(64) | NULLABLE | SHA256 of extracted text (for content deduplication) |
| `similarity_to_previous` | FLOAT | NULLABLE | Cosine similarity score vs previous version (0.0-1.0) |
| `changelog` | TEXT | NULLABLE | What changed in this version |
| `extracted_text` | TEXT | NULLABLE | Extracted text at this version |
| `is_current` | BOOLEAN | DEFAULT false | Whether this is the active version (only ONE per document) |
| `created_by` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Who triggered this version |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Version creation timestamp |

### Indexes

- `idx_document_versions_document_id` on `document_id`
- `idx_document_versions_is_current` on `is_current` (partial index WHERE is_current = true)
- `idx_versions_file_checksum` on `file_checksum` (for exact duplicate lookup)
- `idx_versions_content_hash` on `content_hash` (for content deduplication)
- Composite unique: `UNIQUE(document_id, version_number)`
- Composite: `UNIQUE(document_id, is_current)` with partial index ensures only one current per document

### Constraints

```sql
-- Ensure only one current version per document
CREATE UNIQUE INDEX idx_one_current_version_per_doc
ON knowledge.document_versions(document_id)
WHERE is_current = true;
```

### Notes

- **Immutable**: Once created, a version row never changes. Never delete version records (audit trail).
- **Current Version Flag**: Exactly one version per document has `is_current = true`. Set via:
  ```sql
  -- When creating new version:
  UPDATE knowledge.document_versions
  SET is_current = false
  WHERE document_id = :doc_id AND is_current = true;

  INSERT INTO knowledge.document_versions (..., is_current = true, ...)
  ...
  ```
- **Chunk Linking**: `knowledge.chunks.document_version_id` points to the specific version that produced them.
- **Re-indexing**: To re-process a document, create a new version (do not overwrite existing).

### Redundancy Detection Fields

| Field | Purpose | Usage |
|-------|---------|-------|
| `file_checksum` | SHA256 of raw file bytes | Layer 1: Exact duplicate detection before ingestion |
| `content_hash` | SHA256 of extracted text | Layer 2: Content deduplication (handles renames) |
| `similarity_to_previous` | Cosine similarity vs prior version | Detect minor changes between versions |

**Detection Flow**:
1. Compute `file_checksum` from MinIO download → if exists, link to existing version
2. After extraction, compute `content_hash` → query for content matches
3. Compare embedding with existing versions → store `similarity_to_previous`

---

## document_locks

**Description**: Edit locks for OnlyOffice Document Server integration. One lock per document, records who is editing, which version was locked, and when the lock expires.

**Primary Key**: `document_id` (UUID, FK to `knowledge.documents`)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `document_id` | UUID | PRIMARY KEY, FK → `knowledge.documents(id)` ON DELETE CASCADE | Document being locked |
| `locked_by` | UUID | NOT NULL | User who holds the lock |
| `locked_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When the lock was acquired |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Lock auto-expires (30 minutes default) |
| `lock_token` | UUID | NOT NULL, UNIQUE | Token returned to editor; must match on save callback |
| `version_at_lock` | INT | NOT NULL | Document version at time of lock (for conflict detection) |
| `locked_by_username` | VARCHAR(255) | NULLABLE | Username for UI display |

### Indexes

```sql
CREATE INDEX idx_locks_expires ON knowledge.document_locks(expires_at);
```

### Notes

- **One lock per document**: `PRIMARY KEY (document_id)` enforces this.
- **Auto-expiry**: Stale locks can be cleaned up with: `DELETE FROM knowledge.document_locks WHERE expires_at < NOW()`
- **Conflict Detection**: When OnlyOffice saves, if `documents.current_version > document_locks.version_at_lock`, a conflict is detected (someone else uploaded a newer version).
- **Lock Token**: OnlyOffice must pass the correct `lock_token` in the save callback to verify ownership.

---

## document_version_deletions

**Description**: Soft-delete archive for document versions. Allows recovery of accidentally deleted versions. Only ADMIN can delete versions.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Archive entry ID |
| `document_id` | UUID | NOT NULL, FK → `knowledge.documents(id)` ON DELETE CASCADE | Parent document |
| `version_number` | INT | NOT NULL | Version number that was deleted |
| `deleted_by` | UUID | NOT NULL | User who deleted |
| `deleted_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When deleted |
| `file_key` | VARCHAR(500) | NULLABLE | MinIO key (for recovery) |
| `file_size_bytes` | BIGINT | NULLABLE | File size (for recovery) |
| `changelog` | TEXT | NULLABLE | Original changelog |
| `extracted_text` | TEXT | NULLABLE | Original extracted text |

### Constraints

```sql
CONSTRAINT uq_version_deletion UNIQUE (document_id, version_number)
```

### Notes

- **Cannot delete last version**: Application must enforce that `current_version > 1` before deletion.
- **Cannot delete latest version**: Must upload a new version first, then delete the old one.
- **Immutable archive**: Once archived, records never change.
- **Recovery**: In emergency, an ADMIN can recover by reading `file_key` and manually restoring the version record.

---

## chunks

**Description**: Text chunks with embeddings for AI vector search. This is the **most critical table** for retrieval.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Chunk unique identifier |
| `document_id` | UUID | NOT NULL | Parent document |
| `document_version` | INT | NOT NULL | Version that created this chunk |
| `chunk_index` | INT | NOT NULL | Position index within document version |
| `content` | TEXT | NOT NULL | Chunk text content |
| `content_length` | INT | NOT NULL | Character length |
| `token_count` | INT | NULLABLE | Estimated token count |
| `page_number` | INT | NULLABLE | Page or section number |
| `start_char_index` | INT | NULLABLE | Char offset |
| `end_char_index` | INT | NULLABLE | Char offset end |
| `embedding_model` | VARCHAR(100) | NULLABLE | Model used |
| `embedding_dimension` | INT | NULLABLE | Vector dimension |
| `vector_indexed` | BOOLEAN | DEFAULT false | True if vector successfully saved |
| `vector_id` | VARCHAR(100) | NULLABLE | Auxiliary vector ID |
| `embedding_vector` | `vector(1024)` | NULLABLE | pgvector column - actual embedding vector |
| `department_id` | UUID | NULLABLE | Department context |
| `document_type` | VARCHAR(50) | NULLABLE | Type of document |
| `effective_date` | DATE | NULLABLE | When policy is effective |
| `expiry_date` | DATE | NULLABLE | When policy expires |
| `metadata` | JSONB | DEFAULT '{}' | Flexible metadata (crucial for GitLab Handbook fields) |
| `is_latest` | BOOLEAN | DEFAULT false | Latest version flag |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Chunk creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update |

### Indexes

**Critical Performance Indexes**:

```sql
-- Vector similarity search (HNSW index)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON knowledge.chunks
    USING hnsw (embedding_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ACL filtering (GIN indexes)
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_roles
    ON knowledge.chunks USING GIN (allowed_roles);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_departments
    ON knowledge.chunks USING GIN (allowed_departments);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_users
    ON knowledge.chunks USING GIN (allowed_users);

-- Common query filters
CREATE INDEX IF NOT EXISTS idx_chunks_search_filters
    ON knowledge.chunks (is_latest, chunk_type)
    WHERE is_latest = true AND chunk_type = 'child';

-- Document version lookups
CREATE INDEX IF NOT EXISTS idx_chunks_document_version
    ON knowledge.chunks (document_version_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_latest
    ON knowledge.chunks (document_id) WHERE is_latest = true;

-- Full-text search (BM25)
ALTER TABLE knowledge.chunks
    ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv
    ON knowledge.chunks USING GIN (content_tsv);
```

### Composite Unique Constraint

```sql
-- Prevent duplicate chunks for same document version and index
ALTER TABLE knowledge.chunks
ADD CONSTRAINT IF NOT EXISTS uniq_chunk_per_version
UNIQUE (document_version_id, chunk_index, chunk_type);
```

### Foreign Key Constraints

```sql
ALTER TABLE knowledge.chunks
ADD CONSTRAINT fk_chunks_document
    FOREIGN KEY (document_id) REFERENCES knowledge.documents(id)
    ON DELETE CASCADE;

ALTER TABLE knowledge.chunks
ADD CONSTRAINT fk_chunks_document_version
    FOREIGN KEY (document_version_id) REFERENCES knowledge.document_versions(id)
    ON DELETE CASCADE;

ALTER TABLE knowledge.chunks
ADD CONSTRAINT fk_chunks_parent
    FOREIGN KEY (parent_chunk_id) REFERENCES knowledge.chunks(id)
    ON DELETE SET NULL;
```

### Notes

- **Vector Storage**: Relies natively on `pgvector`. Ensure you are using a `pgvector`-enabled Docker image.
- **GitLab Handbook Support (MISSING FIELDS)**: Currently, the structural fields necessary for the GitLab handbook (e.g., `section_title`, `section_path`, `section_level`) are missing. They either need to be added as dedicated columns or stored inside the `metadata` JSONB column. Storing them in dedicated GIN-indexed JSONB or separate columns is critical for high-performance section filtering.
- **Versioning & Soft Delete (Data Bloat Prevention)**: When superseded by a new version, chunks are marked `is_latest = false`. Because vector embeddings consume massive disk space, a background cron job MUST definitively hard-delete old chunks (e.g., `is_latest = false` AND older than 3 months) to prevent database bloat.
- **Query Pattern**:
  ```sql
  SELECT * FROM knowledge.chunks
  WHERE is_latest = true
    AND chunk_type = 'child'
    AND embedding_vector <=> :query_vector < :threshold
    AND (access_level = 'PUBLIC' OR allowed_departments @> ARRAY[:user_dept_id]::UUID[])
    -- AND ... other ACL filters
  ORDER BY embedding_vector <=> :query_vector
  LIMIT 50;
  ```

---

## processing_jobs

**Description**: Tracks ETL pipeline progress for document ingestion

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Job unique identifier |
| `document_id` | UUID | NOT NULL, FOREIGN KEY → knowledge.documents(id) | Document being processed |
| `document_version_id` | UUID | NULLABLE, FOREIGN KEY → knowledge.document_versions(id) | Version being processed (if any) |
| `job_type` | VARCHAR(50) | NOT NULL | 'INGESTION' or 'REINDEX' |
| `status` | VARCHAR(50) | NOT NULL | 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED' |
| `progress_percent` | INT | DEFAULT 0 | 0-100 completion percentage |
| `started_at` | TIMESTAMP | NULLABLE | Job start timestamp |
| `completed_at` | TIMESTAMP | NULLABLE | Job completion timestamp |
| `success` | BOOLEAN | NULLABLE | True if succeeded, false if failed |
| `error_message` | TEXT | NULLABLE | Error description (if failed) |
| `error_details` | JSONB | NULLABLE | Detailed error info (stack trace, etc.) |
| `retry_count` | INT | DEFAULT 0 | Number of retry attempts |
| `max_retries` | INT | DEFAULT 3 | Max retries configured |
| `output_metrics` | JSONB | NULLABLE | Metrics: {chunk_count, page_count, word_count, extraction_method, ...} |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Job creation timestamp |

### Indexes

- `idx_processing_jobs_document_id` on `document_id`
- `idx_processing_jobs_status` on `status`
- `idx_processing_jobs_created_at` on `created_at` DESC
- `idx_processing_jobs_stuck` on `(status, started_at)` for finding stale jobs

### Notes

- **Idempotency**: Job IDs should be idempotent. If RabbitMQ redelivers `ingestion.requested`, check if job exists with `status IN ('COMPLETED','FAILED')` and skip.
- **TTL**: Completed jobs can be archived/deleted after 30 days (configurable). Use `created_at < NOW() - INTERVAL '30 days'` for cleanup.
- **Stale Job Detection**: Run cron every hour to find jobs in `PROCESSING` state with `started_at > NOW() - INTERVAL '24 hours'` (stuck), mark as `FAILED` with timeout error.
- **Metrics**: `output_metrics` stores statistics useful for monitoring and debugging (token counts, extraction method, etc.)

---

## embedding_cache

**Description**: Cache for embedding vectors to reduce API costs and latency for repeated text

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Cache entry ID |
| `text_hash` | VARCHAR(64) | NOT NULL | SHA256 hash of input text |
| `text_length` | INT | NOT NULL | Character length of input text |
| `embedding_model` | VARCHAR(100) | NOT NULL | Model used (e.g., "BGE-M3") |
| `embedding_dimension` | INT | NOT NULL | Vector dimension |
| `embedding_vector` | `vector(1024)` | NOT NULL | pgvector column - actual embedding vector |
| `usage_count` | INT | DEFAULT 0 | How many times this embedding has been reused |
| `last_used_at` | TIMESTAMP | DEFAULT NOW() | Last retrieval timestamp |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Cache entry creation timestamp |

### Indexes

- Unique composite: `UNIQUE(text_hash, embedding_model, embedding_dimension)`
- `idx_embedding_cache_last_used` on `last_used_at` DESC for LRU cleanup
- GIN index on `embedding_vector` (if querying directly)

### Notes

- **Cache Key**: `(text_hash, embedding_model, embedding_dimension)` tuple uniquely identifies an embedding
- **Hit Workflow**:
  1. Compute SHA256 of input text
  2. Look up cache WHERE `text_hash = ?` AND `embedding_model = ?`
  3. If hit: increment `usage_count`, update `last_used_at`, return cached embedding
  4. If miss: Call embedding model, store in cache
- **Eviction Policy**: LRU (Least Recently Used). Run cleanup job to delete entries where `last_used_at < NOW() - INTERVAL '90 days'` AND `usage_count < 5`.
- **Cost Savings**: Significant for cloud embedding APIs (OpenAI, Cohere). Especially effective for common query templates.

---

## ENUM Types

### processing_status

```sql
CREATE TYPE processing_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
```

### job_type

```sql
CREATE TYPE job_type AS ENUM ('INGESTION', 'REINDEX');
```

### chunk_type

```sql
CREATE TYPE chunk_type AS ENUM ('parent', 'child');
```

---

## Migrations & Schema Changes

### Required Indexes (Run Once)

```sql
-- HNSW vector index
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON knowledge.chunks
    USING hnsw (embedding_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN indexes for arrays
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_roles
    ON knowledge.chunks USING GIN (allowed_roles);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_departments
    ON knowledge.chunks USING GIN (allowed_departments);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_users
    ON knowledge.chunks USING GIN (allowed_users);

-- Full-text search
ALTER TABLE knowledge.chunks
    ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv
    ON knowledge.chunks USING GIN (content_tsv);

-- Partial index for latest child chunks (common query pattern)
CREATE INDEX IF NOT EXISTS idx_chunks_latest_children
    ON knowledge.chunks (document_id, chunk_index)
    WHERE is_latest = true AND chunk_type = 'child';
```

---

## Performance Tuning

### Expected Query Latencies (p99)

| Query | Expected (with indexes) | Notes |
|-------|------------------------|-------|
| Vector search 50 neighbors | < 50ms | Depends on dataset size; HNSW recall ~95% |
| ACL filter by role | < 5ms | GIN index on `allowed_roles` |
| Fetch document + latest chunks | < 10ms | Index on `(document_id, is_latest)` |
| Insert batch of 100 chunks | < 200ms | Bulk insert with single transaction |

### Monitoring

- Track table size: `SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname = 'knowledge';`
- Index usage: `SELECT * FROM pg_stat_user_indexes WHERE schemaname = 'knowledge';`
- Vector index build time: For 1M chunks, ~5-10 minutes. Do during maintenance window.

---

## Related References

- **Dual-Strategy Auth**: `contexts/authorization/dual-strategy.md` - ACL flattening workflow
- **AI Architecture**: `contexts/architecture/ai-service-architecture.md` - ingestion pipeline
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md` - ownership rules
- **Database Schema Overview**: `contexts/database/schema.md` - complete reference

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
