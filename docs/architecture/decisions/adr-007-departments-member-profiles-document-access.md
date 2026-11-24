---
id: ADR-007
title: "V2: per-workspace member profiles, flat departments and department-based read access to documents"
status: approved
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
deciders: ["Owner"]
amends: [ADR-005]
supersedes: []
superseded_by: ""
---

# ADR-007: Member profiles, flat departments and department-based document access

> **Status:** `approved` (2026-10-20) | **Proposed:** `2026-10-19` | **Decider:** `Owner`
>
> This ADR amends ADR-005: it replaces the trade-off "departments and department-based permissions are lost in V2" with a model of flat departments inside the workspace. ADR-005's workspaces, memberships, RLS and per-workspace tokens are unchanged.
>
> **Amended by:** [ADR-009](adr-009-department-publishers.md) (`approved`, 2026-11-10) moves the document write rights of §4.4 from OWNER/ADMIN to per-department publishers and a workspace publisher; read access is unchanged.
>
> Translated from Vietnamese on 2026-11-13; section numbers are stable (cited by code).

---

## 1. Context and the decision to make
- The owner asked (2026-10-19) to keep staff management, departments and department-based document permissions for small companies, without carrying over the old HR roster and without bothering individual users.
- The current code (checked 2026-10-19):
  - `core.departments` is global and has `parent_id` (a tree); `DepartmentService.deleteDepartment` only deactivates, but `DepartmentController` has no delete endpoint.
  - `core.employee_roster` creates profiles before sign-in, has a globally unique email, and gives each person exactly one `department_id`.
  - `metadata.document_access_rules` is a general ACL (`ROLE | DEPARTMENT | USER`) with `target_department_id ... ON DELETE CASCADE`: hard-deleting a department deletes its rules and can leave a restricted document unrestricted.
  - `knowledge.chunks` copies `allowed_roles/allowed_departments/allowed_users/access_level` at ingest; nothing updates them when the rules change. The `access_level` column defaults to `'PUBLIC'`.
  - `ai-qa-service` `chunk_repo.py` filters with `access_level = 'PUBLIC' OR allowed_* && ...` and inserts `department_id` into SQL with an f-string (for score boosting).
- Reusable parts: the one-department-per-person idea, the department/category/tag admin UI in `frontend/web/app/admin/`, and metadata-service's `access-check` as a reference. The schema is not ported as is.

## 2. Evaluation criteria
1. Individual users see and fill in nothing about staff or departments.
2. Read access is correct on every data path, including before anything reaches the LLM context.
3. Changing a department or a document's visibility never widens access by accident (fail closed).
4. ai-service does not call core-api on every request (keeps criterion 4 of ADR-005).
5. As few tables and concepts as possible.

## 3. Options considered

### Staff profiles
- **A. A roster created before sign-in (as before).** (−) Two tables parallel to invitations; a globally unique email conflicts with multiple workspaces.
- **B. The profile lives on the membership, and the invitation carries the initial profile (chosen).** The invitation is the "waiting to join" state. On acceptance the profile is copied to the membership.

### Departments per member
- **One (chosen).** Matches the old model and keeps the token small; documents can still be restricted to several departments.
- **Many.** (+) Flexible for people with several roles. (−) An extra join table, a longer token, a more complex UI. Left as P1.

### Document permission model
- **A general ROLE/DEPARTMENT/USER ACL (as before).** (−) Hard to test completely, easy to get wrong.
- **Two scopes `WORKSPACE | DEPARTMENTS` + role (chosen).**

### Where access is evaluated during retrieval
- **Copy permissions into every chunk.** (−) Changing permissions rewrites every chunk; easily drifts, as in the old code.
- **A per-document access table in ai-service, joined during retrieval (chosen).** One row per document; changing permissions updates one row.

## 4. Decision and rationale

### 4.1 Data model (DDL details in TECH-V2)
- `core.users`: global accounts (ADR-005), no department.
- `core.memberships`: adds `display_name`, `employee_code` (optional, unique on `(workspace_id, employee_code)` when present), `job_title` (optional), `department_id` (nullable), `status` (`ACTIVE | SUSPENDED`), `suspended_at`.
- `core.invitations`: adds `display_name`, `department_id`, `employee_code`, `job_title`.
- `core.departments(workspace_id, name, status ACTIVE|ARCHIVED)`, name unique within the workspace, no `parent_id`. Foreign keys from memberships and from document scopes use `ON DELETE RESTRICT`.
- `core.document_departments(document_id, department_id)` for `DEPARTMENTS` documents; `core.documents.visibility` is `WORKSPACE | DEPARTMENTS`, default `WORKSPACE`. Constraint: `DEPARTMENTS` must have at least one row.
- Flat `core.categories(workspace_id, name, status)`; nullable `documents.category_id`; per-workspace `core.tags` and `core.document_tags`.
- All the tables above have `workspace_id` and RLS as in ADR-005.

### 4.2 Member lifecycle
`invitation (pending) → ACTIVE ⇄ SUSPENDED → left/removed`. `SUSPENDED` stops token issuance for that workspace but keeps the profile, conversations and audit. Leaving/removal deletes the membership; that person's conversations in the workspace are kept for audit until the workspace is deleted. A workspace-level block does not affect the global account; deleting the global account is out of scope for V2.

### 4.3 Departments
- Moving department: updates the membership; takes effect at the next token issuance (≤ 15 minutes, the same revocation mechanism as ADR-005 §4.4).
- Deactivation (`ARCHIVED`): no new assignments; current members keep it until moved; documents restricted to that department stay restricted. If nobody is left in the department, only OWNER/ADMIN can read those documents.
- Hard delete: only when no membership, pending invitation or document references it (FK `RESTRICT`).
- Personal workspaces: no default department; the UI hides departments while the workspace has a single member.

### 4.4 Permission matrix
| Action | OWNER | ADMIN | MEMBER in department D | MEMBER without a department |
|---|:---:|:---:|:---:|:---:|
| Read `WORKSPACE` documents | ✓ | ✓ | ✓ | ✓ |
| Read `DEPARTMENTS` documents that include D | ✓ | ✓ | ✓ | |
| Read `DEPARTMENTS` documents that do not include D | ✓ | ✓ | | |
| Upload, edit metadata, change visibility, delete documents | ✓ | ✓ | | |
| Manage departments, categories, invitations, edit profiles, suspend members (except OWNER) | ✓ | ✓ | | |
| Suspend/remove an OWNER, view audit | ✓ | | | |

> **Amended 2026-11-10 by [ADR-009](adr-009-department-publishers.md):** the "Upload, edit metadata, change visibility, delete documents" row now belongs to the publisher of the document's scope (OWNER revokes any document; ADMIN does not write documents). The read rows are unchanged.

"Read" covers lists, search, detail, preview, download, appearing in retrieval results, the LLM context and citations. A `SUSPENDED` member has no rights; an access token issued before the suspension stays valid until it expires (§5). Document-management rights for department heads are P1.

### 4.5 Enforcement
- The access token adds a `wdept` claim (the membership's department, or empty) next to `wid` and `wrole`. Refresh re-checks the membership, its `status` and `department_id`.
- ai-service keeps `rag.document_access(workspace_id, document_id, visibility, department_ids uuid[])`. Dense and BM25 queries join this table with `wrole IN (OWNER, ADMIN) OR visibility = 'WORKSPACE' OR :wdept = ANY(department_ids)`, **before** `LIMIT k`. Rerank and the LLM only receive filtered candidates. Everything is parameterized, no f-strings.
- Changing a document's visibility: core-api writes the DB, calls ai-service synchronously to update `rag.document_access`, and the outbox retries on failure. A new document enters retrieval only once its access row exists (`READY` requires the access row); a missing access row means it cannot be read (fail closed).
- Download/preview: core-api checks access, then issues a pre-signed URL valid ≤ 5 minutes.
- Caches: answer/retrieval-result caches (if any) use a key including `workspace_id`, `wrole` and `wdept`; the embedding cache holds only vectors keyed by chunk content and never returns text.
- Conversation history: on reopening, every document an answer was generated from (sources in the LLM context and citations) is checked against current access; an answer with a document no longer readable is hidden with a reason. (Changed 2026-11-09 to match §4.4: the earlier version checked only citations; details in [TECH-V2-ai-service §7.5](../components/ai-service.md).)

## 5. Impact and consequences
- **Positive:** enough for teams and small companies; individual users are unaffected; a single filter point in the retrieval SQL; changing permissions needs no re-embedding.
- **Trade-offs:**
  - Revocation by department change or suspension lags by at most one access-token lifetime; narrowing a document's visibility takes effect when ai-service receives the update.
  - One department per person does not serve people with several roles (P1).
  - `rag.document_access` is data copied between two services; synchronization needs tests.
- **Next actions (historical, done):**
  - TECH-V2 (V2-03) fixes the DDL, token claims, the department/profile/metadata APIs and the access-update contract to ai-service.
  - FR-29: a department authorization test suite separate from FR-19.
  - On approval: rewrite the authorization context docs for this model together with the implementation, not before (now `docs/architecture/domain/identity-and-access.md`).
