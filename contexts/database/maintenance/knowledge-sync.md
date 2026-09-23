# Knowledge Schema Sync Tasks

**Created At**: 2026-04-10
**Status**: Completed
**Target Schema**: `knowledge`

## Overview
This document tracks the discrepancies between the [knowledge documentation](../../database/tables/knowledge.md) and the actual implementation in the Postgres database, specifically concerning the pivot to the GitLab Handbook dataset.

## Task 1: Re-instating pgvector Setup (Critical Blocker) - COMPLETED
The system relies on the `pgvector` extension. All blockers have been resolved.

### Completed Actions:
- [x] **Docker Image**: Updated `docker-compose.yml` to use `pgvector/pgvector:pg16` instead of `postgres:16-alpine`.
- [x] **SQL Initialization**: Updated `docs/supbase_sql/knowledge_management.sql` to include `CREATE EXTENSION IF NOT EXISTS vector;`.
- [x] **Table Schema**: Added `embedding_vector vector(1024)` column to both `knowledge.chunks` and `knowledge.embedding_cache` tables.
- [x] **HNSW Index**: Added `CREATE INDEX ... USING hnsw (embedding_vector vector_cosine_ops)` for fast vector similarity search.

## Task 2: GitLab Structural Field Migrations - COMPLETED
The hierarchical nature of the GitLab Handbook is now fully supported with dedicated columns.

### Completed Actions:
- [x] Added dedicated columns to `knowledge.chunks`: `section_title`, `section_level`, `section_path` (TEXT[]).
- [x] Added `parent_chunk_id` for parent-child chunk relationships.
- [x] Added GIN index on `section_path` for fast hierarchical path queries.
- [x] Added `chunk_type` ENUM ('parent', 'child') for chunk classification.

## Task 3: Access Control Flatting Shift - COMPLETED
The read-optimized ACL flattening is now fully implemented.

### Completed Actions:
- [x] Added `allowed_roles core.user_role[]`, `allowed_departments UUID[]`, `allowed_users UUID[]`, and `access_level VARCHAR(20)` columns to `knowledge.chunks`.
- [x] Added GIN indexes on all ACL array columns for fast filtering.
- [x] Authorization filtering now happens directly in Postgres via pgvector + GIN index queries.

## Task 4: File Metadata Normalization - COMPLETED
File-specific metadata is now properly stored in `document_versions`.

### Completed Actions:
- [x] Added `is_current` BOOLEAN to `document_versions` with unique partial index ensuring only one current version per document.
- [x] Added `document_version_id` FK to `chunks` table for proper version tracking.
- [x] Added `is_latest` BOOLEAN to `chunks` for soft versioning.
- [x] Added `deleted_at` to `chunks` for soft deletion support.
