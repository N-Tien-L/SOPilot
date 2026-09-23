---
title: Analytics Schema Tables
description: Database tables for the analytics schema (feedback-service ownership)
schema: analytics
owner: feedback-service
---

# Analytics Schema Tables

**Owner Service**: `feedback-service`  
**Purpose**: Usage statistics, user feedback, audit logging, and system analytics

---

## Table of Contents

- [analytics.feedbacks](#feedbacks)
- [analytics.usage_stats](#usage-stats)
- [analytics.audit_logs](#audit-logs)
- [analytics.daily_aggregates](#daily-aggregates)
- [analytics.hourly_aggregates](#hourly-aggregates)
- [analytics.department_daily_stats](#department-daily-stats)
- [analytics.popular_questions](#popular-questions)
- [analytics.document_popularity](#document-popularity)
- [analytics.report_exports](#report-exports)

---

## feedbacks

**Description**: User feedback on AI answers (like/dislike with optional comments)

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Feedback unique identifier |
| `user_id` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | User who provided feedback |
| `message_id` | UUID | NOT NULL, FOREIGN KEY → conversation.messages(id) | AI message being rated |
| `conversation_id` | UUID | NOT NULL, FOREIGN KEY → conversation.conversations(id) | Conversation context |
| `type` | ENUM('LIKE','DISLIKE') | NOT NULL | Feedback type |
| `comment` | TEXT | NULLABLE | Optional comment explaining rating |
| `question_text` | TEXT | NOT NULL | Snapshot of user's question (denormalized) |
| `answer_text` | TEXT | NOT NULL | Snapshot of AI's answer (denormalized) |
| `sources_used` | JSONB | NULLABLE | Array of sources cited: `[{document_id, title, page}]` |
| `user_department_id` | UUID | NULLABLE | Track context of feedback |
| `user_role` | VARCHAR(20) | NULLABLE | Track role context |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Feedback timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |
| `deleted_at` | TIMESTAMP | NULLABLE | Soft delete timestamp |

### Indexes

- `idx_feedbacks_user_id` on `user_id`
- `idx_feedbacks_message_id` on `message_id` (unique to prevent duplicate feedback per message)
- `idx_feedbacks_type` on `type`
- `idx_feedbacks_created_at` on `created_at` DESC
- Composite: `idx_feedbacks_user_message` on `(user_id, message_id)` unique (one feedback per user per message)

### Notes

- **Denormalization**: Store `question_text` and `answer_text` at feedback time so historical record persists even if message is edited/deleted.
- **One Feedback Per Message**: Enforce that a user can only provide feedback once per AI message (unique constraint on `(user_id, message_id)`).
- **Source Tracking**: `sources_used` array preserves which documents were cited at time of feedback (may differ if sources are updated later).
- **Analytics Use**: Calculate satisfaction rate:
  ```sql
  SELECT 
    COUNT(*) FILTER (WHERE type = 'LIKE') * 100.0 / COUNT(*) as satisfaction_rate
  FROM analytics.feedbacks
  WHERE created_at >= NOW() - INTERVAL '30 days';
  ```

---

## usage_stats

**Description**: High-volume API usage logging. Every API request that passes through the gateway is logged here.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Log entry ID |
| `user_id` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | User (NULL for unauthenticated) |
| `service_name` | VARCHAR(100) | NOT NULL | Service that handled request (e.g., "ai-qa-service") |
| `endpoint` | VARCHAR(200) | NOT NULL | API endpoint path (e.g., "/api/v1/ai/chat") |
| `method` | VARCHAR(10) | NOT NULL | HTTP method (GET, POST, etc.) |
| `response_time_ms` | INT | NOT NULL | End-to-end response time |
| `status_code` | INT | NOT NULL | HTTP status code (200, 401, 500, etc.) |
| `request_size_bytes` | INT | NULLABLE | Size of request payload |
| `response_size_bytes` | INT | NULLABLE | Size of response payload |
| `is_error` | BOOLEAN | DEFAULT false | Flag for failed requests |
| `error_code` | VARCHAR(50) | NULLABLE | Specific error code if failed |
| `error_message` | TEXT | NULLABLE | Error description |
| `tokens_used` | INT | NULLABLE | Tokens consumed (if LLM call) |
| `model_used` | VARCHAR(100) | NULLABLE | LLM model name (if applicable) |
| `chunks_retrieved` | INT | NULLABLE | Number of chunks used in context |
| `confidence` | VARCHAR(20) | NULLABLE | Overall confidence score |
| `trace_id` | VARCHAR(100) | NULLABLE | Trace ID for telemetry |
| `ip_address` | INET | NULLABLE | Request IP address |
| `user_agent` | TEXT | NULLABLE | Browser/client string |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Request timestamp |

### Indexes

- `idx_usage_stats_user_id` on `user_id`
- `idx_usage_stats_created_at` on `created_at` DESC
- `idx_usage_stats_service_endpoint` on `service_name, endpoint`
- `idx_usage_stats_status_code` on `status_code`
- Partition by month on `created_at` (recommended for high volume)

### Notes

- **High Volume**: This table grows quickly. Implement partitioning:
  ```sql
  CREATE TABLE analytics.usage_stats_2024_01 PARTITION OF analytics.usage_stats
  FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
  ```
- **Data Retention**: Keep detailed logs for 90 days, then aggregate into `daily_aggregates` and delete raw records.
- **Aggregation Job**: Daily cron:
  1. Summarize yesterday's usage into `daily_aggregates`
  2. Delete raw rows older than 90 days
- **Cost Tracking**: Use `tokens_used` to calculate LLM costs (multiply by per-token price).
- **Performance Monitoring**: Alert on:
  - P99 response time > 5000ms
  - Error rate (status >= 400) > 5%
  - Token usage spike (> 2x average)

---

## audit_logs

**Description**: Immutable audit trail of all admin actions and sensitive operations for compliance

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Audit entry ID |
| `user_id` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Actor (who performed action) |
| `username` | VARCHAR(100) | NOT NULL | Username at time of action (denormalized in case user deleted) |
| `user_role` | VARCHAR(20) | NULLABLE | Role at time of action |
| `action` | ENUM(`analytics.audit_action`) | NOT NULL | What action was taken |
| `resource_type` | ENUM(`analytics.resource_type`) | NOT NULL | Type of resource affected |
| `resource_id` | UUID | NULLABLE | ID of affected resource |
| `resource_name` | VARCHAR(255) | NULLABLE | Name of the affected resource |
| `old_value` | JSONB | NULLABLE | Previous state (for updates) |
| `new_value` | JSONB | NULLABLE | New state (for creates/updates) |
| `changed_fields` | TEXT[] | NULLABLE | Array of field names modified |
| `ip_address` | INET | NULLABLE | Actor's IP address |
| `user_agent` | TEXT | NULLABLE | Actor's user agent |
| `trace_id` | VARCHAR(100) | NULLABLE | Telemetry correlation ID |
| `service_name` | VARCHAR(50) | NULLABLE | Service where action originated |
| `metadata` | JSONB | DEFAULT '{}' | Additional context |
| `created_at` | TIMESTAMP | DEFAULT NOW() | When action occurred |

### Indexes

- `idx_audit_logs_user_id` on `user_id`
- `idx_audit_logs_action` on `action`
- `idx_audit_logs_resource` on `resource_type, resource_id`
- `idx_audit_logs_created_at` on `created_at` DESC

### Notes

- **Immutable**: Never UPDATE or DELETE audit logs. Append-only for compliance (GDPR, ISO 27001).
- **Retention**: Keep for 7 years (legal requirement for enterprise systems).
- **Partitioning**: Partition by year to manage size.
- **Triggers**: Use database triggers or application events to auto-populate this table on sensitive actions:
  ```sql
  -- Example trigger on user update
  CREATE OR REPLACE FUNCTION log_user_audit()
  RETURNS TRIGGER AS $$
  BEGIN
    INSERT INTO analytics.audit_logs (
      user_id, username, action, resource_type, resource_id,
      old_value, new_value, ip_address
    ) VALUES (
      NEW.updated_by,
      (SELECT username FROM core.users WHERE id = NEW.updated_by),
      'USER_UPDATED',
      'USER',
      NEW.id,
      row_to_json(OLD),
      row_to_json(NEW),
      current_setting('myapp.client_ip', true)  -- Pass via connection parameter
    );
    RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;
  ```

---

## daily_aggregates

**Description**: Pre-aggregated usage statistics by day for dashboard queries

**Primary Key**: `id` (UUID)  
**Unique Constraint**: `(date)` - one row per day

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Aggregate record ID |
| `date` | DATE | UNIQUE, NOT NULL | Date of aggregation (UTC) |
| `total_questions` | INT | DEFAULT 0 | Total AI questions asked |
| `total_conversations` | INT | DEFAULT 0 | Total conversations started |
| `unique_users_asked` | INT | DEFAULT 0 | Distinct users who asked questions |
| `total_likes` | INT | DEFAULT 0 | Total likes received |
| `total_dislikes` | INT | DEFAULT 0 | Total dislikes received |
| `feedback_ratio` | DECIMAL(5,4) | NULLABLE | Like/dislike ratio |
| `avg_response_time_ms` | INT | NULLABLE | Average AI response time |
| `p50_response_time_ms` | INT | NULLABLE | P50 response time |
| `p95_response_time_ms` | INT | NULLABLE | P95 response time |
| `p99_response_time_ms` | INT | NULLABLE | P99 response time |
| `total_requests` | INT | DEFAULT 0 | Total API requests |
| `total_errors` | INT | DEFAULT 0 | Total error responses |
| `error_rate` | DECIMAL(5,4) | NULLABLE | Error percentage |
| `total_tokens_used` | BIGINT | DEFAULT 0 | Total LLM tokens consumed |
| `avg_tokens_per_question` | INT | NULLABLE | Average tokens per question |
| `avg_chunks_retrieved` | DECIMAL(5,2) | NULLABLE | Average chunks per query |
| `documents_uploaded` | INT | DEFAULT 0 | Documents uploaded this day |
| `documents_published` | INT | DEFAULT 0 | Documents published this day |
| `unique_active_users` | INT | DEFAULT 0 | Distinct active users |
| `new_users` | INT | DEFAULT 0 | New users created |
| `unanswered_questions` | INT | DEFAULT 0 | Unanswered questions count |
| `resolved_questions` | INT | DEFAULT 0 | Resolved questions count |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Aggregation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Notes

- **Population**: Daily cron job at 02:00 UTC aggregates previous day's `usage_stats` and `feedbacks`.
- **Query Pattern**: All dashboard queries should hit this table (not raw `usage_stats`) for performance.
- **Rollup**: Monthly aggregates can be derived from daily (no separate monthly table needed).

---

## hourly_aggregates

**Description**: Hourly aggregates for near-real-time monitoring

**Primary Key**: `id` (UUID)  
**Unique Constraint**: `(datetime)` - one row per hour

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Aggregate ID |
| `datetime` | TIMESTAMP | UNIQUE, NOT NULL | Hour timestamp (e.g., "2024-01-15 14:00:00") |
| `total_questions` | INT | DEFAULT 0 | Questions in this hour |
| `total_requests` | INT | DEFAULT 0 | All API requests |
| `total_errors` | INT | DEFAULT 0 | Error responses (4xx + 5xx) |
| `unique_users` | INT | DEFAULT 0 | Active unique users |
| `avg_response_time_ms` | INT | NULLABLE | Average response time |
| `likes` | INT | DEFAULT 0 | Likes in this hour |
| `dislikes` | INT | DEFAULT 0 | Dislikes in this hour |
| `computed_at` | TIMESTAMP | DEFAULT NOW() | Aggregation timestamp |

### Notes

- **Retention**: Keep 90 days of hourly data, then delete (daily aggregates retained longer).
- **Use Case**: Operational dashboards, alerting on volume drops or error spikes.

---

## department_daily_stats

**Description**: Department-level daily statistics for manager analytics

**Primary Key**: `id` (UUID)  
**Unique Constraint**: `(date, department_id)`

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Stat ID |
| `date` | DATE | NOT NULL | Date (UTC) |
| `department_id` | UUID | NOT NULL, FOREIGN KEY → core.departments(id) | Department |
| `total_questions` | INT | DEFAULT 0 | Questions by department users |
| `unique_users` | INT | DEFAULT 0 | Active department users |
| `likes` | INT | DEFAULT 0 | Likes by department users |
| `dislikes` | INT | DEFAULT 0 | Dislikes by department users |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Aggregation timestamp |

### Composite Unique

```sql
ALTER TABLE analytics.department_daily_stats
ADD CONSTRAINT uniq_dept_date UNIQUE (date, department_id);
```

### Notes

- **Join for Department Names**: When querying, join with `core.departments` to get department name:
  ```sql
  SELECT d.name, stats.*
  FROM analytics.department_daily_stats stats
  JOIN core.departments d ON d.id = stats.department_id
  WHERE stats.date = CURRENT_DATE - 1;
  ```

---

## popular_questions

**Description**: Aggregated popular questions for knowledge gap insights

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Record ID |
| `question_normalized` | TEXT | NOT NULL | Normalized question (lowercase, no diacritics) |
| `question_sample` | TEXT | NOT NULL | Representative question text (most frequent variant) |
| `ask_count` | INT | DEFAULT 1 | How many times asked (across all users) |
| `unique_users_count` | INT | DEFAULT 1 | Distinct users who asked |
| `first_asked_at` | TIMESTAMP | NOT NULL | First time this question was asked |
| `last_asked_at` | TIMESTAMP | NOT NULL | Most recent ask timestamp |
| `total_likes` | INT | DEFAULT 0 | Total likes on AI answers |
| `total_dislikes` | INT | DEFAULT 0 | Total dislikes on AI answers |
| `common_source_documents` | JSONB | DEFAULT '[]' | Frequently cited docs for this question |
| `detected_category` | VARCHAR(100) | NULLABLE | Auto-detected category |
| `detected_department_id` | UUID | NULLABLE | Auto-detected department |
| `created_at` | TIMESTAMP | DEFAULT NOW() | First seen in aggregation |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Indexes

- `idx_popular_questions_ask_count` on `ask_count` DESC
- `idx_popular_questions_last_asked` on `last_asked_at` DESC
- Unique on `question_normalized` for upsert

### Notes

- **Population**: Daily batch job scans `conversation.messages` (USER role) and aggregates:
  ```sql
  INSERT INTO analytics.popular_questions
  SELECT
    normalize(question) as question_norm,
    mode() WITHIN GROUP (ORDER BY question) as sample_question,
    COUNT(*) as ask_count,
    COUNT(DISTINCT user_id) as unique_count,
    ...
  FROM conversation.messages
  WHERE role = 'USER' AND created_at >= yesterday()
  GROUP BY normalize(question)
  ON CONFLICT (question_normalized) DO UPDATE SET
    ask_count = popular_questions.ask_count + EXCLUDED.ask_count,
    unique_users_count = popular_questions.unique_users_count + EXCLUDED.unique_users_count;
  ```
- **Use**: Show "Popular Questions" section in dashboard, identify trending topics.

---

## document_popularity

**Description**: Tracks which documents are most frequently cited in AI answers

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Record ID |
| `document_id` | UUID | NOT NULL, FOREIGN KEY → knowledge.documents(id) | Document |
| `total_citations` | INT | DEFAULT 0 | Times referenced in AI answers |
| `unique_questions_cited` | INT | DEFAULT 0 | Distinct questions that cited this doc |
| `citations_with_likes` | INT | DEFAULT 0 | Citations where user liked the answer |
| `citations_with_dislikes` | INT | DEFAULT 0 | Citations where user disliked |
| `first_cited_at` | TIMESTAMP | NULLABLE | First time this doc was cited |
| `last_cited_at` | TIMESTAMP | DEFAULT NOW() | Most recent citation |
| `citations_last_7_days` | INT | DEFAULT 0 | Citations in last 7 days |
| `citations_last_30_days` | INT | DEFAULT 0 | Citations in last 30 days |
| `created_at` | TIMESTAMP | DEFAULT NOW() | First citation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Indexes

- `idx_document_popularity_document_id` on `document_id`
- `idx_document_popularity_citations` on `total_citations` DESC

### Notes

- **Update Trigger**: When a message with `sources` is saved to `conversation.messages`, increment counters for each cited `document_id`.
- **Use**: Knowledge managers can see which documents are most valuable (or outdated if low citations).

---

## report_exports

**Description**: Tracks admin report export requests and their status

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Export request ID |
| `report_type` | ENUM(`analytics.report_type`) | NOT NULL | Type of report |
| `title` | VARCHAR(255) | NOT NULL | User-provided export title |
| `date_from` | DATE | NULLABLE | Report start date filter |
| `date_to` | DATE | NULLABLE | Report end date filter |
| `department_id` | UUID | NULLABLE | Department filter |
| `filters` | JSONB | DEFAULT '{}' | Additional query filters |
| `format` | ENUM(`analytics.export_format`) | NOT NULL | Export format |
| `file_key` | VARCHAR(500) | NULLABLE | MinIO key where file stored |
| `file_size_bytes` | INT | NULLABLE | Size of generated file |
| `status` | ENUM(`analytics.report_status`) | DEFAULT 'PENDING' | Export status |
| `error_message` | TEXT | NULLABLE | Error if failed |
| `requested_by` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Who requested |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Request timestamp |
| `completed_at` | TIMESTAMP | NULLABLE | When export finished |
| `downloaded_at` | TIMESTAMP | NULLABLE | When file was downloaded |
| `expires_at` | TIMESTAMP | NULLABLE | When export file expires |

### Notes

- **Async Generation**: Large reports processed by background worker (not real-time).
- **Expiration**: Delete export files after 30 days.

---

## Enums

### feedback_type

```sql
CREATE TYPE analytics.feedback_type AS ENUM ('LIKE', 'DISLIKE');
```

### audit_action

```sql
CREATE TYPE analytics.audit_action AS ENUM (
  'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'TOKEN_REFRESH', 'PASSWORD_CHANGE',
  'USER_CREATE', 'USER_UPDATE', 'USER_DEACTIVATE', 'USER_ACTIVATE', 'USER_REVOKE', 'USER_DELETE',
  'DOCUMENT_UPLOAD', 'DOCUMENT_UPDATE', 'DOCUMENT_DELETE', 'DOCUMENT_PUBLISH', 'DOCUMENT_ARCHIVE', 'DOCUMENT_VERSION_CREATE',
  'QUESTION_ASK', 'CONVERSATION_CREATE', 'CONVERSATION_DELETE',
  'FEEDBACK_SUBMIT',
  'SETTINGS_UPDATE', 'BULK_IMPORT', 'REPORT_EXPORT'
);
```

### resource_type

```sql
CREATE TYPE analytics.resource_type AS ENUM (
  'USER', 'DOCUMENT', 'CONVERSATION', 'MESSAGE', 'FEEDBACK',
  'DEPARTMENT', 'CATEGORY', 'TAG', 'SETTINGS'
);
```

### export_format

```sql
CREATE TYPE analytics.export_format AS ENUM ('CSV', 'PDF', 'XLSX', 'JSON');
```

### report_type

```sql
CREATE TYPE analytics.report_type AS ENUM (
  'USER_REPORT', 'DEPARTMENT_REPORT', 'USAGE_SUMMARY', 'QUESTION_ANALYTICS',
  'FEEDBACK_ANALYSIS', 'USER_ENGAGEMENT', 'DOCUMENT_POPULARITY',
  'UNANSWERED_QUESTIONS', 'DEPARTMENT_BREAKDOWN'
);
```

### report_status

```sql
CREATE TYPE analytics.report_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
```

---

## Partitioning Strategy (For High-Volume Tables)

### usage_stats (by month)

```sql
-- Create partitions automatically via setup script
CREATE TABLE analytics.usage_stats_2024_01 PARTITION OF analytics.usage_stats
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE analytics.usage_stats_2024_02 PARTITION OF analytics.usage_stats
FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... etc
```

### audit_logs (by year)

```sql
CREATE TABLE analytics.audit_logs_2024 PARTITION OF analytics.audit_logs
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

---

## Data Retention Policies

| Table | Retention | Action |
|-------|-----------|--------|
| `usage_stats` | 90 days raw, then aggregate & delete | Delete WHERE `created_at < NOW() - INTERVAL '90 days'` |
| `audit_logs` | 7 years | Partition by year, drop oldest partition annually |
| `unanswered_questions` | Keep resolved for 2 years | Delete WHERE `resolved = true AND resolved_at < NOW() - INTERVAL '2 years'` |
| `report_exports` | 30 days file storage | Delete files from MinIO + DB rows |

Schedule via cron or pg_cron extension.

---

## Related References

- **AI Architecture**: `contexts/architecture/ai-service-architecture.md` - feedback component
- **Service Ownership**: `contexts/service-boundaries/responsibilities.md` - feedback-service responsibilities
- **API Contracts**: `contexts/service-boundaries/api-contracts.md` - analytics endpoints
- **Event Contracts**: `contexts/service-boundaries/events.md` - `unanswered.question` event

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
