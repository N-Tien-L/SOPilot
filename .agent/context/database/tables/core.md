---
title: Core Schema Tables
description: Database tables for the core schema (auth-service ownership)
schema: core
owner: auth-service
---

# Core Schema Tables

## V2 (`services/core-api`, `infrastructure/db/migrations/core/`)

core-api is the only owner/writer of V2 `core` (TECH-V2-core-api §3). Added by `V003` (V2-11):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.users` | no (global) | `id` uuid PK (UUIDv7 from app), `email` lower-case, not unique; `display_name`, `avatar_url`, `last_active_workspace_id` (no FK) |
| `core.external_identities` | no (global) | `user_id` FK, `issuer`, `subject`, `email_at_link`, `hosted_domain`; `UNIQUE (issuer, subject)`, `UNIQUE (user_id, issuer)` |
| `core.workspaces` | FORCE | `name` 1–100, `kind` `PERSONAL`/`TEAM`, `created_by` FK; `uq_personal_workspace` = one PERSONAL per user |
| `core.memberships` | FORCE | PK `(workspace_id, user_id)`, `role` `OWNER`/`ADMIN`/`MEMBER`, `status` `ACTIVE`/`SUSPENDED` (+ `suspended_at` check), `display_name`, `email`, `department_id` (FK to departments arrives with V2-23) |

Added by `V004` (V2-23) and `V005` (V2-12):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.departments` | FORCE | `name` 1-100, `status` `ACTIVE`/`ARCHIVED`; `UNIQUE (workspace_id, lower(name))`; `UNIQUE (workspace_id, id)` is the FK target |
| `core.memberships` (extended) | FORCE | + `employee_code` (unique per workspace when set), `job_title`; FK `(workspace_id, department_id)` -> departments `RESTRICT` |
| `core.invitations` | FORCE | `email`, `role` `ADMIN`/`MEMBER`, profile fields, `token_hash` unique, `expires_at`, `accepted_at`/`revoked_at`; one pending per `(workspace_id, email)`; department FK `SET NULL`; logic is V2-30 |
| `core.categories` | FORCE | `name`, `status`; `UNIQUE (workspace_id, lower(name))`; API is V2-24 |
| `core.documents` | FORCE | `title`/`description`/`language` each with `*_source` (`SYSTEM`/`SUGGESTED`/`USER`), `visibility` `WORKSPACE`/`DEPARTMENTS`, `access_revision`, `current_version_id` (READY, serves Q&A), `latest_version_id`, `deleted_at` (soft delete until ai-service confirms) |
| `core.document_versions` | FORCE | `version_no`, `status` `UPLOADED`/`PROCESSING`/`READY`/`FAILED`/`SUPERSEDED`, `failure_code`/`failure_message` (fixed sentence per code), `file_type` `PDF`/`MD`, `size_bytes` <= 20 MB, `sha256`, `object_key` unique, extraction metadata, `warning_codes`, `attempt` |
| `core.document_departments` | FORCE | `(document_id, department_id)`; department FK `RESTRICT`; written by V2-24 |
| `core.outbox_events` | FORCE | `id` = Idempotency-Key, `event_type` `INGEST_REQUESTED`/`ACCESS_UPDATED`/`DOCUMENT_DELETED`, `status` `PENDING`/`DELIVERED`/`DEAD`, `attempts`, `next_attempt_at` |
| `core.audit_logs` | FORCE | append-only for the app role; `action`, `target_*`, `details` jsonb, `trace_id` |

Added by `V006` (V2-29):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.refresh_tokens` | no (global, TECH §3.1) | `user_id` FK, `target_workspace_id` (no FK; not named `workspace_id` so the isolation suite lists the table as global), `family_id`, `token_hash` bytea unique (SHA-256), `expires_at`, `used_at`, `revoked_at`, `revoked_reason` (`LOGOUT`/`REUSE_DETECTED`/`MEMBERSHIP_LOST`/`SUSPENDED`/`EXPIRED_FAMILY`); indexes on `family_id` and `(user_id, target_workspace_id)` |
| `core.workspaces` (extended) | FORCE | + `deleted_at` (soft delete; hidden from `findVisible`, `findMembership` and the workspace list) |

Added by `V007` (V2-24):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.tags` | FORCE | `name` 1–50 chars (case kept as typed); unique on `(workspace_id, lower(name))`; `UNIQUE (workspace_id, id)` for the composite FK |
| `core.document_tags` | FORCE | PK `(document_id, tag_id)`; composite FKs `(workspace_id, document_id)` → `documents` and `(workspace_id, tag_id)` → `tags`, both `ON DELETE CASCADE`; index `ix_document_tags_tag (workspace_id, tag_id)` |

Functions: `core.claim_outbox_batch(int)` leases due events of every workspace for 60 s (`FOR UPDATE SKIP LOCKED`);
`core.referenced_object_keys(text[])` tells the storage janitor which object keys a version still references.

Function `core.create_personal_workspace(p_user_id, p_workspace_id, p_name, p_email)` returns the
user's PERSONAL workspace id, creating it and the OWNER membership if absent. Later tables
(refresh tokens, departments, invitations, documents, outbox, audit) follow TECH §3 in new migrations.

## V1 (frozen, `infrastructure/init-db/`)

**Owner Service**: `auth-service`  
**Purpose**: User authentication, roles, permissions, and login history

---

## Table of Contents

- [core.departments](#departments)
- [core.users](#users)
- [core.user_profiles](#user-profiles)
- [core.refresh_tokens](#refresh-tokens)
- [core.login_history](#login-history)
- [core.access_token_blacklist](#access-token-blacklist)

---

## departments

**Description**: Company department hierarchy

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Department unique identifier |
| `name` | VARCHAR(255) | NOT NULL | Department name |
| `code` | VARCHAR(50) | UNIQUE, NOT NULL | Department code (e.g., "HR", "IT") |
| `description` | TEXT | NULLABLE | Department description |
| `parent_id` | UUID | NULLABLE, FOREIGN KEY → core.departments(id) | Parent department for hierarchy |
| `is_active` | BOOLEAN | DEFAULT true | Whether department is active |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Indexes

- `idx_departments_parent_id` on `parent_id`
- `idx_departments_is_active` on `is_active`

### Notes

- Hierarchical structure allows multi-level department nesting
- `parent_id` NULL for root departments
- Soft deletion: Not used (departments are never deleted, only deactivated via `is_active`)
- **Tree Traversal**: Use PostgreSQL `WITH RECURSIVE` CTEs for querying sub-departments up/down the hierarchy.
- **Circular Reference Prevention**: Application logic must strictly prevent cyclical relationships (e.g., A -> B -> A) when creating or updating departments.
- **GitLab Handbook Alignment**: This table maps extremely well to GitLab's organizational structure (e.g., Engineering -> Development -> Create). Use `parent_id` to mirror these handbook sections.

---

## users

**Description**: User accounts with authentication and authorization data

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | User unique identifier |
| `username` | VARCHAR(100) | UNIQUE, NOT NULL | Login username |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email address |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt-hashed password |
| `role` | ENUM('USER','MANAGER','ADMIN') | DEFAULT 'USER' | RBAC role |
| `status` | ENUM('ACTIVE','DEACTIVATED','REVOKED') | DEFAULT 'ACTIVE' | Account status |
| `department_id` | UUID | FOREIGN KEY → core.departments(id) | Primary department |
| `failed_login_attempts` | INT | DEFAULT 0 | Count of consecutive failed logins |
| `locked_until` | TIMESTAMP | NULLABLE | Account lock expiry time |
| `password_changed_at` | TIMESTAMP | NULLABLE | Last password change timestamp |
| `must_change_password` | BOOLEAN | DEFAULT false | Force password change on next login |
| `created_by` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | Who created this user (NULL for root admin) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |
| `deactivated_at` | TIMESTAMP | NULLABLE | When account was deactivated |
| `revoked_at` | TIMESTAMP | NULLABLE | When account was revoked |
| `deleted_at` | TIMESTAMP | NULLABLE | Soft delete timestamp |

### Indexes

- `idx_users_username` on `username`
- `idx_users_email` on `email`
- `idx_users_status` on `status`
- `idx_users_department_id` on `department_id`

### Important Constraints

- `CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')`
- `CHECK (username ~* '^[a-z0-9_]{3,50}$')`
- `CHECK (status != 'REVOKED' OR revoked_at IS NOT NULL)`
- `CHECK (status != 'DEACTIVATED' OR deactivated_at IS NOT NULL)`

### Notes

- **Password Policy**: Must meet complexity requirements before being hashed with Bcrypt (cost factor 12)
- **Force Password Change**: If `must_change_password` is true, the API Gateway/Auth Guards MUST block all requests except the change password endpoint, even if the JWT is otherwise valid.
- **Account Lockout**: After 5 failed login attempts, `locked_until` is set to 15 minutes
- **Role/Department Changes**: When a user's `role` or `department_id` is updated, the system MUST revoke all their active `refresh_tokens` to force a re-login and issue a new JWT with updated claims.
- **Status Transitions**:
  - `ACTIVE` → `DEACTIVATED`: Manual admin action, `deactivated_at` set
  - `ACTIVE`/`DEACTIVATED` → `REVOKED`: Security incident, `revoked_at` set
  - Once `REVOKED`, cannot transition back
- **Event Publishing**: When `status` changes, publish `user.status.changed` event to RabbitMQ

---

## user_profiles

**Description**: Detailed user personal and employment information

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Profile record ID |
| `user_id` | UUID | UNIQUE, NOT NULL, FOREIGN KEY → core.users(id) | Linked user |
| `full_name` | VARCHAR(255) | NOT NULL | Full name |
| `phone` | VARCHAR(20) | NULLABLE | Phone number |
| `position` | VARCHAR(255) | NULLABLE | Job position/title |
| `avatar_url` | VARCHAR(500) | NULLABLE | Profile picture URL |
| `bio` | TEXT | NULLABLE | Personal bio |
| `date_of_birth` | DATE | NULLABLE | Date of birth |
| `employee_code` | VARCHAR(50) | NULLABLE | Employee ID number |
| `joined_date` | DATE | NULLABLE | Date joined company |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Notes

- **One-to-one** relationship with `core.users`
- PII data: Handle with care, encrypt if required by compliance
- `employee_code` is searchable (used for HR lookups)
- On user deletion (hard or soft), cascade delete or anonymize PII per GDPR

---

## refresh_tokens

**Description**: JWT refresh token tracking for secure token rotation

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Token ID |
| `user_id` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Token owner |
| `token_hash` | VARCHAR(255) | NOT NULL | Hash of refresh token (bcrypt) |
| `device_info` | VARCHAR(255) | NULLABLE | Device info (e.g., "Chrome on Windows") |
| `ip_address` | INET | NULLABLE | IP address used for token issuance |
| `user_agent` | TEXT | NULLABLE | Full user agent string |
| `expires_at` | TIMESTAMP | NOT NULL | Token expiry timestamp |
| `revoked` | BOOLEAN | DEFAULT false | Whether token is revoked |
| `revoked_at` | TIMESTAMP | NULLABLE | When token was revoked |
| `revoked_reason` | VARCHAR(255) | NULLABLE | Reason for revocation |
| `replaced_by` | UUID | NULLABLE, FOREIGN KEY → core.refresh_tokens(id) | New token that replaced this one |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### Indexes

- `idx_refresh_tokens_user_id` on `user_id`
- `idx_refresh_tokens_token_hash` on `token_hash` (for quick lookup)
- `idx_refresh_tokens_expires_at` on `expires_at` (for cleanup)

### Notes

- **Token Rotation**: When user uses refresh token:
  1. Mark old token as `revoked = true`, set `replaced_by` to new token ID
  2. Issue new refresh token with longer expiry
  3. Old token cannot be used again
- **Compromise Detection**: If `user_agent` or `ip_address` changes between uses, flag for security review
- **Cleanup Job**: Daily cron to delete expired tokens (where `expires_at < NOW()` and `revoked = true`)

---

## login_history

**Description**: Audit log of all login attempts (successful and failed)

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Log entry ID |
| `user_id` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | User (NULL for non-existent user attempts) |
| `username` | VARCHAR(100) | NOT NULL | Username attempted |
| `ip_address` | INET | NOT NULL | Source IP address |
| `user_agent` | TEXT | NULLABLE | Client user agent |
| `device_type` | VARCHAR(50) | NULLABLE | Detected device type (mobile, desktop, tablet) |
| `location` | VARCHAR(255) | NULLABLE | Geo location (city, country) from IP |
| `status` | ENUM('SUCCESS','FAILED') | NOT NULL | Login outcome |
| `failure_reason` | TEXT | NULLABLE | If FAILED, reason (e.g., "invalid_password", "account_locked") |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Timestamp of attempt |

### Indexes

- `idx_login_history_user_id` on `user_id`
- `idx_login_history_created_at` on `created_at` DESC
- `idx_login_history_ip_address` on `ip_address`

### Notes

- **Retention**: Keep for 90 days (security audit requirement), then archive/delete
- **Geo IP**: Use MaxMind GeoIP2 or similar to populate `location` on write
- **Device Detection**: Parse user agent to populate `device_type` (use ua-parser library)
- **Failed Login Aggregation**: Update `core.users.failed_login_attempts` on each FAILED attempt (before account lock)
- **Security Monitoring**: Alert on:
  - > 10 failed attempts from single IP in 1 hour
  - Login from unusual geographic location (different country than usual)
  - Multiple concurrent sessions from different locations

---

## Enum Types

### user_role

```sql
CREATE TYPE user_role AS ENUM ('USER', 'MANAGER', 'ADMIN');
```

### account_status

```sql
CREATE TYPE account_status AS ENUM ('ACTIVE', 'DEACTIVATED', 'REVOKED');
```

### login_status (not used in table, defined for completeness)

```sql
CREATE TYPE login_status AS ENUM ('SUCCESS', 'FAILED');
```

---

## Related References

- **Authorization Strategy**: `.agent/context/authorization/dual-strategy.md` - how these tables integrate with ACL
- **Service Ownership**: `.agent/context/service-boundaries/responsibilities.md` - auth-service responsibilities
- **Event Contracts**: `.agent/context/service-boundaries/events.md` - `user.status.changed` event

---

## access_token_blacklist

**Description**: Securely revokes individual JWT access tokens upon explicit logout or token compromise

**Primary Key**: `jti` (VARCHAR)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `jti` | VARCHAR(255) | PRIMARY KEY, NOT NULL | JWT ID (unique identifier claim in the token) |
| `user_id` | UUID | NOT NULL | User associated with the token |
| `expired_at` | TIMESTAMP | NOT NULL | When the token naturally expires |
| `blacklisted_at` | TIMESTAMP | DEFAULT NOW() | When it was blacklisted |
| `reason` | VARCHAR(100) | NULLABLE | Reason (e.g., 'LOGOUT', 'SECURITY') |

### Indexes

- `idx_core_access_token_blacklist_expired_at` on `expired_at` (for cleanup)
- `idx_core_access_token_blacklist_user_id` on `user_id`

### Notes

- **Cleanup**: Delete rows where `expired_at < NOW()` since they are naturally invalid anyway.

---

**Last Updated**: 2026-04-10
**Documentation Version**: 1.1



## core.external_identities ? migration 012

Owner: auth-service. Columns: id UUID, user_id UUID references core.users(id), issuer VARCHAR(255), subject VARCHAR(255), email_at_link VARCHAR(255), created_at TIMESTAMPTZ. Unique (issuer,subject) prevents one provider identity from owning multiple local users; unique (user_id,issuer) prevents silently replacing a user identity. Canonical Google issuer is https://accounts.google.com. Email is enrollment metadata; returning login follows subject. No email-based migration backfill. Migration must precede auth deployment; do not alter live schema through Hibernate.
