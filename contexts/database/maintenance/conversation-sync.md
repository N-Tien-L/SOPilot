# Conversation Schema Sync Tasks

**Created At**: 2026-04-10
**Status**: Completed
**Target Schema**: `conversation`

## Overview
This document tracks the discrepancies between the [conversation documentation](../../database/tables/conversation.md) and the actual implementation in the Postgres database, aligning with the new GitLab Handbook scope.

## Task 1: Type Alignment - COMPLETED
The `unanswered_questions` table now uses native PostgreSQL ENUM types for priority.

### Completed Actions:
- [x] Created `conversation.priority_level` ENUM type ('LOW', 'NORMAL', 'HIGH', 'CRITICAL').
- [x] Migrated `priority` column from VARCHAR with CHECK constraint to native ENUM.
- [x] Verified that `message_role` and `confidence_level` ENUMs are properly defined and used.

## Task 2: Soft Deletes for Messages - COMPLETED
The `messages` table now supports soft deletes for compliance and auditing.

### Completed Actions:
- [x] Added `deleted_at` column to `conversation.messages`.
- [x] Added `deleted_at` column to `conversation.unanswered_questions`.
- [x] Added partial indexes on `deleted_at WHERE deleted_at IS NULL` for both tables.
- [x] Soft delete cascade behavior: when conversation is soft-deleted, trigger sets `deleted_at` on all messages.

## Task 3: Observability Columns - COMPLETED

### Completed Actions:
- [x] Added `trace_id VARCHAR(100)` to `messages` and `unanswered_questions`.
- [x] Added `metadata JSONB DEFAULT '{}'` to `messages` and `unanswered_questions`.
- [x] Added indexes on `trace_id` for distributed tracing correlation.

## Task 4: Streaming State Management - RESOLVED
The system correctly tracks streaming state with `is_streaming` and `streaming_completed` columns. Recovery jobs should handle crashed streams by setting `is_streaming = false` after a timeout.
