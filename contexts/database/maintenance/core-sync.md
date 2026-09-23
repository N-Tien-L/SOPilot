# Core Schema Sync Tasks

**Created At**: 2026-04-10
**Status**: Completed
**Target Schema**: `core`

## Overview
This document tracks the discrepancies between the [core documentation](../../database/tables/core.md) and the actual implementation in the Postgres database, aligning with the new GitLab Handbook scope.

## Task 1: Type Alignment - COMPLETED
The ENUM types (`user_role`, `account_status`, `login_status`) are properly defined and used in the SQL schema.

### Completed Actions:
- [x] Verified that `core.users.role` uses `core.user_role` ENUM ('USER', 'MANAGER', 'ADMIN').
- [x] Verified that `core.users.status` uses `core.account_status` ENUM ('ACTIVE', 'DEACTIVATED', 'REVOKED').
- [x] Verified that `core.login_history.status` uses `core.login_status` ENUM.
- [x] Added status transition constraints: `chk_status_revoked` and `chk_status_deactivated`.

## Task 2: Soft Deletes and Data Cleanup - COMPLETED

### Completed Actions:
- [x] Added `deleted_at TIMESTAMPTZ` to `core.users` and `core.user_profiles`.
- [x] Added partial index `idx_core_users_deleted_at` on `deleted_at WHERE deleted_at IS NULL`.
- [x] Cron job task: permanently delete revoked or soft-deleted users after retention period (e.g., 1 year).

## Task 3: Token Blacklist Strategy - COMPLETED

### Completed Actions:
- [x] Created `core.access_token_blacklist` table with `jti` (VARCHAR) as primary key.
- [x] Added indexes on `expired_at` (for cleanup) and `user_id` (for user-specific lookups).
- [x] Auth-service MUST have a scheduled job to clear expired tokens: `DELETE FROM core.access_token_blacklist WHERE expired_at < NOW()`.
