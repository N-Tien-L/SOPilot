---
title: Dual-Strategy Authorization Pattern
description: Detailed technical specification for document access control and AI retrieval ACL
type: authorization
version: 1.0
related:
  - contexts/database/schema.md
  - contexts/architecture/system-overview.md
---

# Dual-Strategy Authorization Pattern

## Purpose

This document defines the strict Dual-Strategy Authorization pattern used for document access control and AI knowledge retrieval (RAG) in Poliwise. **AI agents MUST follow this pattern** when implementing SQL queries for document permissions or when designing new permission-related features.

## Core Concept Overview

We trade **eventual consistency** for **extreme read performance** during AI searches. The system maintains two parallel authorization flows:

1. **Real-time Flow (Source of Truth)**: Uses `metadata.document_access_rules` for direct CRUD operations. Provides 100% accuracy.
2. **Read-Optimized Flow (Flattened)**: Uses pre-computed arrays (`allowed_roles`, `allowed_departments`, `allowed_users`) stored in `knowledge.chunks` for AI vector search. Provides O(1) permission checks during high-throughput retrieval.

### Why This Hybrid Approach?

- **AI Search Requirements**: Vector search queries retrieve top-k chunks from potentially millions. Each query needs to filter results by user permissions within milliseconds. Joining `metadata.document_access_rules` for every chunk would be prohibitively slow (complex OR conditions across multiple rows).
- **Permission Change Frequency**: Document permissions are relatively static (change maybe 1-2 times per document per month). Real-time accuracy during CRUD is critical; slight delay during AI search is acceptable.
- **Scale**: With 10,000 documents × 100 chunks each = 1M chunks. Flattened arrays allow indexed array containment checks (`@>` operator) which are extremely fast with GIN indexes.

## Architecture Components

### Source of Truth Schema

**Table**: `metadata.document_access_rules`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_metadata_id` | UUID | FK to `metadata.document_metadata` |
| `target_type` | ENUM ('ROLE' \| 'USER' \| 'DEPARTMENT') | Type of permission target |
| `target_role` | ENUM ('USER' \| 'MANAGER' \| 'ADMIN') \| NULL | Role if target_type = 'ROLE' |
| `target_department_id` | UUID \| NULL | Department FK if target_type = 'DEPARTMENT' |
| `target_user_id` | UUID \| NULL | User FK if target_type = 'USER' |
| `permission` | ENUM ('VIEW' \| 'EDIT' \| 'MANAGE') | Permission level |
| `created_by` | UUID | Who created this rule |
| `created_at` | TIMESTAMP | Creation timestamp |

**Sample Rules** for a document:
```sql
-- Allow all authenticated users
INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, permission)
VALUES (?, 'ROLE', 'VIEW');  -- Implicit: applies to USER, MANAGER, ADMIN

-- Allow specific department
INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_department_id, permission)
VALUES (?, 'DEPARTMENT', 'dept-uuid', 'VIEW');

-- Deny specific user
INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_user_id, permission)
VALUES (?, 'USER', 'user-uuid', 'DENY');
```

### Read-Optimized Schema

**Table**: `knowledge.chunks` (flattened ACL columns)

| Column | Type | Description | Derived From |
|--------|------|-------------|--------------|
| `allowed_roles` | TEXT[] | Array of roles that can access this chunk | `ARRAY_AGG(target_role)` from `document_access_rules` where `permission = 'VIEW'` and `target_type = 'ROLE'` |
| `allowed_departments` | UUID[] | Array of department IDs that can access | `ARRAY_AGG(target_department_id)` from `document_access_rules` where `permission = 'VIEW'` and `target_type = 'DEPARTMENT'` UNION with `document_metadata.access_level = 'DEPARTMENT_ONLY'` → `department_id` |
| `allowed_users` | UUID[] | Array of specific user IDs that can access | `ARRAY_AGG(target_user_id)` from `document_access_rules` where `permission = 'VIEW'` and `target_type = 'USER'` |
| `access_level` | VARCHAR | 'PUBLIC' or 'DEPARTMENT_ONLY' | From `metadata.document_metadata.access_level` |

**Important**: These arrays are **denormalized** into each chunk row for that document. When permissions change, we batch-update all chunks for that document.

## Workflow Implementation

### Workflow 1: Initial Document Upload (Baking Permissions)

This workflow ensures chunks are created with correct flattened ACLs in a single transaction.

**Actors**: Admin user → Knowledge Service → Ingestion Service

**Steps**:

1. **Admin uploads document** via UI
2. **Knowledge Service** (`:8083`) handles upload:
   ```java
   // 1. Upload file to MinIO
   String fileKey = minioService.upload(file);
   
   // 2. Create DB records
   Document document = documentRepository.save(new Document(fileKey, ...));
   DocumentVersion version = documentVersionRepository.save(new DocumentVersion(document.getId(), 1));
   ProcessingJob job = processingJobRepository.save(new ProcessingJob(document.getId(), version.getId(), "INGESTION"));
   
   // 3. Fetch metadata from metadata-service (HTTP call or cached)
   DocumentMetadataResponse metadata = metadataServiceClient.getMetadataForDocument(document.getId());
   
   // 4. Publish RabbitMQ event
   rabbitTemplate.convertAndSend(
       "poliwise.events",
       "ingestion.requested",
       new IngestionRequestedEvent(
           document.getId(),
           version.getId(),
           fileKey,
           bucketName,
           job.getId(),
           metadata.getAccessRules(),  // ← flattened ACL data
           metadata.getDocumentMetadata()
       )
   );
   ```

3. **Ingestion Service** (`:8088`) consumes `ingestion.requested`:
   ```python
   async def on_ingestion_requested(event):
       # 1. Download file from MinIO
       file_bytes = await minio_service.download(event.file_key, event.bucket_name)
       
       # 2. Extract text
       extracted = await extractor.extract(file_bytes)
       
       # 3. Standardize
       structured = standardizer.normalize(extracted.raw_text)
       
       # 4. Chunk with metadata assignment (CRITICAL!)
       chunks = chunker.chunk(
           structured,
           metadata={
               'allowed_roles': event.metadata.allowed_roles,        # ← from payload
               'allowed_departments': event.metadata.allowed_departments,
               'access_level': event.metadata.access_level,
               'document_metadata': event.document_metadata
           }
       )
       
       # 5. Generate embeddings
       embeddings = await embedding_service.embed_batch([c.content for c in chunks])
       for chunk, embedding in zip(chunks, embeddings):
           chunk.embedding_vector = embedding
       
       # 6. Store in single transaction
       async with db_session() as session:
           await chunk_repo.bulk_insert(chunks)  # INSERT with ACL arrays
           await document_repo.update_extraction_results(...)
           await job_repo.mark_completed(event.job_id)
           await session.commit()
       
       # 7. Publish document.uploaded event
       await publish_document_uploaded(event.document_id, event.version_id)
   ```

**Critical**: The ACL arrays are assigned to each chunk **during chunk creation** from the event payload. No additional DB lookups needed.

### Workflow 2: Permission Update (Background Flattening)

When admin changes document permissions, the system asynchronously updates all chunks for that document.

**Actors**: Admin → Metadata Service → RabbitMQ → Ingestion Service (background worker)

**Steps**:

1. **Admin updates permissions** via UI (e.g., "Allow Department: Sales")
2. **Metadata Service** (`:8084`) updates `metadata.document_access_rules`:
   ```sql
   INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_department_id, permission)
   VALUES (?, 'DEPARTMENT', 'sales-dept-uuid', 'VIEW');
   ```

3. **Metadata Service** publishes event:
   ```java
   rabbitTemplate.convertAndSend(
       "poliwise.events",
       "document.permissions.changed",
       new DocumentPermissionsChangedEvent(documentId)
   );
   ```

4. **Ingestion Service** (or dedicated permission-sync service) consumes event:
   ```python
   async def on_permissions_changed(event):
       document_id = event.document_id
       
       # Fetch latest access rules from metadata service (HTTP call)
       metadata = await metadata_service_client.get_document_access_rules(document_id)
       
       # Calculate flattened arrays
       flattened = {
           'allowed_roles': metadata.get_allowed_roles(),
           'allowed_departments': metadata.get_allowed_departments(),
           'access_level': metadata.access_level
       }
       
       # Batch update all chunks for this document
       await chunk_repo.update_acls(
           document_id=document_id,
           allowed_roles=flattened['allowed_roles'],
           allowed_departments=flattened['allowed_departments'],
           access_level=flattened['access_level']
       )
       
       logger.info("Chunk ACLs synchronized", document_id=document_id)
   ```

**SQL for Batch Update**:
```sql
UPDATE knowledge.chunks
SET
    allowed_roles = :allowed_roles,
    allowed_departments = :allowed_departments,
    access_level = :access_level,
    updated_at = NOW()
WHERE
    document_id = :document_id
    AND is_latest = true;
```

**Consistency Model**: Eventual consistency. After the update completes (typically < 1 second), all new AI queries will see the updated permissions. There is a small race window where a query in-flight during the update might use stale permissions.

### Workflow 3: AI Vector Search Query (Read-Optimized)

This is the hot path that must be extremely fast. Uses pre-flattened ACLs in `knowledge.chunks`.

**Actors**: User → API Gateway → AI Q&A Service → PostgreSQL

**Steps**:

1. **User** sends chat query with JWT
2. **Gateway** validates JWT, extracts claims:
   ```json
   {
     "sub": "user-uuid",
     "role": "USER",
     "department_id": "dept-uuid"
   }
   ```
   Injects as headers:
   ```
   X-User-Id: user-uuid
   X-Role: USER
   X-Department-Id: dept-uuid
   ```

3. **AI Q&A Service** (`:8086`) receives request:
   ```python
   user_id = request.headers.get('X-User-Id')
   user_role = request.headers.get('X-Role')  # 'USER', 'MANAGER', 'ADMIN'
   user_dept_id = request.headers.get('X-Department-Id')
   ```

4. **Generate query embedding** via embedding service:
   ```python
   query_embedding = await embedding_service.embed_single(query)
   ```

5. **Execute hybrid search with ACL filter**:
   ```sql
   -- Dense vector search with pre-flattened ACL arrays
   SELECT
       c.id,
       c.content,
       c.embedding_vector <=> :query_vector AS similarity_score,
       d.title AS document_title,
       dm.status,
       dm.access_level
   FROM knowledge.chunks c
   JOIN knowledge.documents d ON d.id = c.document_id
   JOIN metadata.document_metadata dm ON dm.document_id = d.id
   WHERE
       c.is_latest = true
       AND c.chunk_type = 'child'
       AND dm.status = 'PUBLISHED'
       AND dm.effective_date <= NOW()
       AND (dm.expiry_date IS NULL OR dm.expiry_date > NOW())
       -- CRITICAL: ACL filter using flattened arrays
       AND (
           c.access_level = 'PUBLIC'
           OR (:user_role IS NOT NULL AND c.allowed_roles @> ARRAY[:user_role]::TEXT[])
           OR (:user_dept_id IS NOT NULL AND c.allowed_departments @> ARRAY[:user_dept_id]::UUID[])
           OR (:user_id IS NOT NULL AND c.allowed_users @> ARRAY[:user_id]::UUID[])
       )
       AND dm.deleted_at IS NULL
   ORDER BY c.embedding_vector <=> :query_vector
   LIMIT 50;
   ```

**Performance Note**: The `@>` (array contains) operator with GIN indexes is O(log n) regardless of array size. Ensure these indexes exist:
```sql
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_roles ON knowledge.chunks USING GIN (allowed_roles);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_departments ON knowledge.chunks USING GIN (allowed_departments);
CREATE INDEX IF NOT EXISTS idx_chunks_allowed_users ON knowledge.chunks USING GIN (allowed_users);
```

### Workflow 4: Real-time Permission Check (CRUD Operations)

When a user directly requests a document (view, download, edit), use the **source-of-truth** `metadata.document_access_rules` for accurate, up-to-date permissions.

**Example**: Check if user can view document
```sql
SELECT check_document_access(
    p_user_id := :user_id,
    p_document_id := :document_id
) AS has_access;
```

**Function Implementation** (stored procedure):
```sql
CREATE OR REPLACE FUNCTION check_document_access(
    p_user_id UUID,
    p_document_id UUID
) RETURNS BOOLEAN AS $$
DECLARE
    v_user_role TEXT;
    v_user_department_id UUID;
    v_metadata_record RECORD;
    has_specific_deny BOOLEAN := FALSE;
    has_specific_allow BOOLEAN := FALSE;
BEGIN
    -- Lấy thông tin user (query to core.users)
    SELECT role, department_id INTO v_user_role, v_user_department_id
    FROM core.users
    WHERE id = p_user_id AND deleted_at IS NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Lấy metadata tài liệu
    SELECT * INTO v_metadata_record
    FROM metadata.document_metadata
    WHERE document_id = p_document_id AND deleted_at IS NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- 1. Kiểm tra quy tắc DENY (highest priority)
    SELECT TRUE INTO has_specific_deny
    FROM metadata.document_access_rules dar
    WHERE dar.document_metadata_id = v_metadata_record.id
      AND dar.permission = 'DENY'
      AND (
          (dar.target_type = 'USER' AND dar.target_user_id = p_user_id)
          OR (dar.target_type = 'ROLE' AND dar.target_role = v_user_role)
          OR (dar.target_type = 'DEPARTMENT' AND dar.target_department_id = v_user_department_id)
      )
    LIMIT 1;

    IF has_specific_deny THEN
        RETURN FALSE;
    END IF;

    -- 2. Kiểm tra quy tắc VIEW tường minh
    SELECT TRUE INTO has_specific_allow
    FROM metadata.document_access_rules dar
    WHERE dar.document_metadata_id = v_metadata_record.id
      AND dar.permission = 'VIEW'
      AND (
          (dar.target_type = 'USER' AND dar.target_user_id = p_user_id)
          OR (dar.target_type = 'ROLE' AND dar.target_role = v_user_role)
          OR (dar.target_type = 'DEPARTMENT' AND dar.target_department_id = v_user_department_id)
      )
    LIMIT 1;

    IF has_specific_allow THEN
        RETURN TRUE;
    END IF;

    -- 3. Fallback to access_level
    IF v_metadata_record.access_level = 'PUBLIC' THEN
        RETURN TRUE;
    END IF;

    IF v_metadata_record.access_level = 'DEPARTMENT_ONLY'
       AND v_metadata_record.department_id = v_user_department_id THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;
```

**Priority Order**:
1. Explicit DENY for user/role/department → **always deny**
2. Explicit VIEW grant for user/role/department → **allow**
3. `access_level = 'PUBLIC'` → **allow all authenticated users**
4. `access_level = 'DEPARTMENT_ONLY'` + user in same department → **allow**
5. Default: **deny**

## Implementation Checklist

When implementing features that touch authorization:

- [ ] **For AI search queries**: Always use flattened ACL arrays (`allowed_roles`, `allowed_departments`, `allowed_users`, `access_level`) on `knowledge.chunks`.
- [ ] **For document CRUD**: Always check `metadata.document_access_rules` via stored function or equivalent logic in application code.
- [ ] **For chunk ingestion**: Assign flattened ACLs from event payload **before** inserting chunks.
- [ ] **For permission updates**: Publish event and ensure background sync job updates all affected chunks.
- [ ] **Indexes exist**: Verify GIN indexes on all ACL array columns in `knowledge.chunks`.
- [ ] **Soft delete handling**: Always include `deleted_at IS NULL` in permission-related queries.
- [ ] **Test coverage**: Include tests for all three workflows (upload, permission change, query).

## Common Pitfalls & How to Avoid

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Cross-schema joins in AI query | Slow query (>100ms), full table scan | Use flattened ACLs, don't join `document_access_rules` during vector search |
| Forgetting `is_latest = true` filter | Stale chunks from previous versions appear in results | Always include `WHERE c.is_latest = true` |
| Not indexing ACL arrays | Permissions filter uses sequential scan → slow | Create GIN indexes: `CREATE INDEX idx_chunks_allowed_roles ON knowledge.chunks USING GIN (allowed_roles)` |
| Race condition during permission update | User sees old permissions for a few seconds | Acceptable (eventual consistency). If critical, add synchronization lock or short delay |
| Direct chunk modification | Ingested chunks lose ACLs, security breach | Never UPDATE `knowledge.chunks` directly in feature code. Only ingestion-service manages chunks |
| Missing `deleted_at IS NULL` | Deleted documents still appear in search | Add to all queries on `metadata.document_metadata` and `knowledge.documents` |

## Performance Benchmarks & Tuning

| Query Type | Expected Latency (p99) | Optimization Tips |
|------------|----------------------|------------------|
| AI search with ACL filter | < 50ms | Ensure HNSW index on `embedding_vector`, GIN indexes on ACL arrays, composite index on `(is_latest, chunk_type)` |
| Permission check (CRUD) | < 10ms | This is a simple lookup; ensure `document_metadata_id` index on `document_access_rules` |
| Permission sync (batch update) | < 500ms for 1000 chunks | Update in batches of 100, use `WHERE document_id = ? AND is_latest = true` |

## SQL Reference Quick Card

### Insert Flattened ACLs (Ingestion)
```sql
INSERT INTO knowledge.chunks (
    id, document_id, document_version_id, chunk_type, content,
    embedding_vector, embedding_model, embedding_dimension,
    allowed_roles, allowed_departments, allowed_users, access_level,
    is_latest, created_at
) VALUES (
    :id, :document_id, :document_version_id, 'child', :content,
    :embedding_vector, 'BGE-M3', 1024,
    :allowed_roles, :allowed_departments, :allowed_users, :access_level,
    true, NOW()
);
```

### AI Search Query (with hybrid search)
```sql
WITH dense_search AS (
    SELECT c.*, c.embedding_vector <=> :query_vector AS dense_score
    FROM knowledge.chunks c
    JOIN knowledge.documents d ON d.id = c.document_id
    JOIN metadata.document_metadata dm ON dm.document_id = d.id
    WHERE c.is_latest = true
      AND c.chunk_type = 'child'
      AND dm.status = 'PUBLISHED'
      AND dm.effective_date <= NOW()
      AND (dm.expiry_date IS NULL OR dm.expiry_date > NOW())
      AND (
          c.access_level = 'PUBLIC'
          OR c.allowed_roles @> ARRAY[:user_role]::TEXT[]
          OR c.allowed_departments @> ARRAY[:user_dept_id]::UUID[]
          OR c.allowed_users @> ARRAY[:user_id]::UUID[]
      )
      AND dm.deleted_at IS NULL
      ORDER BY c.embedding_vector <=> :query_vector
      LIMIT 50
)
SELECT * FROM dense_search
ORDER BY dense_score ASC
LIMIT 10;
```

### Batch Update ACLs (Permission Sync)
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

## Migration & Idempotency

### Initial Backfill (for existing documents without chunks)

If you have existing documents with chunks that don't have ACL arrays populated:

```python
async def backfill_acl_for_existing_documents(batch_size=100):
    # 1. Fetch all documents missing ACLs
    documents = await db.fetch_all("""
        SELECT d.id FROM knowledge.documents d
        LEFT JOIN knowledge.chunks c ON d.id = c.document_id AND c.is_latest = true
        WHERE c.id IS NULL OR c.allowed_roles IS NULL
        GROUP BY d.id
    """)
    
    for doc in documents:
        # 2. Fetch access rules from metadata
        metadata = await metadata_service_client.get_document_access_rules(doc['id'])
        
        # 3. Calculate flattened arrays (same as ingestion)
        flattened = calculate_flattened_acl(metadata)
        
        # 4. Update chunks
        await db.execute("""
            UPDATE knowledge.chunks
            SET allowed_roles = :allowed_roles,
                allowed_departments = :allowed_departments,
                allowed_users = :allowed_users,
                access_level = :access_level
            WHERE document_id = :document_id AND is_latest = true
        """, flattened)
        
        logger.info("Backfilled ACL", document_id=doc['id'])
```

### Idempotency During Permission Updates

The batch update is **idempotent**: running it multiple times with the same flattened arrays produces the same result. This is crucial for RabbitMQ message redelivery.

## Testing Strategy

### Unit Tests

Test ACL calculation logic:
```python
def test_flatten_acl_from_rules():
    rules = [
        DocumentAccessRule(target_type='ROLE', target_role='USER', permission='VIEW'),
        DocumentAccessRule(target_type='DEPARTMENT', target_department_id='dept-1', permission='VIEW'),
        DocumentAccessRule(target_type='USER', target_user_id='user-1', permission='VIEW'),
        DocumentAccessRule(target_type='ROLE', target_role='MANAGER', permission='DENY'),
    ]
    
    flattened = calculate_flattened_acl(rules, access_level='PUBLIC')
    
    assert flattened.allowed_roles == ['USER']  # Only VIEW, exclude DENY
    assert flattened.allowed_departments == ['dept-1']
    assert flattened.allowed_users == ['user-1']
    assert flattened.access_level == 'PUBLIC'
```

### Integration Tests

Test full query with ACL filter returns only authorized chunks:
```python
@pytest.mark.asyncio
async def test_ai_search_acl_filter():
    # Setup: Create chunks with different ACLs
    await create_chunk(
        document_id='doc1',
        allowed_roles=['USER'],
        access_level='PUBLIC'
    )
    await create_chunk(
        document_id='doc2',
        allowed_roles=['ADMIN'],
        access_level='PUBLIC'
    )
    
    # Execute search as USER role
    results = await ai_service.hybrid_search(
        query="test query",
        user_role='USER',
        user_dept_id=None,
        user_id='user-uuid'
    )
    
    # Assert: Only USER-accessible chunk returned
    assert len(results) == 1
    assert results[0].document_id == 'doc1'
```

### Performance Tests

Load test the ACL filter:
```sql
-- Use EXPLAIN ANALYZE
EXPLAIN ANALYZE
SELECT c.id FROM knowledge.chunks c
WHERE c.is_latest = true
  AND (c.allowed_roles @> ARRAY['USER'] OR c.access_level = 'PUBLIC')
LIMIT 100;
```

Expected: Index scan using GIN index, < 5ms execution time for 1M chunks.

## References

- **Database Schema**: `contexts/database/schema.md` - complete table definitions
- **System Architecture**: `contexts/architecture/system-overview.md` - component interactions
- **Implementation Plans**: `contexts/development/extraction-plan.md` - ingestion pipeline details
- **Event Contracts**: `contexts/service-boundaries/events.md` - RabbitMQ events

---

**CRITICAL**: This pattern is fundamental to Poliwise's security and performance. Do not deviate without architectural review.
