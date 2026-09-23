---
title: Database Indexes & Performance Strategy
description: Indexing strategy and query optimization for Poliwise PostgreSQL database
type: database
version: 1.0
---

# Database Indexes & Performance

## Purpose

This document defines the **indexing strategy and performance optimization rules** for the Poliwise PostgreSQL database. It specifies which indexes MUST exist and how to query them efficiently.

## When to Use

- Adding new indexes to support query patterns
- Optimizing slow queries
- Understanding query execution plans
- Designing new database tables

---

## Core Indexing Rules

### 1. ALWAYS Create These Index Types

| Index Type | Use Case | Example |
|------------|----------|---------|
| **Primary Key** | Every table must have `id UUID PRIMARY KEY` | Default on all tables |
| **Foreign Key** | Columns used in JOINs | `document_id UUID` referencing `documents.id` |
| **Composite** | WHERE clauses with multiple columns | `(department_id, status)` |
| **Partial** | Filtering on subset of rows | `WHERE is_latest = true` |
| **GIN** | Array, JSONB, full-text search | `allowed_roles TEXT[]`, `metadata JSONB` |
| **BRIN** | Time-series data (timestamps) | `created_at TIMESTAMP` |

### 2. Vector Search Indexes (pgvector)

For `knowledge.chunks.embedding_vector vector(1024)`:
- **HNSW** index for approximate nearest neighbor (ANN)
- Must use `USING hnsw (embedding_vector vector_cosine_ops)`
- Parameters: `WITH (m = 16, ef_construction = 64)`

### 3. Full-Text Search Indexes

For text search on `knowledge.chunks.content`:
- **GIN** index on generated TSVECTOR column
- Use `to_tsvector('english', content)` 
- Index: `USING GIN (content_tsv)`

---

## Required Indexes by Schema

### Schema: `core`

```sql
-- core.departments
CREATE INDEX idx_departments_parent_id ON core.departments (parent_id);
CREATE INDEX idx_departments_is_active ON core.departments (is_active);

-- core.users
CREATE INDEX idx_users_role_status ON core.users (role, status);
CREATE INDEX idx_users_department_id ON core.users (department_id);
CREATE INDEX idx_users_email ON core.users (email);
CREATE INDEX idx_users_username ON core.users (username);
CREATE UNIQUE INDEX uq_users_email ON core.users (email) WHERE deleted_at IS NULL;

-- core.user_profiles
CREATE UNIQUE INDEX uq_user_profiles_user_id ON core.user_profiles (user_id);
CREATE INDEX idx_user_profiles_employee_code ON core.user_profiles (employee_code);

-- core.refresh_tokens
CREATE INDEX idx_refresh_tokens_user_id ON core.refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON core.refresh_tokens (expires_at) WHERE revoked = false;

-- core.login_history
CREATE INDEX idx_login_history_user_id_date ON core.login_history (user_id, created_at DESC);
CREATE INDEX idx_login_history_ip ON core.login_history (ip_address);
```

### Schema: `metadata`

```sql
-- metadata.categories
CREATE INDEX idx_categories_parent_id ON metadata.categories (parent_id);
CREATE INDEX idx_categories_is_active ON metadata.categories (is_active);

-- metadata.tags
CREATE INDEX idx_tags_slug ON metadata.tags (slug);
CREATE INDEX idx_tags_usage_count ON metadata.tags (usage_count DESC);

-- metadata.document_metadata
CREATE INDEX idx_document_metadata_document_id ON metadata.document_metadata (document_id);
CREATE INDEX idx_document_metadata_category_id ON metadata.document_metadata (category_id);
CREATE INDEX idx_document_metadata_department_id ON metadata.document_metadata (department_id);
CREATE INDEX idx_document_metadata_status ON metadata.document_metadata (status);
CREATE INDEX idx_document_metadata_access_level ON metadata.document_metadata (access_level);
CREATE INDEX idx_document_metadata_created_by ON metadata.document_metadata (created_by);
CREATE INDEX idx_document_metadata_published_at ON metadata.document_metadata (published_at) WHERE published_at IS NOT NULL;

-- metadata.document_tags
CREATE UNIQUE INDEX uq_document_tags_composite ON metadata.document_tags (document_metadata_id, tag_id);
CREATE INDEX idx_document_tags_tag_id ON metadata.document_tags (tag_id);

-- metadata.document_access_rules
CREATE INDEX idx_access_rules_document_id ON metadata.document_access_rules (document_metadata_id);
CREATE INDEX idx_access_rules_target_type ON metadata.document_access_rules (target_type, permission);
CREATE INDEX idx_access_rules_target_user ON metadata.document_access_rules (target_user_id) WHERE target_type = 'USER';
CREATE INDEX idx_access_rules_target_dept ON metadata.document_access_rules (target_department_id) WHERE target_type = 'DEPARTMENT';
```

### Schema: `knowledge`

```sql
-- knowledge.documents
CREATE INDEX idx_documents_uploaded_by ON knowledge.documents (uploaded_by);
CREATE INDEX idx_documents_status ON knowledge.documents (status);
CREATE INDEX idx_documents_created_at ON knowledge.documents (created_at DESC);
CREATE INDEX idx_documents_file_type ON knowledge.documents (file_type);

-- knowledge.document_versions
CREATE INDEX idx_doc_versions_document_id ON knowledge.document_versions (document_id);
CREATE INDEX idx_doc_versions_version ON knowledge.document_versions (document_id, version_number DESC);
CREATE INDEX idx_doc_versions_is_current ON knowledge.document_versions (is_current) WHERE is_current = true;

-- knowledge.chunks (CRITICAL TABLE)
-- Primary vector search index
CREATE INDEX idx_chunks_embedding_hnsw ON knowledge.chunks 
  USING hnsw (embedding_vector vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- ACL filtering indexes (for fast permission checks)
CREATE INDEX idx_chunks_allowed_roles ON knowledge.chunks USING GIN (allowed_roles);
CREATE INDEX idx_chunks_allowed_departments ON knowledge.chunks USING GIN (allowed_departments);
CREATE INDEX idx_chunks_allowed_users ON knowledge.chunks USING GIN (allowed_users);
CREATE INDEX idx_chunks_access_level ON knowledge.chunks (access_level);

-- Document relationship indexes
CREATE INDEX idx_chunks_document_id ON knowledge.chunks (document_id);
CREATE INDEX idx_chunks_document_version_id ON knowledge.chunks (document_version_id);
CREATE INDEX idx_chunks_parent_chunk_id ON knowledge.chunks (parent_chunk_id);

-- Latest chunks filter (commonly used)
CREATE INDEX idx_chunks_latest ON knowledge.chunks (document_id, is_latest) WHERE is_latest = true;

-- Chunk type hierarchy
CREATE INDEX idx_chunks_chunk_type ON knowledge.chunks (chunk_type);
CREATE INDEX idx_chunks_latest_children ON knowledge.chunks (document_id, chunk_index) 
  WHERE is_latest = true AND chunk_type = 'child';

-- Full-text search
ALTER TABLE knowledge.chunks ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX idx_chunks_content_tsv ON knowledge.chunks USING GIN (content_tsv);

-- knowledge.processing_jobs
CREATE INDEX idx_processing_jobs_document_id ON knowledge.processing_jobs (document_id);
CREATE INDEX idx_processing_jobs_status_created ON knowledge.processing_jobs (status, created_at DESC);
CREATE INDEX idx_processing_jobs_started_at ON knowledge.processing_jobs (started_at) WHERE started_at IS NOT NULL;

-- knowledge.embedding_cache
CREATE UNIQUE INDEX uq_embedding_cache_text_hash ON knowledge.embedding_cache (text_hash);
CREATE INDEX idx_embedding_cache_last_used ON knowledge.embedding_cache (last_used_at DESC);
CREATE INDEX idx_embedding_cache_model ON knowledge.embedding_cache (embedding_model);
```

### Schema: `conversation`

```sql
-- conversation.conversations
CREATE INDEX idx_conversations_user_id ON conversation.conversations (user_id);
CREATE INDEX idx_conversations_last_message ON conversation.conversations (last_message_at DESC);
CREATE INDEX idx_conversations_deleted_at ON conversation.conversations (deleted_at) WHERE deleted_at IS NULL;

-- conversation.messages
CREATE INDEX idx_messages_conversation_id ON conversation.messages (conversation_id, created_at ASC);
CREATE INDEX idx_messages_role ON conversation.messages (role);
CREATE INDEX idx_messages_has_sources ON conversation.messages (has_sources) WHERE has_sources = true;
CREATE INDEX idx_messages_created_at ON conversation.messages (created_at DESC);

-- conversation.unanswered_questions
CREATE INDEX idx_unanswered_resolved ON conversation.unanswered_questions (resolved) WHERE resolved = false;
CREATE INDEX idx_unanswered_priority ON conversation.unanswered_questions (priority);
CREATE INDEX idx_unanswered_created_at ON conversation.unanswered_questions (created_at DESC);
```

### Schema: `analytics`

```sql
-- analytics.feedbacks
CREATE INDEX idx_feedbacks_user_id ON analytics.feedbacks (user_id);
CREATE INDEX idx_feedbacks_message_id ON analytics.feedbacks (message_id);
CREATE INDEX idx_feedbacks_type ON analytics.feedbacks (type);
CREATE INDEX idx_feedbacks_created_at ON analytics.feedbacks (created_at DESC);

-- analytics.usage_stats
CREATE INDEX idx_usage_user_id ON analytics.usage_stats (user_id);
CREATE INDEX idx_usage_service_endpoint ON analytics.usage_stats (service_name, endpoint);
CREATE INDEX idx_usage_created_at ON analytics.usage_stats (created_at DESC);
CREATE INDEX idx_usage_status_code ON analytics.usage_stats (status_code);

-- analytics.audit_logs
CREATE INDEX idx_audit_user_id ON analytics.audit_logs (user_id);
CREATE INDEX idx_audit_action_date ON analytics.audit_logs (action, created_at DESC);
CREATE INDEX idx_audit_resource ON analytics.audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_ip ON analytics.audit_logs (ip_address);

-- Time-series aggregates (partitioned by date)
CREATE INDEX idx_daily_aggregates_date ON analytics.daily_aggregates (date DESC);
CREATE INDEX idx_hourly_aggregates_datetime ON analytics.hourly_aggregates (datetime DESC);
CREATE INDEX idx_dept_daily_stats_date_dept ON analytics.department_daily_stats (date, department_id);

-- analytics.popular_questions
CREATE INDEX idx_popular_questions_ask_count ON analytics.popular_questions (ask_count DESC);
CREATE UNIQUE INDEX uq_popular_questions_normalized ON analytics.popular_questions (question_normalized);

-- analytics.document_popularity
CREATE INDEX idx_doc_popularity_citations ON analytics.document_popularity (total_citations DESC);
CREATE UNIQUE INDEX uq_doc_popularity_document ON analytics.document_popularity (document_id);
```

---

## Query Patterns & Index Usage

### 1. Vector Search with ACL Filtering

**Query Pattern:**
```sql
SELECT c.* 
FROM knowledge.chunks c
WHERE c.embedding_vector <=> :query_embedding < 0.3
  AND (
    c.access_level = 'PUBLIC'
    OR c.allowed_users @> ARRAY[:user_id]::UUID[]
    OR c.allowed_departments @> ARRAY[:department_id]::UUID[]
    OR c.allowed_roles @> ARRAY[:user_role]::TEXT[]
  )
  AND c.is_latest = true
ORDER BY c.embedding_vector <=> :query_embedding
LIMIT 10;
```

**Indexes Used:**
- `idx_chunks_embedding_hnsw` (vector search)
- `idx_chunks_allowed_users`, `idx_chunks_allowed_departments`, `idx_chunks_allowed_roles` (GIN for array containment)
- `idx_chunks_access_level` (access level filter)
- `idx_chunks_latest` (partial index for latest chunks)

### 2. Document Search by Metadata

**Query Pattern:**
```sql
SELECT dm.*, c.name as category_name
FROM metadata.document_metadata dm
JOIN metadata.categories c ON dm.category_id = c.id
WHERE dm.department_id = :dept_id
  AND dm.status = 'PUBLISHED'
  AND dm.access_level = 'DEPARTMENT_ONLY'
  AND dm.deleted_at IS NULL
ORDER BY dm.published_at DESC
LIMIT 50;
```

**Indexes Used:**
- `idx_document_metadata_department_id`
- `idx_document_metadata_status`
- `idx_document_metadata_access_level`
- `idx_document_metadata_published_at` (partial)
- `idx_categories_id` (FK join)

### 3. User Conversations with Latest Messages

**Query Pattern:**
```sql
SELECT conv.*, 
       (SELECT content FROM conversation.messages m 
        WHERE m.conversation_id = conv.id 
        ORDER BY m.created_at DESC LIMIT 1) as last_message
FROM conversation.conversations conv
WHERE conv.user_id = :user_id
  AND conv.deleted_at IS NULL
ORDER BY conv.last_message_at DESC;
```

**Indexes Used:**
- `idx_conversations_user_id`
- `idx_conversations_last_message`
- `idx_conversations_deleted_at` (partial)
- `idx_messages_conversation_id_created` (for subquery)

---

## Index Maintenance & Monitoring

### 1. Bloat Detection

Check for index bloat monthly:
```sql
-- Index bloat check
SELECT schemaname, tablename, indexname, 
       pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
       idx_scan as scans_since_boot
FROM pg_stat_user_indexes 
WHERE schemaname IN ('core', 'metadata', 'knowledge', 'conversation', 'analytics')
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
```

### 2. Unused Indexes

Identify indexes with zero scans:
```sql
-- Unused indexes (consider dropping)
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes 
WHERE idx_scan = 0
  AND schemaname NOT LIKE 'pg_%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 3. Index Creation Best Practices

1. **Use CONCURRENTLY** for production:
   ```sql
   CREATE INDEX CONCURRENTLY idx_name ON table_name (column);
   ```

2. **Test index impact** on staging with `EXPLAIN ANALYZE`:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM table WHERE column = value;
   ```

3. **Monitor query plans** after index creation:
   ```sql
   -- Check if index is being used
   SELECT * FROM pg_stat_statements 
   WHERE query LIKE '%table_name%' 
   ORDER BY total_time DESC;
   ```

4. **Rebuild bloated indexes**:
   ```sql
   REINDEX INDEX CONCURRENTLY idx_name;
   ```

---

## Performance Anti-Patterns

### ❌ DO NOT DO THESE:

1. **Full table scans without WHERE**: Always filter by indexed columns
2. **Functions on indexed columns**: `WHERE UPPER(column) = 'VALUE'` bypasses index
3. **OR conditions on different columns**: Use UNION instead
4. **LIKE with leading wildcard**: `'%value%'` can't use index (except trigram)
5. **Implicit type conversions**: Ensure comparands have same type

### ✅ DO THESE INSTEAD:

1. **Use covering indexes**: Include frequently selected columns
2. **Batch operations**: Use `IN` clause instead of multiple `OR`
3. **Partial indexes**: For filtered subsets of data
4. **Composite indexes**: Match query `WHERE` and `ORDER BY` clauses
5. **Query planner hints**: Use `/*+ IndexScan(table idx_name) */` if needed

---

## Emergency Procedures

### Slow Query Investigation

1. **Identify culprit**:
   ```sql
   SELECT pid, query, state, age(clock_timestamp(), query_start) as duration
   FROM pg_stat_activity 
   WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
   ORDER BY duration DESC;
   ```

2. **Kill long-running query** (if safe):
   ```sql
   SELECT pg_cancel_backend(pid);  -- Graceful cancel
   SELECT pg_terminate_backend(pid); -- Force kill
   ```

3. **Analyze query plan**:
   ```sql
   EXPLAIN (ANALYZE, BUFFERS) <problem_query>;
   ```

### Index Corruption

If index returns wrong results:
1. **Check for corruption**:
   ```sql
   SELECT * FROM pg_stat_all_tables WHERE relname = 'table_name';
   ```

2. **Reindex table**:
   ```sql
   REINDEX TABLE table_name;
   ```

3. **Verify with checksum**:
   ```sql
   CHECKSUM TABLE table_name;
   ```

---

## References

- **Schema Definitions**: `contexts/database/tables/*.md`
- **Migration Procedures**: `contexts/database/migrations.md`
- **Query Patterns**: `contexts/database/queries.md`
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md`

---

**Last Updated**: 2026-04-08  
**Documentation Version**: 1.0  
**Critical**: Index changes require performance testing on staging before production.