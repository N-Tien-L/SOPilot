---
id: TECH-V2-DOCUMENT-ACCESS-SYNC
title: "Technical design: document access sync through the outbox (core-api -> ai-service)"
status: approved
created: 2026-11-09
updated: 2026-11-13
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/architecture/components/core-api.md
  - docs/architecture/components/ai-service.md
author: "Owner"
affected_services: [core-api, ai-service]
affected_schemas: [core, rag]
---

# TECHNICAL DESIGN: DOCUMENT ACCESS SYNC

> **Document id:** `TECH-V2-DOCUMENT-ACCESS-SYNC` | **Status:** `approved` (approved 2026-11-10, checked against the code after V2-12/V2-23)
> **References:** [ADR-004](../decisions/adr-004-two-service-architecture.md), [ADR-007](../decisions/adr-007-departments-member-profiles-document-access.md), [TECH-V2-core-api](../components/core-api.md) §2.3, §5.6, §7, §8, [TECH-V2-ai-service](../components/ai-service.md) §3.1, §6.1, §8
>
> Translated from Vietnamese on 2026-11-13; section numbers and the numbered items of §7 are stable (tickets cite §7.1).

This document collects in one readable place the access-sync flow that is spread over the two service designs. On any conflict, the contract in TECH-V2-core-api §8 and the code are authoritative.

---

## 1. Overview and system boundaries

SOPilot V2 runs as two independent services:
1. **`core-api`**: the **single source of truth** for documents, users, departments, permissions and versions. Owns schema `core`.
2. **`ai-service`**: extracts text, embeds, stores chunks and runs semantic search (RAG). Owns schema `rag` and **never accesses schema `core`** (ADR-004 §4.3).

So that RAG retrieves correctly by permission (RBAC / department filtering) without calling back to `core-api` in real time during inference, `ai-service` keeps a copy of the access state: **`rag.document_access`** (one row per document).

### Sync boundaries:
- Every change to a document's access scope or existence in `core-api` is synchronized to `ai-service` through the **Transactional Outbox Pattern** over internal HTTP.
- **Overwrites with an ordering check (`access_revision`)** keep the copy eventually consistent and safe against out-of-order delivery.
- Every internal request carries `X-Internal-Token` and `Idempotency-Key = outbox_events.id`; ai-service ignores keys it has already processed.

| Component | Schema owned | Role in the flow |
|---|---|---|
| `core-api` (`DocumentService`, `OutboxService`) | `core` | Stores document changes and writes the event to `core.outbox_events` in the same transaction. |
| `OutboxDispatcher` (inside `core-api`) | `core` | Three send paths: `ACCESS_UPDATED` is sent directly on the request thread right after commit (`sendDirect`, 2 s timeout); other events are pushed after commit (`@TransactionalEventListener(phase = AFTER_COMMIT)` on the `outbox-wake` thread); a periodic scan every `sopilot.outbox.poll` (default `PT5S`) through `core.claim_outbox_batch(20)` for every due event. Sent with `HttpAiServiceClient`. |
| `ai-service` | `rag` | Receives `POST /internal/ingestions`, `PUT /internal/document-access/{id}`, `DELETE /internal/documents/{id}`; writes `rag.document_access`. |

---

## 2. Sequence diagram

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrator (OWNER/ADMIN)
    participant CoreAPI as core-api
    participant CoreDB as Postgres (schema core)
    participant Worker as OutboxDispatcher (core-api)
    participant AIService as ai-service
    participant AIDB as Postgres (schema rag)

    %% Scenario 1: access update
    rect rgb(240, 248, 255)
    Note over Admin,AIDB: Scenario 1: change visibility (PUT /api/v1/documents/{id}/visibility)
    Admin->>CoreAPI: Update the document's scope (e.g. restrict to departments)
    activate CoreAPI
    CoreAPI->>CoreDB: 1 transaction:<br/>1. UPDATE core.documents (visibility, access_revision + 1)<br/>2. Rewrite core.document_departments<br/>3. UPDATE the access payload of still-PENDING INGEST_REQUESTED events (§7.1)<br/>4. INSERT core.outbox_events (ACCESS_UPDATED, PENDING, 60 s lease)<br/>5. INSERT core.audit_logs
    CoreDB-->>CoreAPI: Commit
    CoreAPI->>AIService: sendDirect (request thread, 2 s timeout): PUT /internal/document-access/{documentId}<br/>X-Internal-Token, Idempotency-Key = event id<br/>{ workspaceId, visibility, departmentIds, accessRevision }
    activate AIService
    AIService->>AIDB: UPDATE rag.document_access ... WHERE access_revision < :rev AND deleted_at IS NULL
    AIService-->>CoreAPI: 200 { "applied": true | false }
    deactivate AIService
    CoreAPI->>CoreDB: UPDATE core.outbox_events SET status = 'DELIVERED', delivered_at = now()
    CoreAPI-->>Admin: 200 { accessSync: APPLIED } (error or timeout: markRetry, returns PENDING)
    deactivate CoreAPI
    Note over Worker,AIService: If the direct send fails, the Worker resends at next_attempt_at (or when the lease expires).<br/>Network/5xx/408/429: backoff 2^attempts s (capped at 10 minutes, jitter), at most SOPILOT_OUTBOX_MAX_ATTEMPTS, then DEAD.<br/>Other 4xx: DEAD immediately (contract error).
    end

    %% Scenario 2: deleting a document
    rect rgb(255, 245, 245)
    Note over Admin,AIDB: Scenario 2: delete a document (DELETE /api/v1/documents/{id})
    Admin->>CoreAPI: Click delete
    activate CoreAPI
    CoreAPI->>CoreDB: 1 transaction:<br/>1. UPDATE core.documents SET deleted_at = now()<br/>2. INSERT core.outbox_events (DOCUMENT_DELETED, PENDING)<br/>3. INSERT core.audit_logs
    CoreDB-->>CoreAPI: Commit
    CoreAPI-->>Admin: 200 OK
    deactivate CoreAPI

    Worker->>AIService: DELETE /internal/documents/{documentId}?workspaceId={workspaceId}<br/>Idempotency-Key = event id
    activate AIService
    AIService->>AIDB: 1 transaction:<br/>1. SET deleted_at = now() on document_access<br/>2. DELETE ingestion_jobs, chunks (chunk_terms cascade), extracted_documents, suggestion_jobs<br/>3. DELETE the document_access row
    AIService-->>Worker: 200 { "deleted": true } (idempotent)
    deactivate AIService
    Worker->>CoreDB: status = 'DELIVERED'; hook hard-deletes core.documents and the S3 object
    end
```

> How `accessSync` is computed, per TECH-V2-core-api §2.3, as implemented by V2-24 (updated 2026-11-10): the `ACCESS_UPDATED` event is written with a 60 s lease (`next_attempt_at = now() + 60 s`, `OutboxService.enqueueLeased`) and emits no `Enqueued`, so `outbox-wake` and the scan do not send duplicates. After commit, `OutboxDispatcher.sendDirect` sends on the request thread with a 2 s timeout: 2xx → `DELIVERED`, returns `APPLIED`; a retryable error or timeout → `markRetry`, returns `PENDING`; another 4xx → `DEAD`, returns `PENDING`. The request is never blocked longer than 2 s.

Since ADR-009 (V2-36) the actor of scenario 1 is the document's publisher, or the OWNER through `PUT /documents/{id}/ownership` (TECH-V2-core-api §15); the sync flow is the same.

---

## 3. Data model

### 3.1 Table `rag.document_access` (in `ai-service`, migration `rag/V003`)
The table holds each document's current access, one row per document. Every chunk query goes through the `allowed` CTE built from this table (§6).

```sql
CREATE TABLE rag.document_access (
    workspace_id      uuid NOT NULL,
    document_id       uuid PRIMARY KEY,
    visibility        text NOT NULL CHECK (visibility IN ('WORKSPACE', 'DEPARTMENTS')),
    department_ids    uuid[] NOT NULL DEFAULT '{}',
    access_revision   bigint NOT NULL,
    active_version_id uuid,                 -- the version being retrieved (NULL = no READY version yet)
    title             text NOT NULL,        -- written on insert and on version activation
    deleted_at        timestamptz,          -- blocks retrieval immediately in the deleting transaction
    updated_at        timestamptz NOT NULL DEFAULT now(),  -- trigger trg_document_access_updated
    CHECK (visibility = 'WORKSPACE' OR cardinality(department_ids) >= 1)
);
CREATE INDEX ix_document_access_ws ON rag.document_access (workspace_id);
CREATE INDEX ix_document_access_depts ON rag.document_access USING gin (department_ids);
-- RLS: ENABLE + FORCE, policy tenant_isolation on rag.current_workspace().
```

The row is **created** by `POST /internal/ingestions` (upsert, applied only when `access_revision` is newer). `PUT /internal/document-access` **never creates** a row.

### 3.2 Table `core.outbox_events` (in `core-api`, migration `core/V005`)

```sql
CREATE TABLE core.outbox_events (
    id              uuid PRIMARY KEY,               -- also the Idempotency-Key sent to ai-service
    workspace_id    uuid NOT NULL,
    aggregate_id    uuid NOT NULL,                  -- document id
    event_type      text NOT NULL CHECK (event_type IN ('INGEST_REQUESTED','ACCESS_UPDATED','DOCUMENT_DELETED')),
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','DELIVERED','DEAD')),
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz
);
CREATE INDEX ix_outbox_due ON core.outbox_events(next_attempt_at) WHERE status = 'PENDING';
-- RLS by workspace_id; core.claim_outbox_batch(p_limit) (SECURITY DEFINER) takes due events
-- of every workspace with FOR UPDATE SKIP LOCKED and sets a 60 s lease through next_attempt_at.
```

There is no `PROCESSING` status: "being sent" is a 60 s lease on `next_attempt_at`, and the event stays `PENDING`.

---

## 4. Internal API contracts

Common headers for every endpoint below:

```http
Content-Type: application/json
X-Internal-Token: <SOPILOT_INTERNAL_TOKEN>
Idempotency-Key: <outbox_events.id (uuid)>
```

Missing/wrong token → `401`. Missing `Idempotency-Key` or an invalid body → `422` (core-api treats it as a contract error, `DEAD` immediately).

### 4.1 Updating access scope: `PUT /internal/document-access/{documentId}`
Sent for `ACCESS_UPDATED` events.

- **Properties:** idempotent, does not touch chunks (FR-26: changing scope does not re-embed).
- **Request body:**
  ```json
  {
    "workspaceId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "visibility": "DEPARTMENTS",
    "departmentIds": [
      "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22"
    ],
    "accessRevision": 4
  }
  ```
- **Handling in `ai-service`** (`db/repositories/access.py::update_access`, inside `tenant_tx`):
  ```sql
  UPDATE rag.document_access
     SET visibility = :visibility,
         department_ids = CAST(:depts AS uuid[]),
         access_revision = :rev
   WHERE workspace_id = :wid AND document_id = :doc
     AND deleted_at IS NULL
     AND access_revision < :rev
  RETURNING document_id;
  ```
- **Response:** always `200 {"applied": true | false}`. `false` when: `accessRevision` is not newer, the idempotency key was already seen, the document is deleted, **or ai-service has no row yet** (ingest has not arrived). core-api treats every `200` as `DELIVERED`.

### 4.2 Deleting a document: `DELETE /internal/documents/{documentId}?workspaceId=...`
Sent for `DOCUMENT_DELETED` events.

- **Properties:** idempotent; repeats still return `200`.
- **Handling in `ai-service`** (`access.delete_document`, one transaction):
  1. `UPDATE rag.document_access SET deleted_at = now()` (concurrent retrieval sees the document as gone).
  2. `DELETE` the document's rows in `rag.ingestion_jobs` (this is how the job is "cancelled"), `rag.chunks` (`chunk_terms` cascade), `rag.extracted_documents`, `rag.suggestion_jobs`.
  3. `DELETE` the `rag.document_access` row.
  `rag.message_citations` are kept so conversation history shows `DOCUMENT_DELETED`.
- **Response:** `200 {"deleted": true}`.

---

## 5. Walkthrough examples

Assume the document **"Quy trình thanh toán công tác phí"** (travel-expense payment procedure) has `documentId = "doc-8888"` (ids shortened for readability; in reality they are UUIDs).

### Example 1: an admin creates a document and ingests the first version
1. `core-api` writes an `INGEST_REQUESTED` outbox event; the dispatcher sends `POST /internal/ingestions` with `access = {visibility: "WORKSPACE", departmentIds: [], accessRevision: 1}` and `title`.
2. `ai-service` upserts the first row into `rag.document_access`:
   ```json
   {
     "workspace_id": "ws-1111",
     "document_id": "doc-8888",
     "visibility": "WORKSPACE",
     "department_ids": [],
     "access_revision": 1,
     "active_version_id": null,
     "title": "Quy trình thanh toán công tác phí",
     "deleted_at": null
   }
   ```
3. When the ingestion job finishes, the `ai-service` worker activates the version: `active_version_id = "ver-0001"`. The document starts serving RAG.

### Example 2: an admin restricts the scope to Accounting and HR
1. **The admin** selects `dept-acc` and `dept-hr`.
2. **`core-api`** sets `access_revision = 2`, rewrites `document_departments`, and writes the outbox event and audit in one transaction:
   ```json
   {
     "aggregateId": "doc-8888",
     "eventType": "ACCESS_UPDATED",
     "payload": {
       "workspaceId": "ws-1111",
       "visibility": "DEPARTMENTS",
       "departmentIds": ["dept-acc", "dept-hr"],
       "accessRevision": 2
     }
   }
   ```
3. **The dispatcher** sends `PUT /internal/document-access/doc-8888` right after commit.
4. **`ai-service`** overwrites: `visibility = DEPARTMENTS`, `department_ids = {dept-acc, dept-hr}`, `access_revision = 2`; `active_version_id` and `title` stay.

### Example 3: out-of-order delivery
1. The admin changes `DEPARTMENTS` → `WORKSPACE` (`accessRevision = 3`).
2. A few seconds later, back to only `dept-board` (`accessRevision = 4`).
3. The rev 3 event fails transiently and waits for backoff; rev 4 arrives first → the row becomes `access_revision = 4`.
4. Rev 3 arrives later: `WHERE access_revision < 3` does not match → `200 {"applied": false}`, and the row keeps the rev 4 state.

### Example 4: deleting a document
1. The admin deletes `doc-8888`; `core-api` sets `deleted_at` and writes `DOCUMENT_DELETED`.
2. The dispatcher sends `DELETE /internal/documents/doc-8888?workspaceId=ws-1111`.
3. `ai-service` sets `deleted_at`, deletes jobs/chunks/extraction/suggestion jobs, then deletes the access row, all in one transaction, and returns `200 {"deleted": true}`.
4. core-api records `DELIVERED`, then hard-deletes the document and the S3 object.

---

## 6. RAG retrieval isolation

ai-service verifies core-api's RS256 access token itself through `/.well-known/jwks.json` and takes `wid`, `wrole`, `wdept` (one department or `NULL`) from the token, never from the request. Every retrieval path (vector, BM25, section expansion, rereading citations) uses a single predicate in `retrieval/access_filter.py`:

```sql
WITH allowed AS (
    SELECT da.document_id, da.active_version_id, da.title
      FROM rag.document_access da
     WHERE da.workspace_id = :wid
       AND da.deleted_at IS NULL
       AND da.active_version_id IS NOT NULL
       AND ( CAST(:wrole AS text) IN ('OWNER', 'ADMIN')
             OR da.visibility = 'WORKSPACE'
             OR (CAST(:wdept AS uuid) IS NOT NULL
                 AND CAST(:wdept AS uuid) = ANY (da.department_ids)) )
)
SELECT c.id, c.document_id, c.version_id, c.section_path, c.content, a.title
  FROM rag.chunks c
  JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
 WHERE c.workspace_id = :wid
 ORDER BY c.embedding <=> :query_embedding
 LIMIT :k;
```

> **Fail closed:** a document without a `document_access` row, deleted, or without an activated version is not in `allowed`, so none of its chunks are returned. `workspace_id = :wid` is repeated next to RLS (two layers, ADR-005).

core-api uses the equivalent predicate on `core.documents` + `core.document_departments` for lists, detail and download URLs (TECH-V2-core-api §5.6); documents outside access return `404`.

---

## 7. Known risks and constraints for V2-24

1. **The ingest–access race (handled in V2-24, `OutboxRepository.updatePendingIngestAccess`).** The `INGEST_REQUESTED` payload snapshots `access` at enqueue time. If the ingest is still `PENDING` (in backoff because ai-service failed) when the admin changes the scope, `ACCESS_UPDATED` (the new rev) may arrive first, get `applied: false` because there is no row yet, and be marked `DELIVERED`. The later ingest would then create the row with the **old rev and old scope**, and nothing would fix it: a document narrowed to departments could be retrieved workspace-wide. The proposed fix (only in `core`): in the same transaction that changes the scope, update `payload->'access'` of the document's still-`PENDING` `INGEST_REQUESTED` events to the new scope and revision. An integration test for this scenario is mandatory. **Still open:** `sendDirect` runs on the request thread, outside `synchronized dispatchDue`. If the dispatcher has already claimed and is sending `INGEST_REQUESTED` (the old payload already in memory) at the moment the admin changes the scope, `ACCESS_UPDATED` may arrive first, get `applied: false` because there is no row yet, and be marked `DELIVERED`; the later ingest creates the row with the old scope. The window is only as long as one in-flight ingest request; closing it needs its own ticket.
2. **The title in `rag.document_access`** is updated only on insert and on version activation. Editing the title through `PATCH /api/v1/documents/{id}` does not call ai-service (TECH-V2-core-api §5.6), so citations show the old title until the next activation. Accepted for the MVP; recorded in the V2-24 report.
3. **The user's department lag:** `wdept` comes from the token (≤ 15 minutes); a department change takes effect at the next refresh (ADR-007).

---

## 8. Test strategy

1. **Unit (core-api):** a scope change writes `documents`, `document_departments`, the `ACCESS_UPDATED` outbox event and the audit in one transaction (on error both roll back); an empty `DEPARTMENTS` or a department from another workspace is rejected.
2. **Unit/integration (ai-service, existing):** `PUT /internal/document-access` returns `applied: false` when `accessRevision` ≤ the current one, on a repeated key, and when no row exists.
3. **Integration (core-api, Testcontainers + an ai-service mock):** the dispatcher sends the right path/header/body; ai-service errors → the outbox retries and then reaches `DELIVERED`; 4xx → `DEAD`; resending the same payload 3 times does not change state; the §7.1 race ends with the latest `access`.
4. **Security (FR-29, V2-26):** a document for `dept-finance`; a `dept-marketing` MEMBER does not see it in the list/detail/download URL (`404`) and gets no chunks or citations from it; OWNER/ADMIN still see it.
