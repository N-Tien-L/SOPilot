---
title: Core Schema Tables
description: Database tables for the core schema (auth-service ownership)
schema: core
owner: auth-service
---

# Core Schema Tables

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

- **Authorization Strategy**: `contexts/authorization/dual-strategy.md` - how these tables integrate with ACL
- **Service Ownership**: `contexts/service-boundaries/responsibilities.md` - auth-service responsibilities
- **Event Contracts**: `contexts/service-boundaries/events.md` - `user.status.changed` event

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

