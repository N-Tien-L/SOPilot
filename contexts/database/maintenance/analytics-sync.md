# Analytics Schema Sync Tasks

**Created At**: 2026-04-10
**Status**: Completed
**Target Schema**: `analytics`

## Overview
This document tracks the discrepancies between the [analytics documentation](../../database/tables/analytics.md) and the actual implementation in the Postgres database as of April 10, 2026.

## Task 1: ENUM Type Alignment - COMPLETED
All VARCHAR columns with CHECK constraints have been migrated to native PostgreSQL ENUM types.

### Completed Actions:
- [x] `analytics.feedbacks.type` → uses `analytics.feedback_type` ENUM (already defined).
- [x] `analytics.audit_logs.action` → uses `analytics.audit_action` ENUM (already defined).
- [x] `analytics.audit_logs.resource_type` → uses `analytics.resource_type` ENUM (already defined).
- [x] `analytics.report_exports.report_type` → uses `analytics.report_type` ENUM (already defined).
- [x] `analytics.report_exports.format` → uses `analytics.export_format` ENUM (already defined).
- [x] `analytics.report_exports.status` → uses new `analytics.report_status` ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED').

## Task 2: Report Exports Reconciliation - COMPLETED

### Completed Actions:
- [x] Documentation and DB are now aligned. The DB uses `downloaded_at` and `expires_at` instead of `download_count` and `bucket_name`.
- [x] Recommendation: Use centralized bucket config and `downloaded_at` timestamp. No need for `bucket_name` or `download_count` columns.

## Task 3: Observability and Metadata Fields - COMPLETED

### Completed Actions:
- [x] `analytics.usage_stats` already has `trace_id`, `ip_address`, `user_agent`, `request_size_bytes`, `response_size_bytes`, `is_error`, `error_code`, `error_message`, `chunks_retrieved`, `confidence`.
- [x] `analytics.audit_logs` already has `user_role`, `resource_name`, `changed_fields` (TEXT[]), `trace_id`, `service_name`, `metadata` (JSONB).
- [x] `analytics.daily_aggregates` already has `feedback_ratio`, `p50/p95/p99_response_time_ms`, `total_requests`, `total_errors`, `error_rate`, `total_tokens_used`, `avg_tokens_per_question`, `avg_chunks_retrieved`, `documents_uploaded`, `documents_published`, `unique_active_users`, `new_users`, `unanswered_questions`, `resolved_questions`.
- [x] `analytics.popular_questions` already has `first_asked_at`, `common_source_documents` (JSONB), `detected_category`, `detected_department_id`.
- [x] `analytics.document_popularity` already has `first_cited_at`, `citations_last_7_days`, `citations_last_30_days`.
- [x] `analytics.report_exports` already has `date_from`, `date_to`, `department_id`, `filters` (JSONB), `file_size_bytes`, `downloaded_at`, `expires_at`.

## Task 4: Standardize Timestamps - COMPLETED
- [x] All tables use consistent `created_at` and `updated_at` tracking where appropriate.
- [x] `hourly_aggregates` uses `datetime` as the unique timestamp column with `computed_at` for aggregation time.

## Task 5: Soft Delete for Feedbacks - COMPLETED
- [x] Added `deleted_at` to `analytics.feedbacks` with partial index.
