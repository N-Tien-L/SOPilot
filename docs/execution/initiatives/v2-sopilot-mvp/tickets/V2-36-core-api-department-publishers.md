---
id: V2-36
title: "core-api: document write rights by department publisher and workspace publisher"
type: feat
status: done
created: 2026-11-10
updated: 2026-11-13
author: "Owner"
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-23, V2-24]
blocks: [V2-16, V2-31, V2-33]
branch: "feat/knowledge-core-api-department-publishers"
assignee: pair
---

# TICKET V2-36: Department publishers and workspace-wide publishers

> **Scope:** `knowledge` | **Size:** `L` | **Priority:** `P0`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `feat/knowledge-core-api-department-publishers`

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under `.agent/context/` are as they were at the time.

## 1. Context & goal

Implements [ADR-009](../../../../architecture/decisions/adr-009-department-publishers.md) per [TECH-V2-core-api §15](../../../../architecture/components/core-api.md): document write rights move from OWNER/ADMIN to the publishers of the owning department (`DEPARTMENTS` documents) or workspace-wide publishers (`WORKSPACE` documents). Read rights, tokens and ai-service are unchanged.

**Start condition:** met. ADR-009 `approved` 2026-11-10 (Q0–Q7 settled in ADR-009 §6); PRD-V2 FR-06, FR-25, FR-26, §8 item 9 amended accordingly (Q7).

## 2. Acceptance criteria

**Schema (migration `core/V009`, skill `flyway-migration`)**
- [x] `core.department_publishers`, `core.workspace_publishers`, `core.documents.owner_department_id` exactly as TECH §15.2: two-column FKs to `departments` and `memberships`, `fk_documents_owner_in_scope` deferred to commit, CHECK `WORKSPACE ⇔ owner_department_id IS NULL`; RLS `FORCE` and grants like the other tenant tables.
- [x] Backfill per decision Q6 and ADR-009 §4.4; `core.create_personal_workspace` and `POST /workspaces` make the creator a workspace publisher. `./scripts/check-migrations.ps1` green; no committed migration edited.

**Write rights (core-api)**
- [x] `DocumentWritePolicy` is the single check point for the 7 document write endpoints (TECH §15.1); `DocumentService` no longer has `requireManager()` outside `deleteAll`.
- [x] The right publisher: a publisher of department D uploads, uploads a replacement, retries, edits metadata, applies suggestions, changes the department list (keeping D) and deletes documents owned by D; a workspace publisher does the same for `WORKSPACE` documents.
- [x] The wrong publisher: a publisher of department D2 writing a D-owned document that D2 can read (listed in `document_departments`) → `403 NOT_PUBLISHER`; a document D2 cannot read → `404`, the name not revealed. A department publisher writing a `WORKSPACE` document → `403`.
- [x] ADMIN refused: an ADMIN who is not a publisher gets `403` on all 7 write endpoints; still creates/edits/deletes departments, categories and members as before; still reads every document.
- [x] An OWNER who is not a publisher gets `403` on upload, replacement upload, retry, metadata edit, applying suggestions, `PUT /visibility` (ADR-009 decision 8, Q4).
- [x] OWNER revocation: an `ACTIVE` OWNER can delete any document, including those of departments without a publisher; audit `actingAs = OWNER`. An OWNER just demoted to ADMIN (old token still valid) → `403` (the role is read from the DB).
- [x] OWNER reassignment: only the OWNER can call the §15.4 API (ADMIN, MEMBER → `403`); after the OWNER changes department D's publisher from A to B, A's next write request → `403`, B's → success, with no token refresh needed. Assigning someone from another department → `409 PUBLISHER_NOT_IN_DEPARTMENT`; a `SUSPENDED` person → `409 MEMBER_NOT_ACTIVE`; an `ARCHIVED` department → `409 DEPARTMENT_ARCHIVED`.
- [x] Leaving a department: changing a publisher's `departmentId` deletes the publisher row in the same transaction and writes an audit entry; when department D has no publisher left, every new document owned by D → `403`. Removing a member or leaving the workspace cascades the publisher row.
- [x] A `READY` version is unaffected by changing or removing a publisher (Q3): `current_version_id`, the status and `rag.document_access` are unchanged; the document is still answerable.
- [x] Ownership transfer (Q5): `PUT /documents/{id}/ownership` is OWNER-only (ADMIN, publisher → `403`). Three cases `DEPARTMENTS → WORKSPACE`, `WORKSPACE → DEPARTMENTS`, changing the owning department: the writer changes on the next request; `current_version_id`, versions and chunks unchanged; `rag.document_access` updated through `ACCESS_UPDATED`; audit `DOCUMENT_OWNERSHIP_CHANGED`. An `ARCHIVED` target department → `409`; an owning department outside `departmentIds` → `400`.
- [x] A publisher calling `PUT /visibility` to change the type or drop the owning department → `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`; the DB blocks dropping the owning department at commit (`fk_documents_owner_in_scope`).
- [x] Changing the publisher concurrently with an upload does not let the old person write after the change has committed (`FOR SHARE`/`FOR UPDATE` locks on the publisher row); integration test present.
- [x] `GET /api/v1/publishers` for every `ACTIVE` member, without emails; `GET /members/me` has `publisherOf`. `GET /documents/{id}/versions` returns `uploadedBy`, `uploadedAt` (from `uploaded_by`, `created_at`).
- [x] Audit `PUBLISHER_ASSIGNED`, `PUBLISHER_UNASSIGNED`; `DOCUMENT_*` carry `ownerDepartmentId`, `actingAs`; `DOCUMENT_OWNERSHIP_CHANGED` (TECH §15.5).

**Read isolation (FR-29, FR-19), regression**
- [x] The ADR-007 §4.4 read matrix holds with publisher data: a MEMBER outside the department still gets `404` on list, detail and download URL; publishers read no extra documents outside their department; OWNER/ADMIN still read every document.
- [x] The `INGEST_REQUESTED`, `ACCESS_UPDATED` payloads are unchanged (no `owner_department_id`); ai-service needs no change.
- [x] `tests/tenant-isolation` green with the two new tables (RLS FORCE, the negative control red when RLS is disabled); `TenantIsolation*IT` green.

**Docs**
- [x] Update `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `services/core-api/README.md` along with the change; the ERD moves the proposed part to actual.
- [x] Code deviations from TECH §15 recorded as an implementation-notes table in TECH-V2-core-api.

## 3. Guide

- Order: migration → `DocumentWritePolicy` + replacing the 7 `requireManager()` calls → the publisher API and `PUT /ownership` → `MemberService` (deleting the row on department change) → audit → tests → docs.
- Read publishers and membership from the DB inside the write operation's `TenantTx`, with an explicit `workspace_id` filter (`CLAUDE.md` constraint 4); do not put publishers into the token.
- `DocumentView` uses the shared (non-locking) publisher query to decide whether to return management fields.
- No change to `services/ai-service`, `rag.*` or the §8 contract.

## 4. Testing

| Kind | Content | Command |
|---|---|---|
| Unit | The write-rights table (role × publisher × endpoint, including `PUT /ownership`), `404`/`403` order, `requireCanCreate`, `requireCanDelete`, `requireCanTransfer` | `./scripts/run-tests.ps1 -Scope core-api -Type unit` |
| Integration | The "Write rights" criteria and the FR-29 read regression, concurrent locking, deferred FK | `./scripts/run-tests.ps1 -Scope core-api -Type all` (Docker) |
| Isolation | The new tables in the tenant isolation suite | `cd tests/tenant-isolation; uv run pytest -v` (Docker) |
| Migration | Naming, no edits to old files, no destructive DDL | `./scripts/check-migrations.ps1` |

## 5. Changed files (planned)

| Path | Action |
|---|:---:|
| `infrastructure/db/migrations/core/V009__department_publishers.sql` | CREATE |
| `services/core-api/src/main/java/com/sopilot/core/document/DocumentWritePolicy.java` | CREATE |
| `services/core-api/src/main/java/com/sopilot/core/document/DocumentService.java`, `DocumentView.java`, `DocumentController.java` | MODIFY |
| `services/core-api/src/main/java/com/sopilot/core/department/` (publisher assignment API), `member/MemberService.java` | MODIFY |
| `services/core-api/src/test/java/...` (unit, IT) | CREATE/MODIFY |
| `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `services/core-api/README.md` | MODIFY |

## 6. Quick check commands

```powershell
./scripts/validate-build.ps1 -Scope core
./scripts/check-migrations.ps1
./scripts/pre-commit-check.ps1
```

## 7. Implementation notes and evidence (2026-11-11)

- Migration `core/V009__department_publishers.sql` (V008 was used by V2-30): two publisher tables, `documents.owner_department_id`, backfill (Q6 lists multi-department documents with `NOTICE`), replacing `create_personal_workspace`.
- Code: `document/DocumentWritePolicy` (the single check point), `DocumentService` (no `requireManager()` outside `deleteAll`, adds `transferOwnership`), `department/PublisherRepository|Service|Controller`, `MemberService` (deleting the publisher row on department change, audit on removal/leaving), `GET /members/me` with `publisherOf`, `GET /documents/{id}/versions` with `uploadedBy`/`uploadedAt`.
- **Deviation from the ticket:** the code has no `POST /documents/{id}/suggestion/apply` endpoint yet (not done in V2-24), so `DocumentWritePolicy` protects the 6 existing write endpoints; the suggestion endpoint will call `requireCanWrite` when added. Other deviations are in TECH-V2-core-api §17.
- Tests: `DocumentWritePolicyTest` (unit, the rights table), `DocumentPublisherIT` (right/wrong write rights, ADMIN, OWNER revocation, reassignment without refresh, leaving a department, Q3, the three ownership transfer cases, deferred FK, FR-29 reads, concurrent locking both ways); `DepartmentAuthorizationIT`, `DocumentLifecycleIT`, `DocumentMetadataVisibilityIT` updated for the new rules. See the run results in the handoff report.
- Not checked: the migration has not been applied to the owner's `sopilot-v2` volume (run `docker compose -f docker-compose.v2.yml up flyway-core` when ready); no UI yet (V2-31/V2-33).
