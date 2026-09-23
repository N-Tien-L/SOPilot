---
title: Database Query Patterns & Examples
description: Common SQL query patterns for Poliwise services, with performance considerations
type: database
version: 1.0
---

# Database Query Patterns

## Purpose

Provides AI agents with ready-to-use SQL patterns for common operations across all schemas. Use this as a reference when implementing repository classes or debugging queries.

## When to Use

- Implementing new database queries
- Optimizing slow queries
- Ensuring consistent patterns across services
- Understanding how to construct complex joins without crossing schema boundaries

---

## General Rules (Apply to All Queries)

1. **Always include soft delete filter**:
   ```sql
   WHERE deleted_at IS NULL
   ```
   on tables that have `deleted_at` column (`core.*`, `metadata.*`, `knowledge.*`, `conversation.*`, `analytics.*`).

2. **Never cross schema joins**:
   ❌ `SELECT ... FROM knowledge.chunks JOIN metadata.document_metadata ...`
   ✅ Either:
   - Denormalize needed data into target schema (via events)
   - Call other service via HTTP
   - Use flattened arrays in `knowledge.chunks`

3. **Use parameterized queries** to prevent SQL injection:
   ```python
   await session.execute(text("SELECT * FROM core.users WHERE id = :id"), {"id": user_id})
   ```

---

## Core Schema Queries (auth-service)

### Find User by Username (for login)

```sql
SELECT
    u.id, u.username, u.email, u.password_hash, u.role, u.status,
    u.department_id, u.failed_login_attempts, u.locked_until,
    d.name as department_name
FROM core.users u
LEFT JOIN core.departments d ON d.id = u.department_id
WHERE u.username = :username
  AND u.deleted_at IS NULL;
```

**Index**: `idx_users_username`

---

### Validate JWT Claims (user exists and active)

```sql
SELECT id, username, role, status, department_id
FROM core.users
WHERE id = :user_id
  AND status = 'ACTIVE'
  AND deleted_at IS NULL;
```

---

### Record Login History

```sql
INSERT INTO core.login_history (
    id, user_id, username, ip_address, user_agent,
    device_type, location, status, failure_reason, created_at
) VALUES (
    :id, :user_id, :username, :ip_address, :user_agent,
    :device_type, :location, 'SUCCESS', NULL, NOW()
);
```

---

### Increment Failed Login Attempts

```sql
UPDATE core.users
SET
    failed_login_attempts = failed_login_attempts + 1,
    locked_until = CASE
        WHEN failed_login_attempts + 1 >= 5 THEN NOW() + INTERVAL '15 minutes'
        ELSE locked_until
    END
WHERE id = :user_id
  AND deleted_at IS NULL
RETURNING failed_login_attempts, locked_until;
```

---

### Reset Failed Login Attempts (on successful login)

```sql
UPDATE core.users
SET failed_login_attempts = 0,
    locked_until = NULL
WHERE id = :user_id
  AND deleted_at IS NULL;
```

---

## Metadata Schema Queries (metadata-service)

### Get Document Metadata with Access Rules

```sql
SELECT
    dm.id, dm.document_id, dm.title, dm.description, dm.document_type,
    dm.category_id, dm.department_id, dm.access_level,
    dm.effective_date, dm.expiry_date, dm.status,
    c.name as category_name,
    d.name as department_name,
    COALESCE(JSON_AGG(
        JSON_BUILD_OBJECT(
            'target_type', dar.target_type,
            'target_role', dar.target_role,
            'target_department_id', dar.target_department_id,
            'target_user_id', dar.target_user_id,
            'permission', dar.permission
        )
    ) FILTER (WHERE dar.id IS NOT NULL), '[]') as access_rules
FROM metadata.document_metadata dm
LEFT JOIN metadata.categories c ON c.id = dm.category_id
LEFT JOIN core.departments d ON d.id = dm.department_id
LEFT JOIN metadata.document_access_rules dar ON dar.document_metadata_id = dm.id
WHERE dm.document_id = :document_id
  AND dm.deleted_at IS NULL
GROUP BY dm.id, c.name, d.name;
```

**Note**: Returns one row with `access_rules` as JSON array of all rule entries.

---

### Check Document Access (Real-time permission check)

```sql
CREATE OR REPLACE FUNCTION check_document_access(
    p_user_id UUID,
    p_document_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_user_role TEXT;
    v_user_department_id UUID;
    v_metadata_id UUID;
    has_specific_deny BOOLEAN := FALSE;
    has_specific_allow BOOLEAN := FALSE;
BEGIN
    -- Get user role and department
    SELECT role, department_id INTO v_user_role, v_user_department_id
    FROM core.users
    WHERE id = p_user_id AND deleted_at IS NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Get document metadata ID
    SELECT id INTO v_metadata_id
    FROM metadata.document_metadata
    WHERE document_id = p_document_id AND deleted_at IS NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Check for explicit DENY
    SELECT TRUE INTO has_specific_deny
    FROM metadata.document_access_rules
    WHERE document_metadata_id = v_metadata_id
      AND permission = 'DENY'
      AND (
          (target_type = 'USER' AND target_user_id = p_user_id)
          OR (target_type = 'ROLE' AND target_role = v_user_role)
          OR (target_type = 'DEPARTMENT' AND target_department_id = v_user_department_id)
      )
    LIMIT 1;

    IF has_specific_deny THEN
        RETURN FALSE;
    END IF;

    -- Check for explicit VIEW grant
    SELECT TRUE INTO has_specific_allow
    FROM metadata.document_access_rules
    WHERE document_metadata_id = v_metadata_id
      AND permission = 'VIEW'
      AND (
          (target_type = 'USER' AND target_user_id = p_user_id)
          OR (target_type = 'ROLE' AND target_role = v_user_role)
          OR (target_type = 'DEPARTMENT' AND target_department_id = v_user_department_id)
      )
    LIMIT 1;

    IF has_specific_allow THEN
        RETURN TRUE;
    END IF;

    -- Fallback to access_level
    SELECT access_level INTO v_access_level
    FROM metadata.document_metadata
    WHERE id = v_metadata_id;

    IF v_access_level = 'PUBLIC' THEN
        RETURN TRUE;
    END IF;

    IF v_access_level = 'DEPARTMENT_ONLY'
       AND v_user_department_id IS NOT NULL THEN
        -- Check if user's department matches document's department
        SELECT department_id INTO v_metadata_id
        FROM metadata.document_metadata
        WHERE id = v_metadata_id;

        IF v_metadata_id = v_user_department_id THEN
            RETURN TRUE;
        END IF;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;
```

**Usage**: Call from application code with `SELECT check_document_access(:user_id, :document_id)`.

---

### List Documents with Filters

```sql
SELECT
    dm.document_id,
    dm.title,
    dm.document_type,
    dm.status,
    dm.access_level,
    c.name as category_name,
    d.name as department_name,
    dm.effective_date,
    dm.expiry_date,
    dm.published_at
FROM metadata.document_metadata dm
LEFT JOIN metadata.categories c ON c.id = dm.category_id
LEFT JOIN core.departments d ON d.id = dm.department_id
WHERE dm.deleted_at IS NULL
  AND dm.status = 'PUBLISHED'
  AND dm.effective_date <= CURRENT_DATE
  AND (dm.expiry_date IS NULL OR dm.expiry_date > CURRENT_DATE)
  AND (:category_id IS NULL OR dm.category_id = :category_id)
  AND (:department_id IS NULL OR dm.department_id = :department_id)
  AND (:access_level IS NULL OR dm.access_level = :access_level)
ORDER BY dm.published_at DESC
LIMIT :limit OFFSET :offset;
```

---

## Knowledge Schema Queries (ingestion-service, ai-qa-service)

### Insert Chunks with ACLs (Bulk)

```sql
INSERT INTO knowledge.chunks (
    id, document_id, document_version_id, chunk_type,
    parent_chunk_id, content, summary, section_title, section_level,
    section_path, chunk_index, start_char_index, end_char_index,
    token_count, child_chunk_ids, embedding_model, embedding_dimension,
    embedding_vector, allowed_roles, allowed_departments, allowed_users,
    access_level, is_latest, created_at
) VALUES (
    :id, :document_id, :document_version_id, :chunk_type,
    :parent_chunk_id, :content, :summary, :section_title, :section_level,
    :section_path::jsonb, :chunk_index, :start_char_index, :end_char_index,
    :token_count, :child_chunk_ids, :embedding_model, :embedding_dimension,
    :embedding_vector, :allowed_roles, :allowed_departments, :allowed_users,
    :access_level, true, NOW()
);
```

**Performance**: Use bulk insert with multiple VALUES rows or ` executemany()`.

---

### Vector Search with ACL Filter (AI Q&A hot path)

```sql
SELECT
    c.id,
    c.document_id,
    c.content,
    c.section_title,
    c.section_path,
    d.original_filename as document_title,
    dm.access_level,
    c.embedding_vector <=> :query_vector AS similarity_score
FROM knowledge.chunks c
JOIN knowledge.documents d ON d.id = c.document_id
JOIN metadata.document_metadata dm ON dm.document_id = d.id
WHERE
    c.is_latest = true
    AND c.chunk_type = 'child'
    AND dm.status = 'PUBLISHED'
    AND dm.effective_date <= NOW()
    AND (dm.expiry_date IS NULL OR dm.expiry_date > NOW())
    AND dm.deleted_at IS NULL
    AND (
        dm.access_level = 'PUBLIC'
        OR (:user_role IS NOT NULL AND c.allowed_roles @> ARRAY[:user_role]::TEXT[])
        OR (:user_dept_id IS NOT NULL AND c.allowed_departments @> ARRAY[:user_dept_id]::UUID[])
        OR (:user_id IS NOT NULL AND c.allowed_users @> ARRAY[:user_id]::UUID[])
    )
ORDER BY c.embedding_vector <=> :query_vector
LIMIT :top_k;
```

**Indexes Required**: HNSW on `embedding_vector`, GIN on `allowed_*` arrays, composite on `(is_latest, chunk_type)`.

---

### Update Chunk ACLs (Permission Sync)

```sql
UPDATE knowledge.chunks
SET
    allowed_roles = :allowed_roles,
    allowed_departments = :allowed_departments,
    allowed_users = :allowed_users,
    access_level = :access_level,
    updated_at = NOW()
WHERE
    document_id = :document_id
    AND is_latest = true;
```

**Return**: Number of rows affected (should match `chunks per document` count).

---

### Mark Old Chunks as Not Latest (Versioning)

```sql
UPDATE knowledge.chunks
SET is_latest = false,
    updated_at = NOW()
WHERE
    document_id = :document_id
    AND is_latest = true;
```

**Do this before inserting new version's chunks** (in same transaction).

---

### Get Document Version Info

```sql
SELECT
    dv.id, dv.version_number, dv.file_key, dv.file_size_bytes,
    dv.created_by, dv.created_at,
    d.original_filename
FROM knowledge.document_versions dv
JOIN knowledge.documents d ON d.id = dv.document_id
WHERE dv.document_id = :document_id
  AND dv.is_current = true
  AND dv.deleted_at IS NULL;
```

---

### Count Chunks per Document (for monitoring)

```sql
SELECT
    document_id,
    chunk_type,
    COUNT(*) as chunk_count
FROM knowledge.chunks
WHERE is_latest = true
GROUP BY document_id, chunk_type;
```

---

## Conversation Schema Queries (ai-qa-service)

### Create Conversation

```sql
INSERT INTO conversation.conversations (
    id, user_id, title, message_count, last_message_at, created_at
) VALUES (
    :id, :user_id, :title, 0, NOW(), NOW()
)
RETURNING id, created_at;
```

---

### Insert Message

```sql
INSERT INTO conversation.messages (
    id, conversation_id, role, content, sources,
    model_used, tokens_prompt, tokens_completion, tokens_total,
    latency_ms, confidence, has_sources, created_at
) VALUES (
    :id, :conversation_id, :role, :content, :sources::jsonb,
    :model_used, :tokens_prompt, :tokens_completion, :tokens_total,
    :latency_ms, :confidence, :has_sources, NOW()
)
RETURNING id, created_at;
```

**After insert**, update conversation:
```sql
UPDATE conversation.conversations
SET
    message_count = message_count + 1,
    last_message_at = NOW(),
    updated_at = NOW()
WHERE id = :conversation_id;
```

---

### Get Conversation with Messages (Paginated)

```sql
-- Get conversation metadata
SELECT * FROM conversation.conversations
WHERE id = :conversation_id
  AND user_id = :user_id
  AND deleted_at IS NULL;

-- Get messages (most recent first, paginated)
SELECT * FROM conversation.messages
WHERE conversation_id = :conversation_id
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;
```

---

### Unanswered Questions Insert

```sql
INSERT INTO conversation.unanswered_questions (
    id, user_id, message_id, conversation_id,
    question, question_normalized, search_query, top_similarity_score,
    resolved, priority, created_at
) VALUES (
    :id, :user_id, :message_id, :conversation_id,
    :question, LOWER(REMOVE_DIACRITICS(:question)), :search_query, :score,
    false, :priority, NOW()
)
ON CONFLICT (question_normalized) WHERE resolved = false
DO UPDATE SET
    ask_count = unanswered_questions.ask_count + 1,
    last_asked_at = NOW();
```

**Note**: `REMOVE_DIACRITICS()` is a custom function to normalize English strings and remove special characters. Implement:
```sql
CREATE OR REPLACE FUNCTION remove_diacritics(text TEXT) RETURNS TEXT AS $$
BEGIN
    -- Convert to NFD (decomposed), remove diacritics, recompose
    RETURN regexp_replace(
        convert_to(text, 'UNICODE')::text,
        '[\u0300-\u036f]', '', 'g'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## Analytics Schema Queries (feedback-service)

### Satisfaction Rate (Last 30 days)

```sql
SELECT
    COUNT(*) as total_feedbacks,
    COUNT(*) FILTER (WHERE type = 'LIKE') as likes,
    COUNT(*) FILTER (WHERE type = 'DISLIKE') as dislikes,
    ROUND(
        COUNT(*) FILTER (WHERE type = 'LIKE') * 100.0 / COUNT(*),
        2
    ) as satisfaction_rate
FROM analytics.feedbacks
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days';
```

---

### Top Documents by Citations

```sql
SELECT
    dp.document_id,
    d.original_filename,
    dp.total_citations,
    dp.citations_with_likes,
    dp.citations_with_dislikes,
    ROUND(dp.citations_with_likes * 100.0 / NULLIF(dp.total_citations, 0), 2) as like_ratio
FROM analytics.document_popularity dp
JOIN knowledge.documents d ON d.id = dp.document_id
ORDER BY dp.total_citations DESC
LIMIT 20;
```

---

### Dashboard Daily Stats (Last 14 days)

```sql
SELECT
    d.date,
    d.total_questions,
    d.unique_users_asked,
    ROUND(d.total_likes * 100.0 / NULLIF(d.total_likes + d.total_dislikes, 0), 2) as satisfaction_rate
FROM analytics.daily_aggregates d
WHERE d.date >= CURRENT_DATE - INTERVAL '14 days'
ORDER BY d.date DESC;
```

---

### Department Stats (Last 7 days)

```sql
SELECT
    dept.name,
    dept.code,
    COALESCE(SUM(ds.total_questions), 0) as questions,
    COALESCE(SUM(ds.unique_users), 0) as active_users,
    COALESCE(SUM(ds.likes), 0) as likes,
    COALESCE(SUM(ds.dislikes), 0) as dislikes
FROM core.departments dept
LEFT JOIN analytics.department_daily_stats ds
    ON ds.department_id = dept.id
    AND ds.date >= CURRENT_DATE - INTERVAL '7 days'
WHERE dept.is_active = true
GROUP BY dept.id, dept.name, dept.code
ORDER BY questions DESC;
```

---

### Unanswered Questions for Review

```sql
SELECT
    uq.id,
    uq.question,
    uq.top_similarity_score,
    uq.priority,
    uq.created_at,
    u.full_name as user_name,
    u.email as user_email
FROM conversation.unanswered_questions uq
JOIN core.users u ON u.id = uq.user_id
WHERE uq.resolved = false
ORDER BY
    CASE uq.priority
        WHEN 'HIGH' THEN 1
        WHEN 'MEDIUM' THEN 2
        WHEN 'LOW' THEN 3
    END,
    uq.created_at DESC
LIMIT 100;
```

---

## Performance Tips

### Use EXPLAIN ANALYZE

```sql
EXPLAIN ANALYZE
SELECT ... FROM knowledge.chunks
WHERE embedding_vector <=> :vector < 0.3
LIMIT 50;
```

Check for:
- **Index Scan** on `idx_chunks_embedding_hnsw` (good)
- **Bitmap Index Scan** on GIN indexes for ACL filters (good)
- **Seq Scan** on large tables (bad - add index)

### Avoid SELECT *

Only select needed columns. For chunks, avoid fetching `embedding_vector` unless doing vector search:
```sql
-- Bad (returns 1024 extra floats per row)
SELECT * FROM knowledge.chunks;

-- Good
SELECT id, document_id, content, section_title, allowed_roles FROM knowledge.chunks;
```

---

## Transaction Boundaries

### Ingestion Transaction Pattern

```python
async def process_ingestion(document_id, version_id, chunks):
    async with async_session_factory() as session:
        try:
            # 1. Invalidate old chunks
            await session.execute("""
                UPDATE knowledge.chunks
                SET is_latest = false, updated_at = NOW()
                WHERE document_id = :document_id AND is_latest = true
            """, {"document_id": document_id})

            # 2. Bulk insert new chunks
            await chunk_repo.bulk_insert(session, chunks)

            # 3. Update document metadata
            await session.execute("""
                UPDATE knowledge.documents
                SET extracted_text = :extracted_text,
                    page_count = :page_count,
                    word_count = :word_count,
                    chunking_strategy = :strategy,
                    embedding_model = :model,
                    embedding_dimension = :dim,
                    updated_at = NOW()
                WHERE id = :document_id
            """, {...})

            # 4. Update version as current
            await session.execute("""
                UPDATE knowledge.document_versions
                SET is_current = true
                WHERE id = :version_id
            """, {"version_id": version_id})

            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

All operations in one transaction ensure consistency.

---

## Related References

- **Full Schema Definitions**: `contexts/database/tables/*.md` - complete column details
- **Authorization Queries**: `contexts/authorization/dual-strategy.md` - ACL patterns
- **Indexes**: `contexts/database/indexes.md` - index creation SQL
- **Migrations**: `contexts/database/migrations.md` - schema change procedures

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
