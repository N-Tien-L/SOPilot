# Database Migration Strategy

**Created At**: 2026-04-11
**Purpose**: How to migrate existing PostgreSQL databases to the new schema

---

## When This Applies

- You have an **existing** Poliwise database with older schema
- You need to update to the new schema (pgvector, new columns, ENUM types, etc.)
- You do NOT want to lose data by dropping and recreating

## When This Does NOT Apply

- Fresh install — just run `docker compose up -d postgres`, init scripts handle everything
- Development environment — run `reset-and-bootstrap.ps1` to start fresh

---

## Migration Phases

### Phase 1: pgvector Extension

```sql
-- Must be run BEFORE any vector column is added
-- Requires pgvector extension installed in PostgreSQL
CREATE EXTENSION IF NOT EXISTS vector;
```

**Note**: If your PostgreSQL image is `postgres:16-alpine`, you MUST switch to `pgvector/pgvector:pg16` in docker-compose.yml first, then recreate the container.

### Phase 2: Knowledge Schema (vector columns, GitLab fields, ACL)

```sql
-- Run: docs/supbase_sql/migrations/001_knowledge_vector_and_acl.sql
```

This migration adds:
- `embedding_vector vector(1024)` to `knowledge.chunks` and `knowledge.embedding_cache`
- `section_title`, `section_level`, `section_path` to `knowledge.chunks`
- `allowed_roles`, `allowed_departments`, `allowed_users`, `access_level` to `knowledge.chunks`
- `chunk_type` ENUM type and column
- `is_latest`, `parent_chunk_id`, `document_version_id` FK to `knowledge.chunks`
- `content_tsv` TSVECTOR generated column
- HNSW and GIN indexes

**Risk**: Low — all columns are NULLABLE with defaults. Existing rows are unaffected.

### Phase 3: Core Schema (access_token_blacklist, soft deletes)

```sql
-- Run: docs/supbase_sql/migrations/002_core_blacklist_and_soft_delete.sql
```

This migration adds:
- `core.access_token_blacklist` table
- `deleted_at` to `core.users`, `core.user_profiles`
- Status transition constraints

**Risk**: Low — additive only.

### Phase 4: Conversation Schema (ENUM types, observability)

```sql
-- Run: docs/supbase_sql/migrations/003_conversation_enums_and_observability.sql
```

This migration adds:
- `conversation.priority_level` ENUM type
- `trace_id`, `metadata`, `deleted_at` to `conversation.messages` and `conversation.unanswered_questions`
- Migrates `priority` from VARCHAR to ENUM (requires type cast)

**Risk**: Medium — the ENUM migration for `priority` requires converting existing VARCHAR data.

### Phase 5: Metadata Schema (ENUM types)

```sql
-- Run: docs/supbase_sql/migrations/004_metadata_enums.sql
```

This migration adds:
- `metadata.rule_target_type` and `metadata.rule_permission` ENUM types
- Migrates `target_type` and `permission` from VARCHAR to ENUM

**Risk**: Medium — ENUM migration requires type cast for existing data.

### Phase 6: Analytics Schema (deleted_at, ENUM types)

```sql
-- Run: docs/supbase_sql/migrations/005_analytics_enums_and_soft_delete.sql
```

This migration adds:
- `analytics.report_status` ENUM type
- `deleted_at` to `analytics.feedbacks`
- Migrates `report_exports.status` from VARCHAR to ENUM

**Risk**: Low for `deleted_at`, medium for ENUM migration.

---

## ENUM Migration Strategy

When converting VARCHAR to ENUM, PostgreSQL requires explicit casting. The pattern is:

```sql
-- 1. Create the ENUM type
CREATE TYPE my_schema.my_enum AS ENUM ('VALUE_A', 'VALUE_B', 'VALUE_C');

-- 2. Add a temporary column with the ENUM type
ALTER TABLE my_schema.my_table ADD COLUMN temp_col my_schema.my_enum;

-- 3. Copy data with explicit cast
UPDATE my_schema.my_table SET temp_col = old_varchar_col::my_schema.my_enum;

-- 4. Drop the old column
ALTER TABLE my_schema.my_table DROP COLUMN old_varchar_col;

-- 5. Rename the temp column
ALTER TABLE my_schema.my_table RENAME COLUMN temp_col TO new_col;
```

**Important**: If any row has a VARCHAR value not in the ENUM set, the cast will FAIL. Clean up data first.

---

## Rollback Strategy

If a migration fails:

1. **Stop immediately** — do not continue to the next phase
2. **Check what changed** — `SELECT * FROM information_schema.columns WHERE table_schema = 'knowledge' ORDER BY table_name, ordinal_position;`
3. **Reverse the specific migration** — drop added columns, recreate old ones if needed
4. **Restore from backup** — if data is corrupted, restore from pre-migration backup

### Pre-Migration Backup

```bash
# Always backup before migrating
docker compose exec postgres pg_dump -U poliwise -d poliwise --schema-only > schema_backup_$(date +%Y%m%d).sql
docker compose exec postgres pg_dump -U poliwise -d poliwise --data-only > data_backup_$(date +%Y%m%d).sql
```

---

## Testing Migration on a Clean Database

```bash
# 1. Start fresh database
docker compose down
docker volume rm poliwise_postgres_data
docker compose up -d postgres

# Wait for health...

# 2. Run init scripts (creates base schema)
# (already done by docker-compose on first boot)

# 3. Run migrations in order
docker compose exec -T postgres psql -U poliwise -d poliwise -f /docker-entrypoint-initdb.d/supbase_sql/migrations/001_knowledge_vector_and_acl.sql
docker compose exec -T postgres psql -U poliwise -d poliwise -f /docker-entrypoint-initdb.d/supbase_sql/migrations/002_core_blacklist_and_soft_delete.sql
# ... etc

# 4. Verify
docker compose exec -T postgres psql -U poliwise -d poliwise -c "\d knowledge.chunks"
```
