---
id: ADR-009
title: "V2: document write rights belong to department publishers and a workspace publisher"
status: approved
created: 2026-11-10
updated: 2026-11-13
author: "Owner"
refs:
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/components/core-api.md
deciders: ["Owner"]
amends: [ADR-007]
supersedes: []
superseded_by: ""
---

# ADR-009: Department publishers and a workspace publisher

> **Status:** `approved` (2026-11-10) | **Proposed:** `2026-11-10` | **Decider:** `Owner`
>
> This ADR amends the **document write rights** of ADR-007 §4.4: uploading, editing metadata, changing visibility and deleting documents move from OWNER/ADMIN to **publishers**. Read access (the first three rows of ADR-007 §4.4, §4.5), token claims, the flat department model and one department per member are unchanged. DDL, API and the check point are in [TECH-V2-core-api §15](../components/core-api.md).
>
> Translated from Vietnamese on 2026-11-13; section numbers and the numbered decisions of §4.1 are stable (cited by code and migration `core/V009`).

---

## 1. Context and the decision to make

- ADR-007 §4.4 gives OWNER and ADMIN full write access to every document in the workspace, and says "document-management rights for department heads are P1". PRD-V2 FR-06, FR-25 and §8 item 9 say the same.
- The owner decided (2026-11-10) to separate two jobs: ADMINs keep administering people and catalogs (members, departments, categories), while document **content** is published by the person responsible in each department. Reason: in a company, a department's SOPs are issued by that department; a system administrator should not be able to edit another department's content.
- The code at the time (checked 2026-11-10, branch `feat/knowledge-core-api-metadata-visibility`):
  - Document write access is checked with `AuthPrincipal.requireManager()` (`wrole ∈ {OWNER, ADMIN}`) in 7 places in `DocumentService`; `DocumentView` uses `isManager()` to decide whether to return admin fields. There is no notion of a person responsible for a document. (`CategoryService`, `DepartmentService` and `MemberService` also use `requireManager()` but do not change.)
  - `core.document_versions.uploaded_by uuid NOT NULL REFERENCES core.users(id)` and `created_at` **already exist** since `core/V005`; `core.documents.created_by` also exists. The requirement "each version records who published it and when" (decision 5 below) is already met at the schema level.
  - `core.memberships` has PK `(workspace_id, user_id)` and exactly one nullable `department_id` (ADR-007). `core.departments` has `UNIQUE (workspace_id, id)` for two-column foreign keys.
  - `rag.document_access` (ai-service) holds only read scope; no write data needs to reach ai-service.

## 2. Evaluation criteria

1. Each document has exactly one person allowed to write it at any time, derivable from the DB without reading the audit log.
2. Read access is never widened (fail closed, ADR-007 criterion 3); the change touches only core-api's write paths.
3. No new role, no change to the `wrole`/`wdept` claims, nothing new for ai-service to know (ADR-005 criterion 4).
4. The main constraints live in the DB (FK, unique); the rest is checked in the same write transaction.
5. No review workflow, change requests or notifications inside the system.

## 3. Options considered

### Option A: ADMIN keeps write access (as in ADR-007)
- **Description:** the matrix stays; a department head who wants to publish asks an ADMIN.
- **(+)** No change to code, schema or tests.
- **(−)** ADMINs can edit every department's SOPs; no distinction between the system administrator and the person responsible for content. Contrary to the owner's decision.

### Option B: one publisher for the whole workspace
- **Description:** a single person may write every document.
- **(+)** One table with one row; the simplest access check.
- **(−)** A bottleneck on one person in a workspace with many departments; that person can still edit every department's documents, merely replacing "ADMIN" with "one person".

### Option C: per-department publishers + a workspace publisher (chosen)
- **Description:** each department has exactly one publisher, an `ACTIVE` member of that department; each workspace has exactly one publisher for `WORKSPACE` documents. Each document has an owning department (`owner_department_id`), or `NULL` for a `WORKSPACE` document.
- **(+)** The writer of each document follows directly from two small tables; ADMINs can no longer edit content; a `DEPARTMENTS` document shared by several departments still has one responsible person.
- **(−)** Two extra tables, one column and one access check on every document write endpoint. There is a gap when a publisher leaves the department (that department cannot publish until the OWNER reassigns).

### Variants of option C that were rejected
- **Add a `PUBLISHER` role to `wrole`.** (−) One person can be both ADMIN and publisher; the token would have to carry the departments that may be written; changing the publisher would wait for access-token expiry (≤ 15 minutes). Rejected by the owner (decision 7).
- **Put publishers in a token claim.** (−) As above; reading write rights from the DB inside the write transaction takes effect immediately and needs no change to JWKS or ai-service.
- **A three-column FK `(workspace_id, user_id, department_id) → memberships`** so the DB guarantees the publisher belongs to the department. (−) PostgreSQL has no `ON UPDATE SET NULL (column)`; with `RESTRICT`, an ADMIN could not move a publisher to another department until the OWNER removed them first, contrary to decision 4 ("on leaving the department, the OWNER reassigns"). Instead: core-api deletes the publisher row in the same transaction that changes the department, and re-checks at write time (TECH §15.3).

## 4. Decision and rationale

**Chosen option: C.** The items below are the owner's decisions (2026-11-10), including the questions settled in §6; the owner approved the whole ADR the same day.

### 4.1 Model
1. **Department publisher.** Each `core.departments` row has at most one publisher (`core.department_publishers`, PK `department_id`). The publisher must be an `ACTIVE` member whose `memberships.department_id` equals that department. A department without a publisher cannot have documents published or edited by anyone.
2. **Workspace publisher** *(owner confirmed 2026-11-10, §6 Q0, Q1)*. Each workspace has at most one publisher (`core.workspace_publishers`, PK `workspace_id`), **only** for documents with `visibility = WORKSPACE`; this person cannot publish or edit `DEPARTMENTS` documents (unless they are also the owning department's publisher). They must be an `ACTIVE` member; no department is required.
3. **Owning department.** `core.documents.owner_department_id uuid NULL`:
   - `NULL` ⇔ `visibility = WORKSPACE` (CHECK). A `DEPARTMENTS` document always has exactly one owning department, which must be in the document's `core.document_departments`.
   - A `DEPARTMENTS` document shared by several departments: only the owning department's publisher may write; the other departments in `document_departments` only read.
4. **Assigning and changing publishers.** Only the OWNER assigns, changes and removes publishers (department and workspace). When a publisher is removed, leaves the department, or leaves/is removed from the workspace, the publisher row is deleted in the same transaction; the OWNER reassigns manually. Until then, no new documents can be published in that scope and existing ones cannot be edited. There is no automatic assignment.
5. **Who published.** Each version records `uploaded_by` (user id) and the publication time. These two columns already exist (`document_versions.uploaded_by`, `created_at`, `core/V005`); TECH §15 calls `created_at` the publication time and **adds no** duplicate `uploaded_at` column. The audit log additionally records the owning department and the publisher role at write time (TECH §15.5).
6. **Outside the system.** There is no change-request, review, notification or approval-queue flow. Someone who wants a document changed contacts the publisher outside the system; the system only shows who the publisher is.
7. **No new role.** `wrole` stays `OWNER | ADMIN | MEMBER`; `wdept` is unchanged. Publisher is an extra attribute assigned to a membership and read from the DB at write time. An OWNER, ADMIN or MEMBER can be a publisher; effective rights are the union of role rights and publisher rights.
8. **The OWNER assigns responsibility but does not author content** *(owner decision 2026-11-10, §6 Q4, Q5)*. Separate the person who issues content (the publisher) from the person who assigns and revokes (the OWNER), as in ISO 9001 document control:
   - The OWNER can **revoke** (delete) any document in the workspace without being a publisher, to deal with a wrong document when the scope has no publisher or the publisher is absent.
   - The OWNER can **transfer responsibility** for a document: switch `WORKSPACE ⇄ DEPARTMENTS` or change the owning department, together with the list of departments that may read, in one operation. Content, versions and history are kept; only the writer and the read scope change.
   - The OWNER does **not** upload, upload replacements, retry, edit metadata or apply suggestions without being the publisher of that scope; to do so, they assign themselves as publisher.
   - The workspace creator is the default workspace publisher (§4.4) and can hand it to someone else (for example Administration). In a workspace with several OWNERs every OWNER has both rights above; there is still only one workspace publisher.
   - Every revocation or responsibility transfer is audited as the OWNER.

Corresponding roles in a company (for illustration, not a constraint):

| System role | Usually | Responsible for |
|---|---|---|
| OWNER | Director, business owner | Who may publish what; revoking and transferring responsibility for documents |
| ADMIN | System administration, HR | People and catalogs; does not touch content |
| Workspace publisher | Administration, ISO secretary, or the director in a small company | Company-wide documents |
| Publisher of department D | Department head or a delegate | Department D's SOPs |
| MEMBER | Employee | Reads, asks, contacts the publisher when something needs fixing |

### 4.2 Permission matrix (replaces the corresponding rows of ADR-007 §4.4)

Column "Pub. WS" = workspace publisher; "Pub. D" = publisher of department D. One person can be in several columns (for example an ADMIN who is also Pub. D); then the rights are the union.

| Action | OWNER | ADMIN | Pub. WS | Pub. D | Other MEMBER | Change from ADR-007 §4.4 |
|---|:---:|:---:|:---:|:---:|:---:|---|
| Read `WORKSPACE` documents | ✓ | ✓ | ✓ | ✓ | ✓ | Unchanged |
| Read `DEPARTMENTS` documents that include one's department | ✓ | ✓ | ✓ | ✓ | ✓ | Unchanged |
| Read `DEPARTMENTS` documents that do not include one's department | ✓ | ✓ | | | | Unchanged (publishers get no extra read access) |
| Upload, upload a replacement, retry, edit metadata, apply suggestions on `WORKSPACE` documents | | | ✓ | | | **Changed:** OWNER, ADMIN removed (decision 8) |
| The same for `DEPARTMENTS` documents owned by D | | | | ✓ | | **Changed:** OWNER, ADMIN removed; only the owning department's publisher |
| Delete (revoke) documents | ✓ (any document) | | ✓ (`WORKSPACE` documents) | ✓ (documents owned by D) | | **Changed:** ADMIN removed; the OWNER can revoke any document (§6 Q4) |
| Change the list of departments that may read a document owned by D (keeping D in the list) | ✓ (via responsibility transfer) | | | ✓ | | **Changed:** split from ADR-007's "change visibility" row |
| Transfer responsibility: switch `WORKSPACE ⇄ DEPARTMENTS` or change the owning department | ✓ | | | | | **New:** OWNER only (§6 Q5) |
| View version history, `FAILED` reasons, metadata field sources, suggestions | ✓ | ✓ | ✓ (`WORKSPACE` documents) | ✓ (documents owned by D) | | **New:** the responsible publisher is added; OWNER/ADMIN still see them (read) |
| Assign, change, remove department and workspace publishers | ✓ | | | | | **New** |
| See who publishes for each department and for the workspace | ✓ | ✓ | ✓ | ✓ | ✓ | **New** (to make contact outside the system) |
| Manage departments, categories, invitations, edit profiles, suspend members (except OWNER) | ✓ | ✓ | | | | Unchanged |
| Suspend/remove an OWNER, view audit | ✓ | | | | | Unchanged |

Notes:
- ADR-007 §4.4's row "Upload, edit metadata, change visibility, delete documents" is replaced by the four "Changed" rows above. ADR-007 §4.4's sentence "document-management rights for department heads are P1" is replaced by this ADR: department publishers are in the MVP.
- A publisher of an `ARCHIVED` department can still edit and delete that department's existing documents, but cannot create new documents owned by it (consistent with "no new assignments to an `ARCHIVED` department" in ADR-007 §4.3). No new publisher is assigned to an `ARCHIVED` department.
- A write refused when the caller can read the document → `403 NOT_PUBLISHER`; when the caller cannot read it → `404` as in ADR-007 (the name is not revealed). Creating a document without being the target scope's publisher → `403 NOT_PUBLISHER`.
- A `SUSPENDED` member has no rights (ADR-007); their publisher row is kept, but the write-time check requires `ACTIVE`.

### 4.3 Enforcement
- A single check point in core-api (`DocumentWritePolicy`, TECH §15.3) for every document write endpoint reads the publisher from the DB in the same transaction and locks the publisher row (`FOR SHARE`) so it cannot run concurrently with the OWNER changing publishers.
- Read access is unchanged: core-api's read filter (TECH §5.6) and `rag.document_access` (ADR-007 §4.5) use neither `owner_department_id` nor the publisher tables. ai-service is unchanged.
- The current `READY` version is unaffected when the publisher changes *(owner decision 2026-11-10, §6 Q3)*: changing the publisher only changes who may write next, not the status, read scope or chunks.

### 4.4 Migrating existing data
- `workspace_publishers`: each non-deleted workspace gets `created_by` if that person is still an `ACTIVE` member, otherwise the earliest-joined `ACTIVE` OWNER. `PERSONAL` workspaces and newly created `TEAM` workspaces assign the creator automatically (in `core.create_personal_workspace` and `POST /workspaces`), so personal workspaces, eval and demos can still upload.
- `department_publishers`: no backfill; every department starts without a publisher until the OWNER assigns one (per decision 4).
- `documents.owner_department_id` for existing `DEPARTMENTS` documents: see §6 Q6.

## 5. Impact and consequences

- **Positive:**
  - The writer of each document is derivable from the DB; ADMINs can no longer edit SOP content.
  - No change to tokens, JWKS, ai-service or `rag.document_access`; the FR-29 read tests keep their meaning.
  - Changing a publisher takes effect on the next write request (no waiting for token expiry).
- **Trade-offs:**
  - A gap when a publisher leaves the department: that department cannot publish or edit until the OWNER reassigns. Accepted per decision 4.
  - Each document write request adds one query that locks the publisher row.
  - The OWNER can only revoke or transfer responsibility, not quickly fix wrong content without being a publisher; an ADMIN has no rights on documents (§6 Q4).
  - One more OWNER-only endpoint for responsibility transfer (TECH §15.4), with tests.
  - The knowledge-gap list (FR-17, V2-13) is still visible only to OWNER and ADMIN, not to publishers. An ADMIN sees missing documents but cannot write, so they must tell the relevant department's publisher outside the system (manually). Accepted for the MVP because: (1) `NO_EVIDENCE` and `GENERATOR_NOT_FOUND` questions cannot be tied to a document or department (ai-service fails closed, TECH-V2-ai-service §3.4); (2) `rag.document_access` has no `owner_department_id`; (3) letting publishers see it would require putting publishers in the token or letting ai-service call core-api, contrary to "no change to tokens or ai-service" above; (4) department A's publisher would read (PII-masked) questions from department B's staff. Letting publishers see and handle this list is outside this ADR; doing it after the MVP needs its own ADR.
  - PRD-V2 FR-06, FR-25 and §8 item 9 must be updated once this ADR is approved.
  - A single-member workspace: that person is the OWNER and the workspace publisher; `DEPARTMENTS` documents can be published only after creating a department, placing themselves in it and assigning themselves as its publisher.
- **Next actions (on approval):**
  - TECH-V2-core-api §15 moves from proposal to specification; migration `core/V009` through the `flyway-migration` skill.
  - Ticket [V2-36](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-36-core-api-department-publishers.md) implements core-api and the write-authorization tests; V2-31 and V2-33 show the write buttons and the publisher assignment screen; V2-16 creates publishers for the demo data.
  - Update PRD-V2 FR-06, FR-25, §8 item 9.
  - Update the identity and core-schema context docs (then `.agent/context/authorization/v2-core-identity.md` and `.agent/context/database/tables/core.md`, now `docs/architecture/domain/identity-and-access.md` and `docs/architecture/data/core-schema.md`) together with the implementation (as for ADR-007), not before.
  - Update the diagram `docs/architecture/diagrams/sopilot-database-erd.excalidraw` from "proposed" to actual once the migration is merged.

## 6. Open questions (the owner decides; the ADR does not settle them itself)

> **Owner decision 2026-11-10:** Q0 keep the workspace publisher; Q1 no (the workspace publisher writes only `WORKSPACE` documents); Q3 the `READY` version is unaffected; Q7 update PRD-V2 after this ADR has resolved all open questions and is approved. Q2 no (as proposed); Q6 by the publishing user's department rule (as proposed); Q4, Q5 per decision 8 (the OWNER revokes and transfers responsibility, does not author content). No open questions remain; the owner approved the ADR (`approved`) the same day.

| # | Question | Known constraints | Proposal |
|---|---|---|---|
| Q0 | Keep the **workspace publisher** (decision 2)? | Without it nobody could write `WORKSPACE` documents, unless `WORKSPACE` documents also had an owning department (then the rule "`NULL` ⇔ `WORKSPACE`" would have to go). | **Decided: keep.** One row per workspace, needed for personal workspaces and eval. |
| Q1 | May the workspace publisher publish `DEPARTMENTS` documents, or only `WORKSPACE`? | If yes, a `DEPARTMENTS` document published by this person has no owning department, so the rule "`owner_department_id IS NULL` ⇔ `WORKSPACE`" no longer holds; a separate column or value would be needed to know who writes (for example `owner_scope WORKSPACE|DEPARTMENT`). | **Decided: no.** `WORKSPACE` only; the rule "`NULL` ⇔ `WORKSPACE`" stays and the TECH §15.2 DDL is unchanged. |
| Q2 | Can one person publish for several departments? | With ADR-007 (one department per member) and decision 1 (the publisher must belong to the department), a person **can only** publish for their own department. "Yes" would need relaxing decision 1 or allowing members in several departments (ADR-007's P1). A person can still be both a department publisher and the workspace publisher. | **Decided: no** in the MVP (a natural consequence of the schema). Documents shared by several departments are handled by one owning department (decision 3). |
| Q3 | When the OWNER changes a publisher, is the current `READY` version affected? | Changing the publisher touches neither `document_versions`, `rag.document_access` nor chunks. | **Decided: no effect.** The old version keeps serving Q&A; the new publisher uploads a replacement when needed. |
| Q4 | Does the OWNER have implicit write rights (without being a publisher), for example to remove a wrong document when a department has no publisher? | The "write rights move to publishers" decision is explicit only about ADMIN. The OWNER can assign themselves as workspace publisher at any time; to publish for department D they must belong to D. | **Decided:** the OWNER has no implicit content-writing rights (they assign themselves as publisher when needed), but **can revoke (delete) any document** (decision 8). |
| Q5 | Who may switch `WORKSPACE ⇄ DEPARTMENTS` or move the owning department (transfer responsibility for a document)? | Each of these changes who may write. If D's publisher switched a document to `WORKSPACE`, they would lose write access to it. | **Decided: OWNER only**, through a separate responsibility-transfer operation that keeps content and history (decision 8, TECH §15.4). A publisher calling `PUT /visibility` to change the type or drop the owning department → `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`. |
| Q6 | Which owning department do existing `DEPARTMENTS` documents (before the migration) get? | The migration cannot infer intent when a document has several departments. The research corpus in the local DB is mostly `WORKSPACE` (not measured). | **Decided:** one department → that department; several → the current department of the first version's uploader (`document_versions.uploaded_by` → `memberships.department_id`) if it is in `document_departments`; otherwise the department with the smallest `lower(name)`. List the multi-department documents in the migration notes for the OWNER to check. |
| Q7 | Are PRD-V2 FR-06, FR-25 and §8 item 9 updated in the same approval as this ADR, or in V2-36? | Three places say "only OWNER/ADMIN upload, edit, delete". | **Decided: update after this ADR has no open questions and is approved**, before V2-36 starts. |
