---
title: Database Migrations & Schema Changes
description: Procedures for making database schema changes safely in Poliwise
type: database
version: 1.0
---

# Database Migrations

## Purpose

This document defines the **safe, standardized procedures** for making database schema changes (adding tables, columns, indexes, constraints) in the Poliwise PostgreSQL database.

## When to Use

- Adding new tables or columns
- Creating or modifying indexes
- Changing constraints
- Adding ENUM types
- Database refactoring (expensive queries)

---

## General Migration Principles

1. **All changes must be backwards compatible** (zero-downtime):
   - Adding new columns: Allow NULL or have safe default
   - Adding new tables: No impact on existing queries
   - Adding indexes: Non-blocking, can be created CONCURRENTLY
   - Never DROP or RENAME columns in production without deprecation cycle

2. **Follow deployment order**:
   - Deploy application code that tolerates old schema FIRST
   - Apply database migration SECOND
   - Deploy application code that uses new features THIRD

3. **Always test migrations on staging** with production-like data volume before applying to production.

---

## Migration Types & Templates

### 1. Add New Column (Safe - Non-Breaking)

```sql
-- Add column with NULL allowed (safest)
ALTER TABLE metadata.document_metadata
ADD COLUMN IF NOT EXISTS source_system VARCHAR(50) NULL;

-- OR add with DEFAULT (fills existing rows)
ALTER TABLE knowledge.documents
ADD COLUMN IF NOT EXISTS processing_priority INT NOT NULL DEFAULT 0;
```

**Why NULL allowed?**: Existing rows unaffected. Application can check `IS NULL` for old data.

**If NOT NULL required**: Use two-step:
```sql
-- Step 1: Add as NULL
ALTER TABLE analytics.feedbacks
ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP NULL;

-- Step 2: Backfill data (application code or SQL UPDATE)
UPDATE analytics.feedbacks
SET resolved_at = created_at
WHERE resolved = true AND resolved_at IS NULL;

-- Step 3: Alter to NOT NULL (only after backfill complete)
ALTER TABLE analytics.feedbacks
ALTER COLUMN resolved_at SET NOT NULL;
```

---

### 2. Create Index (Non-Blocking)

```sql
-- Use CONCURRENTLY to avoid table locks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_uploaded_by
ON knowledge.documents (uploaded_by);

-- For partial indexes (very efficient)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_latest_children
ON knowledge.chunks (document_id, chunk_index)
WHERE is_latest = true AND chunk_type = 'child';

-- For GIN indexes (JSONB, arrays)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_allowed_roles
ON knowledge.chunks USING GIN (allowed_roles);
```

**CONCURRENTLY**: Allows reads/writes during index build. Can take longer but avoids blocking production.

**When NOT to use CONCURRENTLY**: In transaction scripts that need atomic multiple index creation; just be prepared for longer locks.

---

### 3. Add New Table

```sql
CREATE TABLE IF NOT EXISTS metadata.custom_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_metadata_id UUID NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT,
    created_by UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,

    CONSTRAINT fk_custom_fields_document
        FOREIGN KEY (document_metadata_id)
        REFERENCES metadata.document_metadata(id)
        ON DELETE CASCADE,

    CONSTRAINT uniq_document_field
        UNIQUE (document_metadata_id, field_name)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_custom_fields_doc_id
ON metadata.custom_fields (document_metadata_id);
```

**Best Practice**: Always include standard columns: `id`, `created_at`, `updated_at`, `deleted_at` (soft delete).

---

### 4. Add ENUM Type (Breaking - Requires Care)

**ENUM changes are NOT reversible without table rewrite**. Plan carefully.

```sql
-- Add new value to existing ENUM (safe, does not rewrite table)
ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'EXPIRED';

-- NOTE: Cannot remove or reorder enum values. Cannot rename safely.

-- If you need to change enum values, create new type and migrate:
-- 1. Create new type
CREATE TYPE document_status_v2 AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED', 'EXPIRED');

-- 2. Alter column to use new type (this rewrites table!)
ALTER TABLE metadata.document_metadata
ALTER COLUMN status TYPE document_status_v2
USING status::text::document_status_v2;

-- 3. Drop old type (only after all services updated)
DROP TYPE IF EXISTS document_status;
ALTER TYPE document_status_v2 RENAME TO document_status;
```

**Warning**: `ALTER COLUMN TYPE` on large tables locks and rewrites entire table. Do during maintenance window or use `USING` with concurrent approach (complex).

---

### 5. Add Foreign Key Constraint (Use Care)

```sql
-- Verify no orphaned rows first
SELECT COUNT(*) FROM knowledge.chunks c
LEFT JOIN knowledge.documents d ON d.id = c.document_id
WHERE d.id IS NULL;

-- If count > 0, fix data before adding constraint

-- Add constraint (will scan table to validate)
ALTER TABLE knowledge.chunks
ADD CONSTRAINT fk_chunks_document
    FOREIGN KEY (document_id)
    REFERENCES knowledge.documents(id)
    ON DELETE CASCADE
    NOT DEFERRABLE;  -- Default, immediate enforcement
```

**Tip**: Add `ON DELETE SET NULL` if you want to preserve child rows when parent deleted.

---

### 6. Modify Column Type (Breaking, High-Risk)

Requires table rewrite. Plan maintenance window.

```sql
-- Example: Increase VARCHAR length
ALTER TABLE metadata.document_metadata
ALTER COLUMN title TYPE VARCHAR(1000);

-- OR convert TEXT to VARCHAR with check constraint
ALTER TABLE core.users
ALTER COLUMN email TYPE VARCHAR(255)
USING email::varchar(255);

-- Verify data fits: SELECT MAX(LENGTH(email)) FROM core.users; < 255
```

---

## pgvector Specific Migrations

### Enable pgvector Extension

```sql
-- Run once per database
CREATE EXTENSION IF NOT EXISTS vector;
```

### Add embedding_vector Column with HNSW Index

```sql
-- 1. Add column (if not exists)
ALTER TABLE knowledge.chunks
ADD COLUMN IF NOT EXISTS embedding_vector vector(1024);

-- 2. Create HNSW index concurrently
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_hnsw
ON knowledge.chunks
USING hnsw (embedding_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters**:
- `m`: HNSW "maximum number of connections" (4-64, default 16). Higher = better recall, slower insert.
- `ef_construction`: Size of dynamic candidate list during index build (64-100). Higher = better quality, slower build.

**Changing dimensions**: Cannot alter `vector(n)` dimension directly. Must:
1. Add new column `embedding_vector_v2 vector(new_dim)`
2. Backfill with re-embedded vectors (via ingestion-service)
3. Drop old column, rename new column

---

### Full-Text Search (TSVECTOR)

```sql
-- Add generated column for tsvector
ALTER TABLE knowledge.chunks
ADD COLUMN IF NOT EXISTS content_tsv TSVECTOR
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Create GIN index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_content_tsv
ON knowledge.chunks USING GIN (content_tsv);

-- Query using tsquery
SELECT * FROM knowledge.chunks
WHERE content_tsv @@ to_tsquery('english', 'policy & timeoff')
ORDER BY ts_rank(content_tsv, to_tsquery('english', 'policy & timeoff')) DESC;
```

**Note**: English dictionary is available by default in PostgreSQL.

---

## Rollback Strategy

### Safe Rollback Template

```sql
-- 1. Verify deployment success before rolling back
-- 2. Reverse migration in opposite order

-- IF you added column:
ALTER TABLE analytics.feedbacks
DROP COLUMN IF EXISTS resolved_at;

-- IF you added index:
DROP INDEX IF EXISTS idx_documents_uploaded_by;

-- IF you added table:
DROP TABLE IF EXISTS metadata.custom_fields;

-- IF you added ENUM value (can't remove easily, just ignore)
-- ENUM values are effectively permanent; document as deprecated
```

**Best Practice**: Write rollback SQL at same time as forward migration, test both in staging.

---

## Migration Script Template

Create timestamped SQL files in `infrastructure/migrations/`:

```sql
-- File: 20240115-1700-add-resolved-at-to-feedbacks.sql
-- Description: Add resolved_at column to track when unanswered questions get resolved
-- Author: Architecture Team
-- DB: analytics

BEGIN;

-- Check if already applied (idempotent)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'analytics'
          AND table_name = 'feedbacks'
          AND column_name = 'resolved_at'
    ) THEN
        ALTER TABLE analytics.feedbacks
        ADD COLUMN resolved_at TIMESTAMP NULL;
    END IF;
END $$;

-- Create index concurrently (runs in separate transaction internally)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feedbacks_resolved_at
ON analytics.feedbacks (resolved_at);

COMMIT;

-- ROLLBACK (uncomment to rollback):
-- ALTER TABLE analytics.feedbacks DROP COLUMN IF EXISTS resolved_at;
-- DROP INDEX IF EXISTS idx_feedbacks_resolved_at;
```

**Apply**:
```bash
psql -h localhost -U poliwise -d poliwise -f migrations/20240115-1700-add-resolved-at-to-feedbacks.sql
```

---

## Local Bootstrap Baseline (Mode A)

Use this flow for local Docker development when bringing up the baseline stack.

1. The `postgres` container auto-runs `infrastructure/init-db/init.sql` on first boot.
2. That init script loads SQL files from:
    - `docs/supbase_sql/`
    - `docs/supbase_sql_update_v1/`
3. Supabase-specific RLS script (`docs/supbase_sql/row_level_security.sql`) is intentionally excluded from default bootstrap.

### Command Sequence

```bash
# Start infra
docker compose up -d postgres rabbitmq minio

# Verify schemas
docker compose exec -T postgres psql -U poliwise -d poliwise -c "\\dn"

# Start application services
docker compose up -d auth-service user-service knowledge-service metadata-service feedback-service api-gateway frontend
```

### Reinitialize Database

```bash
docker compose down
docker volume rm poliwise_postgres_data
docker compose up -d postgres
```

---

## Automated Migration Tools

### Option 1: Flyway (Java)

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
```

```bash
# Configuration in application.yml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
```

Naming: `V1__Create_initial_schema.sql`, `V2__Add_resolved_at_to_feedbacks.sql`

### Option 2: Alembic (Python)

```python
# alembic/env.py - configure
alembic init alembic

# Generate migration
alembic revision -m "add resolved_at column"

# Edit generated file in alembic/versions/
def upgrade():
    op.add_column('feedbacks', sa.Column('resolved_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_feedbacks_resolved_at'), 'feedbacks', ['resolved_at'])

def downgrade():
    op.drop_index(op.f('ix_feedbacks_resolved_at'), table_name='feedbacks')
    op.drop_column('feedbacks', 'resolved_at')
```

---

## Monitoring Post-Migration

After applying migration to production:

1. **Check query plans** changed?
   ```sql
   EXPLAIN ANALYZE SELECT * FROM knowledge.chunks WHERE ...;
   ```

2. **Monitor index bloat**:
   ```sql
   SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexrelid))
   FROM pg_stat_user_indexes
   WHERE schemaname = 'knowledge';
   ```

3. **Watch for slow queries** in application logs (increase in p99 latency)

4. **Verify connection pool** not exhausted (long-running migrations can hold connections)

---

## Emergency Procedures

### Stuck Long-Running Migration

If `ALTER TABLE` is running for > 1 hour on large table:

1. **Do NOT cancel** (could leave database in inconsistent state)
2. Wait for completion
3. For future, use `CONCURRENTLY` or logical replication approach

### Deadlock Detection

```sql
SELECT * FROM pg_stat_activity
WHERE state = 'active' AND wait_event_type = 'Lock';

SELECT pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid = <blocked_pid>;
```

If migration causes deadlock:
1. Cancel one of the blocking sessions (`SELECT pg_terminate_backend(pid)`)
2. Fix migration to use `NOWAIT` or `SKIP LOCKED`

### Data Corruption from Buggy Migration

If data is corrupted:
1. **Stop deployment**, don't propagate to all instances
2. Restore from backup:
   ```bash
   pg_dump -h backup_host -U postgres poliwise > restore.sql
   psql -h localhost -U postgres poliwise < restore.sql
   ```
3. Fix migration SQL
4. Re-deploy

---

## References

- **Schema Definitions**: `contexts/database/tables/*.md` - what columns to add
- **Indexes**: `contexts/database/indexes.md` - recommended indexes
- **Performance**: `contexts/database/queries.md` - query patterns
- **Service Ownership**: `contexts/service-boundaries/responsibilities.md`

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
**Critical**: All migrations require review from at least one senior engineer.
