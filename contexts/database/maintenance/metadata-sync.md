# Metadata Schema Sync Tasks

**Created At**: 2026-04-10
**Status**: Completed
**Target Schema**: `metadata`

## Overview
This document tracks the discrepancies between the [metadata documentation](../../database/tables/metadata.md) and the actual implementation in the Postgres database, particularly the alignment with the new GitLab Handbook project scope.

## Task 1: Type Alignment and Permissions Restructuring - COMPLETED
The `document_access_rules` table now uses native PostgreSQL ENUM types for `target_type` and `permission`.

### Completed Actions:
- [x] Created `metadata.rule_target_type` ENUM ('ROLE', 'DEPARTMENT', 'USER').
- [x] Created `metadata.rule_permission` ENUM ('VIEW', 'DENY').
- [x] Migrated `target_type` from VARCHAR with CHECK constraint to native ENUM.
- [x] Migrated `permission` from VARCHAR with CHECK constraint to native ENUM.
- [x] The reduction to VIEW/DENY is intentional: the AI system focuses strictly on read-auth mapping. Edit/man mutation permissions are handled at the application layer.

## Task 2: GitLab Structural Adaptation - COMPLETED
With the move to indexing the GitLab Handbook, `metadata.categories` maps to folder directories and `metadata.document_metadata` maps to `.md` files.

### Completed Actions:
- [x] `metadata.categories.parent_id` supports full folder hierarchy reconstruction.
- [x] `metadata.document_metadata` has `metadata JSONB` column for frontmatter variables.
- [x] Added `deleted_at` and `trace_id` columns to `categories` and `tags` for soft deletion and observability.
- [x] Ingestion pipeline task: recursively walk GitLab Handbook files, generate `categories` rows with proper `parent_id` for folder hierarchy.

## Task 3: Observability Columns - COMPLETED

### Completed Actions:
- [x] Added `trace_id VARCHAR(100)` to `document_access_rules`.
- [x] Added `metadata JSONB DEFAULT '{}'` to `document_access_rules`.
- [x] Added `deleted_at TIMESTAMPTZ` to `categories` and `tags`.
- [x] Added indexes on `deleted_at WHERE deleted_at IS NULL` for soft-delete filtering.
