---
title: "Schema core (V2, core-api)"
status: approved
created: 2026-11-04
updated: 2026-11-13
author: "Owner"
affected_services: [core-api]
affected_schemas: [core]
refs:
  - docs/architecture/components/core-api.md
  - infrastructure/db/README.md
---

# Schema `core` (V2, core-api)

> **Implementation status:** migrations `core/V001`–`V010` (V2-08, V2-11, V2-12, V2-23, V2-24, V2-25, V2-29, V2-30, V2-36). Moved from `.agent/context/database/tables/core.md` (V2 section) and `database/schema.md` (V2 bootstrap) on 2026-11-13. The V1 `core` tables are archived at [v1-context/database/tables/core.md](../../archive/v1-context/database/tables/core.md).

Source of truth: the migrations in `infrastructure/db/migrations/core/` and [TECH-V2-core-api](../components/core-api.md) §3. core-api is the only owner/writer of V2 `core`. Schema changes are new Flyway files only (skill `flyway-migration`).

## 1. Roles, grants and bootstrap

- `sopilot_migrator` owns both schemas. App roles own no tables, are `NOBYPASSRLS`, and have DML only in their own schema (`sopilot_core_app` here).
- `V002` in each chain revokes the creator's global default function EXECUTE from PUBLIC and revokes PUBLIC EXECUTE on the existing `current_workspace`, `current_app_user`, `touch_updated_at` helpers. Explicit app-role grants remain. Schema-local REVOKE alone cannot remove PostgreSQL's global PUBLIC default. The two chains take transaction advisory lock `24082026` before changing shared defaults; new helpers require explicit EXECUTE grants. `V001` checksums are unchanged.
- Bootstrap verification uses `eval/sopilot_eval/infra_check.py` on a disposable tmpfs project; see `infrastructure/db/README.md` and [the V2-05/V2-08 acceptance report](../../quality/test-reports/audit-v2-05-v2-08-acceptance-2026-10-25.md).

## 2. Tables

Added by `V003` (V2-11):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.users` | no (global) | `id` uuid PK (UUIDv7 from app), `email` lower-case, not unique; `display_name`, `avatar_url`, `last_active_workspace_id` (no FK) |
| `core.external_identities` | no (global) | `user_id` FK, `issuer`, `subject`, `email_at_link`, `hosted_domain`; `UNIQUE (issuer, subject)`, `UNIQUE (user_id, issuer)` |
| `core.workspaces` | FORCE | `name` 1–100, `kind` `PERSONAL`/`TEAM`, `created_by` FK; `uq_personal_workspace` = one PERSONAL per user |
| `core.memberships` | FORCE | PK `(workspace_id, user_id)`, `role` `OWNER`/`ADMIN`/`MEMBER`, `status` `ACTIVE`/`SUSPENDED` (+ `suspended_at` check), `display_name`, `email`, `department_id` |

`V003` also adds the policies `workspace_visibility`, `membership_visibility`, plus `definer_access` for `sopilot_migrator` so SECURITY DEFINER helpers work under FORCE RLS, and `core.create_personal_workspace(uuid, uuid, text, text)` (SECURITY DEFINER, EXECUTE only for `sopilot_core_app`), which returns the user's PERSONAL workspace id, creating it and the OWNER membership if absent.

Added by `V004` (V2-23) and `V005` (V2-12):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.departments` | FORCE | `name` 1-100, `status` `ACTIVE`/`ARCHIVED`; `UNIQUE (workspace_id, lower(name))`; `UNIQUE (workspace_id, id)` is the FK target |
| `core.memberships` (extended) | FORCE | + `employee_code` (unique per workspace when set), `job_title`; FK `(workspace_id, department_id)` -> departments `RESTRICT` |
| `core.invitations` | FORCE | `email`, `role` `ADMIN`/`MEMBER`, profile fields, `token_hash` unique, `expires_at`, `accepted_at`/`revoked_at`; one pending per `(workspace_id, email)`; department FK `SET NULL`; logic in `member/InvitationService` (V2-30) |
| `core.categories` | FORCE | `name`, `status`; `UNIQUE (workspace_id, lower(name))`; API in V2-24 |
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

Added by `V007` (V2-24) and `V010` (V2-25):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.tags` | FORCE | `name` 1–50 chars (case kept as typed); unique on `(workspace_id, lower(name))`; `UNIQUE (workspace_id, id)` for the composite FK |
| `core.document_tags` | FORCE | PK `(document_id, tag_id)`; composite FKs `(workspace_id, document_id)` → `documents` and `(workspace_id, tag_id)` → `tags`, both `ON DELETE CASCADE`; index `ix_document_tags_tag (workspace_id, tag_id)` |
| `core.document_suggestions` | FORCE | `V010` (V2-25). One row per version: `method` (`LLM` / `RULES_FALLBACK`), suggested `title`, `description`, `category_id`, `proposed_category_name` (stored, never created), `tags text[]`. Written by `PUT /internal/documents/{id}/suggestions`; applied to the document only when the version is current and the field's source is not `USER` (`document/SuggestionService.java`) |

Added by `V008` (V2-30): no table. `definer_access` policies `TO sopilot_migrator` on `core.invitations` and `core.departments` (FORCE RLS binds the owner), index `ix_invitations_email`, and two `SECURITY DEFINER` functions granted to `sopilot_core_app` only: `core.accept_invitation(p_user_id, p_token_hash, p_invitation_id)` (locks the invitation, returns an outcome code and creates the membership) and `core.pending_invitations_for_user(p_user_id)`. Both read the address from `core.users`, never from the caller.

Added by `V009` (V2-36, ADR-009):

| Table | RLS | Key columns / constraints |
|---|---|---|
| `core.department_publishers` | FORCE | PK `department_id` (one publisher per department), `workspace_id`, `user_id`, `assigned_at`; composite FKs `(workspace_id, department_id)` -> departments and `(workspace_id, user_id)` -> memberships, both `ON DELETE CASCADE` |
| `core.workspace_publishers` | FORCE | PK `workspace_id` (one per workspace), `user_id`, `assigned_at`; composite FK to memberships `ON DELETE CASCADE` |
| `core.documents` (extended) | FORCE | + `owner_department_id`; FK `(workspace_id, owner_department_id)` -> departments `RESTRICT`; `fk_documents_owner_in_scope` `(id, owner_department_id)` -> `document_departments` `DEFERRABLE INITIALLY DEFERRED`; `ck_documents_owner_matches_visibility`: `visibility = 'WORKSPACE'` iff `owner_department_id IS NULL` |

`V009` also backfills `workspace_publishers` (creator while ACTIVE, else the earliest ACTIVE OWNER; deleted workspaces skipped) and `documents.owner_department_id` (ADR-009 Q6; documents in several departments are listed as `NOTICE` in the Flyway log), adds `definer_access` policies for `sopilot_migrator` on the two new tables, `documents` and `document_departments`, and replaces `core.create_personal_workspace` so a newly created PERSONAL workspace gets its creator as workspace publisher (only on creation, not on later logins).

## 3. Functions

| Function | Use |
|---|---|
| `core.create_personal_workspace(p_user_id, p_workspace_id, p_name, p_email)` | JIT: the user's PERSONAL workspace and OWNER membership, idempotent |
| `core.claim_outbox_batch(int)` | Leases due events of every workspace for 60 s (`FOR UPDATE SKIP LOCKED`) |
| `core.referenced_object_keys(text[])` | Tells the storage janitor which object keys a version still references |
| `core.accept_invitation(...)`, `core.pending_invitations_for_user(...)` | Invitation redemption and listing for a user without a workspace yet (V008) |
