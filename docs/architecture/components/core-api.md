---
id: TECH-V2-CORE-API
title: "core-api technical design (V2): identity, workspaces, members, documents, outbox"
status: approved
created: 2026-10-20
updated: 2026-11-13
refs:
  - docs/architecture/decisions/adr-009-department-publishers.md
  - docs/research/audit-markdown-normalization-and-preview-2026-10-21.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/research/audit-v2-baseline-analysis-2026-10-17.md
  - docs/architecture/components/ai-service.md
author: "Owner"
affected_services: [core-api, ai-service, frontend/web]
affected_schemas: [core]
---

# TECHNICAL DESIGN: core-api (V2)

> **Document id:** `TECH-V2-CORE-API` | **PRD:** `PRD-V2-SOPILOT-MVP` | **Status:** `approved` (owner approval 2026-10-20, V2-03; open questions settled in §11)
>
> This document pairs with [TECH-V2-ai-service](ai-service.md). The contract between the two services (§8) is the shared source; TECH-V2-ai-service only refers to it and does not redefine it.
>
> **Changed 2026-10-21 (owner, [AUDIT-markdown-normalization](../../research/audit-markdown-normalization-and-preview-2026-10-21.md)):** TXT dropped (§3.3, §5.5); the replacement rule while a version is processing (§3.3, §11 Q7); the document quota defaults to 50/200 MB (§3.3, §9, §11 Q6); `attempt` in the ingest payload and callback so retries really rerun (§5.5, §8); `warningCodes` and `latestVersion` for the FR-31 view (§5.5, §8.2).
>
> **Owner approval 2026-11-10 ([ADR-009](../decisions/adr-009-department-publishers.md), `approved`):** document write rights move to department publishers and a workspace publisher; the OWNER revokes and transfers responsibility; DDL, API and the check point are in §15. Implemented by V2-36 (`done`).
>
> **Implementation status (ticket files, 2026-11-13):** the tickets implementing this design are V2-11, V2-12, V2-23, V2-24, V2-29, V2-30, V2-36 (`done`) and V2-25 (`review`); §13, §14, §16 and §17 record where the code deviates (the §16/§17 headings still say "pending owner approval" as written; V2-30 and V2-36 have since been accepted). Where code and this document disagree, the code wins; the endpoint table in `services/core-api/README.md` lists what is actually served. Translated from Vietnamese on 2026-11-13 without design changes; **section numbers are stable** (code and migrations cite them).

---

## 0. Scope and conventions

- core-api is a Spring Boot 3.x, Java 21 (PRD §8.1) service, written from scratch in `services/core-api`. The old code (`auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`) is only a reference to port from selectively (ADR-004 §4.5).
- core-api is the sole owner of schema `core` and the only service that writes `core.users` (fix A7).
- Every business table has `workspace_id` and enables RLS (ADR-005, ADR-007). The global tables (`users`, `external_identities`) have no `workspace_id` and no RLS.
- There is no gateway, RabbitMQ or Redis (ADR-004). Asynchronous work goes through a Postgres outbox.
- Terms: **wid** = the active workspace in the token; **wrole** = the role in that workspace; **wdept** = the membership's department, or empty.

### Traceability to requirements

| Requirement | Section |
|---|---|
| FR-01, FR-02, A8, A9 | §3.1, §5.1 |
| FR-03 | §5.2 |
| FR-04, FR-22, UC-02, UC-07 | §3.2, §5.3 |
| FR-05 (P1) | §3.2, §5.3 |
| FR-23, UC-08 | §5.4 |
| FR-24 (P1) | §5.3 |
| FR-06, FR-07, UC-04 | §3.3, §5.5, §7 |
| FR-25, FR-26, FR-27, UC-09, UC-10, UC-11 | §3.4, §5.6, §8 |
| FR-28 (storing and applying suggestions) | §5.6, §8.3 |
| FR-09 (document quota, default 50 documents/200 MB since 2026-10-21) | §3.3, §9 |
| FR-30 (multi-file selection) | §5.5 |
| FR-31 (recognized-content view: version label, warning codes) | §3.3, §5.5, §8.2 |
| FR-20 | §3.6, §5.7 |
| FR-16, FR-17 | TECH-V2-ai-service §7.6 (§11 Q1) |
| Tenant-isolation NFR, FR-19, FR-29 | §4, §10 |

---

## 1. Architecture overview and affected components

| Component | Technology | Boundary | Nature of the change |
|---|---|---|---|
| `services/core-api` | Spring Boot 3.x, Java 21, Spring Data JPA + JdbcTemplate, Flyway client | Schema `core`, object storage | New service |
| `infrastructure/db/migrations/core/` | Flyway, PostgreSQL 16 | Schema `core` | New migration chain (V2-08) |
| Object storage | Pinned MinIO version (local, CI) | One bucket, name from env | Used through the standard S3 API |
| `services/ai-service` | FastAPI | Schema `rag` | Receives ingest jobs and access updates, calls back with status (§8) |
| `frontend/web` | Next.js | — | Calls `/api/**` (core-api) and `/ai/**` (ai-service) on the same origin |

> **Implementation note (2026-11-13):** core-api uses `JdbcTemplate` with hand-written SQL only; there is no JPA/Hibernate (see `.claude/rules/core-api.md`, enforced by `ArchitectureTest`). The "Spring Data JPA" entry above is the original design and was not adopted.

### 1.1 One origin for the browser

The V2 environment runs only locally with `docker compose` (PRD §8.2). Next.js `rewrites` route:

| Browser path | Target |
|---|---|
| `/api/**`, `/.well-known/jwks.json` | `core-api:8080` |
| `/ai/**` | `ai-service:8000` |

Consequence: no CORS needed; the refresh cookie uses `SameSite=Strict`. Known risk: the Next.js proxy may buffer SSE. V2-15 must check that the stream passes through the rewrites token by token; if it is buffered, add a Caddy container as reverse proxy (the API contract does not change).

`/internal/**` of both services is **not** rewritten to the outside. The two services call each other by container name on the compose network.

### 1.2 Module structure (modular monolith)

```
services/core-api/src/main/java/com/sopilot/core/
├── common/        # error envelope, TraceIdFilter, clock, ids
├── security/      # JwtIssuer (RS256), JwksController, JwtAuthFilter, InternalTokenFilter
├── tenancy/       # TenantContext, TenantTransactionListener (SET LOCAL), RLS helpers
├── identity/      # GoogleTokenVerifier, NonceService, AuthController, RefreshTokenService, DevLoginController
├── workspace/     # Workspace, WorkspaceService, WorkspaceController, domains (P1)
├── member/        # Membership, Invitation, MemberService, InvitationService, CSV import (P1)
├── department/    # Department, DepartmentService
├── document/      # Document, DocumentVersion, upload, download, visibility, StorageClient
├── metadata/      # Category, Tag, field sources, suggestions
├── outbox/        # OutboxEvent, OutboxDispatcher, AiServiceClient
└── audit/         # AuditLog, AuditService
```

The new Java package is `com.sopilot.core`. New code does not reuse `com.poliwise.*`; the old code keeps its package names until it is removed (V2-17).

---

## 2. Sequence diagrams

### 2.1 First Google sign-in (UC-01, FR-01, FR-02)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (Next.js)
    participant G as Google Identity Services
    participant C as core-api
    participant DB as Postgres (core)

    B->>C: POST /api/v1/auth/google/nonce
    C-->>B: 200 {nonce} + Set-Cookie sp_nonce=<HMAC(nonce, exp)> (HttpOnly, 5 minutes)
    B->>G: Show the Sign in with Google button (nonce)
    G-->>B: ID token (JWT RS256)
    B->>C: POST /api/v1/auth/google {idToken} + cookie sp_nonce
    C->>C: Verify the Google JWKS signature, iss, aud, exp, email_verified, nonce matches the cookie
    C->>DB: BEGIN; find external_identities by (issuer, sub)
    alt No user yet
        C->>DB: INSERT users, external_identities (ON CONFLICT DO NOTHING, then re-read)
        C->>DB: INSERT workspaces(kind=PERSONAL), memberships(OWNER, ACTIVE)
    end
    C->>DB: Apply the link invitation (if invitationToken) / domain join (P1)
    C->>DB: Choose the workspace: just-accepted invitation > last_active_workspace_id > PERSONAL
    C->>DB: INSERT refresh_tokens (hash, family_id, workspace_id); INSERT audit_logs(LOGIN); COMMIT
    C-->>B: 200 {accessToken, expiresIn, workspace} + Set-Cookie sp_refresh (HttpOnly, Secure, SameSite=Strict, Path=/api/v1/auth)
```

### 2.2 Upload to `READY` (UC-04, FR-06, FR-07, FR-08)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant C as core-api
    participant S3 as Object storage
    participant DB as Postgres (core)
    participant A as ai-service

    B->>C: POST /api/v1/documents (multipart, Bearer wid/wrole)
    C->>C: Check wrole ∈ {OWNER, ADMIN}, file type, ≤ 20 MB, compute SHA-256 while streaming
    C->>S3: PUT workspaces/{wid}/documents/{docId}/versions/{verId}
    C->>DB: BEGIN; SET LOCAL app.workspace_id; advisory lock (wid, sha256)
    C->>DB: Check SHA-256 duplicates against other documents; per-workspace advisory lock and document quota check (default 50/200 MB)
    C->>DB: INSERT documents, document_versions(UPLOADED), outbox(INGEST_REQUESTED), audit_logs; COMMIT
    C-->>B: 201 {document, version.status=UPLOADED}
    C->>A: (after commit, outbox) POST /internal/ingestions
    A-->>C: 202 (writes rag.document_access + rag.ingestion_jobs in one transaction)
    A->>C: PATCH /internal/documents/{id}/versions/{verId}/status {PROCESSING}
    A->>C: PATCH ... {READY, pageCount, language, extracted, warningCodes}
    C->>DB: version READY, documents.current_version_id = verId, old version SUPERSEDED
```

The "wrole ∈ {OWNER, ADMIN}" check in step 2 is the original design; since ADR-009 the write check is the publisher rule of §15.3.

If deleting the S3 object fails after the transaction rolls back, the orphan object is cleaned up by the `StorageJanitor` job (compares object keys with `document_versions`, runs hourly). A DB row never points to an unfinished object, because the S3 PUT happens before the commit.

### 2.3 Changing visibility (UC-11, FR-25)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant C as core-api
    participant DB as Postgres (core)
    participant A as ai-service

    B->>C: PUT /api/v1/documents/{id}/visibility {visibility: DEPARTMENTS, departmentIds}
    C->>DB: BEGIN; update documents.visibility, document_departments; outbox(ACCESS_UPDATED, access_revision+1); audit; COMMIT
    C->>A: PUT /internal/document-access/{id} (synchronous call right after commit, 2 s timeout)
    alt ai-service accepts
        A-->>C: 200 (applied only if access_revision is newer than the stored one)
        C->>DB: outbox DELIVERED
        C-->>B: 200 {accessSync: "APPLIED"}
    else Error or timeout
        C-->>B: 200 {accessSync: "PENDING"}
        Note over C,A: OutboxDispatcher retries with backoff until ai-service accepts
    end
```

---

## 3. Data design (schema `core`)

- **Migrations:** `infrastructure/db/migrations/core/V0xx__*.sql`, Flyway with its own history table `core.flyway_schema_history` (ADR-004 §4.4). The Flyway setup, roles and compose belong to V2-08.
- **Common types:** `uuid` primary keys generated by the application (UUIDv7 for time-ordered inserts); `timestamptz` timestamps; emails stored as `citext` or lowercase + `CHECK (email = lower(email))`. Use `text` instead of `varchar(n)` unless the limit has business meaning.
- **Foreign keys:** only within schema `core`. No FKs to `rag`.
- Every table has `updated_at`, maintained by the shared trigger `core.touch_updated_at()`.
- The DDL below is grouped by topic, not by execution order. The migration must create `core.categories` before `core.documents` (FK `category_id`).

### 3.1 Identity (global, no RLS)

```sql
CREATE TABLE core.users (
    id                       uuid PRIMARY KEY,
    email                    text NOT NULL CHECK (email = lower(email)),
    display_name             text,
    avatar_url               text,
    last_active_workspace_id uuid,            -- no FK, to avoid a dependency cycle when deleting a workspace
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
-- email is not unique: identity is (issuer, subject); email is only an attribute (ADR-005 §4.1).

CREATE TABLE core.external_identities (          -- ported from init-db/012_google_identities.sql
    id            uuid PRIMARY KEY,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    issuer        text NOT NULL CHECK (length(trim(issuer)) > 0),
    subject       text NOT NULL CHECK (length(trim(subject)) > 0),
    email_at_link text NOT NULL,
    hosted_domain text,                           -- hd claim at the most recent link
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_external_identity_user UNIQUE (user_id, issuer)
);

CREATE TABLE core.refresh_tokens (
    id             uuid PRIMARY KEY,
    user_id        uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    workspace_id   uuid NOT NULL,                 -- workspace of the access token to be issued
    family_id      uuid NOT NULL,                 -- rotation chain; reusing an old token revokes the whole chain
    token_hash     bytea NOT NULL UNIQUE,         -- SHA-256 of a 256-bit random token
    expires_at     timestamptz NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    used_at        timestamptz,                   -- exchanged for a new token
    revoked_at     timestamptz,
    revoked_reason text CHECK (revoked_reason IN ('LOGOUT','REUSE_DETECTED','MEMBERSHIP_LOST','SUSPENDED','EXPIRED_FAMILY'))
);
CREATE INDEX ix_refresh_tokens_family ON core.refresh_tokens(family_id);
```

`refresh_tokens.workspace_id` does not enable RLS: the table is only read by `token_hash` in the refresh flow, before the workspace is known. There are no device/IP columns (session management is out of scope, PRD §5).

### 3.2 Workspaces, members, invitations, departments

```sql
CREATE TABLE core.workspaces (
    id         uuid PRIMARY KEY,
    name       text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    kind       text NOT NULL CHECK (kind IN ('PERSONAL','TEAM')),
    created_by uuid NOT NULL REFERENCES core.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- Exactly one PERSONAL workspace per user (FR-02, idempotent).
CREATE UNIQUE INDEX uq_personal_workspace ON core.workspaces(created_by) WHERE kind = 'PERSONAL';

CREATE TABLE core.departments (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)                     -- for two-column FKs: the department must be in the same workspace
);
CREATE UNIQUE INDEX uq_department_name ON core.departments(workspace_id, lower(name));

CREATE TABLE core.memberships (
    workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    role          text NOT NULL CHECK (role IN ('OWNER','ADMIN','MEMBER')),
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED')),
    display_name  text,
    email         text NOT NULL CHECK (email = lower(email)),  -- email at join time, shown in lists
    employee_code text,
    job_title     text,
    department_id uuid,
    suspended_at  timestamptz,
    joined_at     timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id),
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT,
    CHECK ((status = 'SUSPENDED') = (suspended_at IS NOT NULL))
);
CREATE UNIQUE INDEX uq_membership_employee_code ON core.memberships(workspace_id, employee_code) WHERE employee_code IS NOT NULL;
CREATE INDEX ix_memberships_user ON core.memberships(user_id);

CREATE TABLE core.invitations (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    email         text NOT NULL CHECK (email = lower(email)),
    role          text NOT NULL CHECK (role IN ('ADMIN','MEMBER')),   -- nobody is invited directly as OWNER
    display_name  text,
    employee_code text,
    job_title     text,
    department_id uuid,
    token_hash    bytea NOT NULL UNIQUE,
    invited_by    uuid NOT NULL REFERENCES core.users(id),
    expires_at    timestamptz NOT NULL,                               -- created_at + 7 days
    accepted_at   timestamptz,
    accepted_by   uuid REFERENCES core.users(id),
    revoked_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT
);
-- One pending invitation per email in a workspace.
CREATE UNIQUE INDEX uq_pending_invitation ON core.invitations(workspace_id, email)
    WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE core.workspace_domains (            -- P1, FR-05
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    domain       text NOT NULL CHECK (domain = lower(domain)),
    enabled_by   uuid NOT NULL REFERENCES core.users(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, domain)
);
CREATE INDEX ix_workspace_domains_domain ON core.workspace_domains(domain);
```

Rules that cannot be expressed as constraints (checked in the service, in a transaction with `SELECT ... FOR UPDATE` on the workspace's OWNER memberships):
- At least one `OWNER` with `status = 'ACTIVE'` always remains.
- An ADMIN does not change the role of, suspend or remove an OWNER, and does not promote anyone to OWNER.
- No new assignments to an `ARCHIVED` department (memberships, invitations).
- A `PERSONAL` workspace never changes `kind` and cannot be deleted while it is the user's only workspace.

### 3.3 Documents and versions

```sql
CREATE TABLE core.documents (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    title              text NOT NULL,
    title_source       text NOT NULL DEFAULT 'SYSTEM' CHECK (title_source IN ('SYSTEM','SUGGESTED','USER')),
    description        text,
    description_source text NOT NULL DEFAULT 'SYSTEM' CHECK (description_source IN ('SYSTEM','SUGGESTED','USER')),
    category_id        uuid,
    category_source    text NOT NULL DEFAULT 'SYSTEM' CHECK (category_source IN ('SYSTEM','SUGGESTED','USER')),
    tags_source        text NOT NULL DEFAULT 'SYSTEM' CHECK (tags_source IN ('SYSTEM','SUGGESTED','USER')),
    language           text,                                   -- short BCP-47: 'vi', 'en'
    language_source    text NOT NULL DEFAULT 'SYSTEM' CHECK (language_source IN ('SYSTEM','SUGGESTED','USER')),
    visibility         text NOT NULL DEFAULT 'WORKSPACE' CHECK (visibility IN ('WORKSPACE','DEPARTMENTS')),
    access_revision    bigint NOT NULL DEFAULT 1,              -- incremented on every visibility change; ai-service ignores older ones
    current_version_id uuid,                                   -- the READY version used for Q&A
    latest_version_id  uuid,                                   -- the newest version (may still be processing)
    created_by         uuid NOT NULL REFERENCES core.users(id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    deleted_at         timestamptz,                            -- soft delete while waiting for ai-service to delete chunks
    UNIQUE (workspace_id, id),
    FOREIGN KEY (workspace_id, category_id) REFERENCES core.categories(workspace_id, id) ON DELETE SET NULL (category_id)
);

CREATE TABLE core.document_versions (
    id               uuid PRIMARY KEY,
    workspace_id     uuid NOT NULL,
    document_id      uuid NOT NULL,
    version_no       int  NOT NULL,
    status           text NOT NULL CHECK (status IN ('UPLOADED','PROCESSING','READY','FAILED','SUPERSEDED')),
    failure_code     text,                                     -- NO_TEXT_LAYER, UNSUPPORTED_TYPE, EMPTY_CONTENT, EXTRACTION_ERROR, ...
    failure_message  text,                                     -- message shown to the user, never a stack trace
    original_name    text NOT NULL,
    mime_type        text NOT NULL,
    file_type        text NOT NULL CHECK (file_type IN ('PDF','MD')),   -- TXT dropped from the MVP on 2026-10-21
    size_bytes       bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 20971520),
    sha256           bytea NOT NULL,
    object_key       text NOT NULL UNIQUE,
    page_count       int,
    detected_language text,
    doc_code         text,                                     -- document code extracted from content (V2-21)
    revision_label   text,                                     -- issue number
    effective_date   date,
    embedding_model  text,                                     -- embedding provenance reported by ai-service
    embedding_revision text,
    chunk_count      int,
    warning_codes    text[] NOT NULL DEFAULT '{}',              -- extraction warning codes reported by ai-service (TECH-V2-ai-service §5.3a)
    attempt          int NOT NULL DEFAULT 0,                    -- incremented on each retry; sent in the ingest payload so ai-service can tell a retry from a duplicate send
    uploaded_by      uuid NOT NULL REFERENCES core.users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    processed_at     timestamptz,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_no),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_document_versions_sha ON core.document_versions(workspace_id, sha256);
```

Notes:
- **Duplicate blocking (FR-06, V2-12):** SHA-256 is compared only with **the current versions of other documents** (`document_id <> :id`, `status <> 'SUPERSEDED'`, document not deleted). No unique index, because older `SUPERSEDED` versions of the same document may coincide. Races are prevented with `pg_advisory_xact_lock(hashtextextended(wid || sha256_hex, 0))`. A duplicate returns `409 DUPLICATE_DOCUMENT` with `{documentId, title}` of the existing document (only when the caller can read that document; OWNER/ADMIN always can).
- **Replacement rules (FR-07, owner decisions 2026-10-20 and 2026-10-21),** evaluated in order within the same transaction and the document's advisory lock, `POST /documents/{id}/versions`:
  1. `latest_version_id` is `UPLOADED`/`PROCESSING` with the same SHA-256 → `200` returning that version (a repeated send of the same operation; no version, outbox or job is created).
  2. `latest_version_id` is `UPLOADED`/`PROCESSING` with a different SHA-256 → `409 VERSION_IN_PROGRESS`. Reason: two versions processed in parallel could activate in the wrong order (an older one becoming `READY` after a newer one).
  3. Same SHA-256 as `current_version_id` (`READY`) → `409 DOCUMENT_UNCHANGED`; no S3 write, no version, outbox or job.
  4. Same SHA-256 as the current version of **another document** → `409 DUPLICATE_DOCUMENT`, as when creating a document.
  5. Otherwise → create a new version. No comparison with `FAILED` versions: re-uploading the exact file of a failed version creates a new version, equivalent to a retry. A file with different bytes is always accepted even if its content is nearly the same; no Markdown hash or semantic comparison is used.
- **Replacing with a new version (FR-07):** `current_version_id` changes only when the new version is `READY`; then **every** older version of the document (including `FAILED`) becomes `SUPERSEDED`, and ai-service has deleted the previous version's chunks in the same activation transaction (TECH-V2-ai-service §5.6). If the new version is `FAILED`, the old one keeps serving.
- **Displayed document status** = the status of `latest_version_id`; a document is "queryable" when `current_version_id IS NOT NULL`.
- **Quotas (FR-09, owner decision 2026-10-21: on by default):** `SOPILOT_QUOTA_DOCS_PER_WORKSPACE=50`, `SOPILOT_QUOTA_BYTES_PER_WORKSPACE=209715200` (`0` = unlimited, the counting step is skipped; set `0` for eval or a large demo). Non-deleted documents and the total `size_bytes` of non-`SUPERSEDED` versions are counted in the same transaction under a per-workspace `pg_advisory_xact_lock`, so N concurrent uploads cannot exceed the quota. Exceeding it returns `409 QUOTA_EXCEEDED` with `{limit, used}`; the S3 object already written is deleted immediately (on failure, `StorageJanitor` cleans it up). A replacement version does not increase the document count; its size is counted together with the current version until the old one is `SUPERSEDED`. Raising the quota does not mean the system can handle a large corpus (not measured).
- **Object key:** `workspaces/{wid}/documents/{docId}/versions/{verId}`; the original file name is stored only in the DB.

### 3.4 Visibility, categories, tags (ADR-007, FR-25..27)

```sql
CREATE TABLE core.document_departments (
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    department_id uuid NOT NULL,
    PRIMARY KEY (document_id, department_id),
    FOREIGN KEY (workspace_id, document_id)   REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT
);

CREATE TABLE core.categories (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);
CREATE UNIQUE INDEX uq_category_name ON core.categories(workspace_id, lower(name));

CREATE TABLE core.tags (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 50),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);
CREATE UNIQUE INDEX uq_tag_name ON core.tags(workspace_id, lower(name));

CREATE TABLE core.document_tags (
    workspace_id uuid NOT NULL,
    document_id  uuid NOT NULL,
    tag_id       uuid NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, tag_id)      REFERENCES core.tags(workspace_id, id) ON DELETE CASCADE
);

-- Metadata suggestions (FR-28) are stored separately; they are applied only to fields whose source is not USER.
CREATE TABLE core.document_suggestions (
    workspace_id    uuid NOT NULL,
    document_id     uuid NOT NULL,
    version_id      uuid NOT NULL,
    payload         jsonb NOT NULL,     -- {title, description, categoryId | proposedCategoryName, tags[], language}
    method          text NOT NULL CHECK (method IN ('RULES','LLM','RULES_FALLBACK')),
    model           text,
    prompt_version  text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version_id),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE
);
```

The constraint "`DEPARTMENTS` must have ≥ 1 department" is checked in the service on write (same transaction) and by a `DEFERRABLE INITIALLY DEFERRED` constraint trigger at commit. An `ARCHIVED` category cannot be newly assigned; deleting a category moves its documents to "uncategorized" (`ON DELETE SET NULL (category_id)`, requires PostgreSQL ≥ 15) and does not affect access.

### 3.5 Outbox

```sql
CREATE TABLE core.outbox_events (
    id             uuid PRIMARY KEY,                -- also the idempotency key sent to ai-service
    workspace_id   uuid NOT NULL,
    aggregate_id   uuid NOT NULL,                   -- document_id
    event_type     text NOT NULL CHECK (event_type IN ('INGEST_REQUESTED','ACCESS_UPDATED','DOCUMENT_DELETED')),
    payload        jsonb NOT NULL,
    status         text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','DELIVERED','DEAD')),
    attempts       int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    delivered_at   timestamptz
);
CREATE INDEX ix_outbox_due ON core.outbox_events(next_attempt_at) WHERE status = 'PENDING';
```

### 3.6 Audit log (FR-20)

```sql
CREATE TABLE core.audit_logs (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    actor_id     uuid,                -- null when done by the system
    action       text NOT NULL,       -- LOGIN, MEMBER_INVITED, MEMBER_JOINED, MEMBER_ROLE_CHANGED, MEMBER_DEPARTMENT_CHANGED,
                                      -- MEMBER_SUSPENDED, MEMBER_REACTIVATED, MEMBER_REMOVED, MEMBER_PROFILE_UPDATED,
                                      -- DEPARTMENT_CREATED/RENAMED/ARCHIVED/DELETED, DOCUMENT_UPLOADED, DOCUMENT_VERSION_UPLOADED,
                                      -- DOCUMENT_DELETED, DOCUMENT_VISIBILITY_CHANGED, WORKSPACE_*
    target_type  text,
    target_id    uuid,
    details      jsonb NOT NULL DEFAULT '{}',   -- before/after; never tokens or document content
    trace_id     text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_workspace_time ON core.audit_logs(workspace_id, created_at DESC);
```

`LOGIN` is recorded in the workspace chosen at sign-in. Audit is written in the same transaction as the change. The table is INSERT-only: the application role has no `UPDATE` or `DELETE` on `core.audit_logs`.

---

## 4. Tenant isolation: RLS and connection handling

### 4.1 Database roles

| Role | Used by | Rights |
|---|---|---|
| `sopilot_migrator` | Flyway (one-shot container) | Owner of schemas `core` and `rag` |
| `sopilot_core_app` | core-api | `SELECT/INSERT/UPDATE/DELETE` on `core` tables (except `audit_logs`: `INSERT/SELECT` only); no rights on `rag`; owns no tables; `NOBYPASSRLS` |
| `sopilot_ai_app` | ai-service | The same, but only on schema `rag` |

The two application roles separate the schemas at the database level, so "each service writes only its own schema" is enforced by Postgres, not just by convention. Passwords come from `.env` (V2-08).

### 4.2 Policies

Every table with `workspace_id` has `ENABLE` and `FORCE ROW LEVEL SECURITY`. Two session variables are set with `set_config(..., true)` (equivalent to `SET LOCAL`) at the start of every transaction:

```sql
CREATE FUNCTION core.current_workspace() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$;
CREATE FUNCTION core.current_app_user() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

-- Pattern for ordinary business tables (documents, document_versions, departments, categories, tags,
-- document_tags, document_departments, document_suggestions, invitations, audit_logs, workspace_domains):
CREATE POLICY tenant_isolation ON core.documents
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

-- memberships: visible in the current workspace, or one's own membership in any workspace
-- (to list "my workspaces" and pick a workspace at sign-in).
CREATE POLICY membership_visibility ON core.memberships
    USING (workspace_id = core.current_workspace() OR user_id = core.current_app_user())
    WITH CHECK (workspace_id = core.current_workspace());

-- workspaces: the current workspace, or workspaces one is a member of.
CREATE POLICY workspace_visibility ON core.workspaces
    USING (id = core.current_workspace()
           OR EXISTS (SELECT 1 FROM core.memberships m WHERE m.workspace_id = id AND m.user_id = core.current_app_user()))
    WITH CHECK (id = core.current_workspace());
```

When a variable is not set the function returns `NULL`, the comparison returns `NULL`, and no row matches (fail closed).

**Queries that must cross workspaces** are wrapped in `SECURITY DEFINER` functions owned by `sopilot_migrator`, with `SET search_path = core, pg_temp`, returning only the needed columns, and with `GRANT EXECUTE` only to `sopilot_core_app`:

| Function | Used for |
|---|---|
| `core.find_invitation_by_token_hash(bytea)` | Accepting an invitation before the workspace is known |
| `core.find_pending_invitations_by_email(text)` | Showing pending invitations after sign-in |
| `core.find_domain_workspaces(text)` | Domain join (P1) |
| `core.claim_outbox_batch(int)` | The dispatcher takes work from every workspace (`FOR UPDATE SKIP LOCKED`) |
| `core.create_personal_workspace(uuid user, uuid workspace_id, text name, text email)` | JIT: creates the workspace + OWNER membership when there is no `wid` yet. `workspace_id` is a UUIDv7 generated by the application (§4); if the user already has a personal workspace it returns the existing id and ignores the one passed in |

### 4.3 Setting the variables in Spring

- `TenantContext` (request scope) holds `userId` and `workspaceId` taken from the verified access token, **never** from the body or query.
- `TenantTransactionListener` hooks into `TransactionSynchronizationManager` (or a `DataSource` proxy) to run `SELECT set_config('app.workspace_id', ?, true), set_config('app.user_id', ?, true)` right after the `BEGIN` of every transaction. Without a transaction, RLS tables cannot be queried (controllers call `@Transactional` services).
- Because `is_local = true`, the values disappear when the transaction ends; a connection returned to the pool carries no old workspace. FR-19 has a dedicated test for this (§10).
- Background jobs (outbox, janitor) set `app.workspace_id` per event before reading/writing business tables.

> **Implementation note (2026-11-13):** the implemented mechanism is `TenantTx` (`tenant.run(principal, () -> ...)`), which binds `app.workspace_id`/`app.user_id` with `set_config(..., true)` for that transaction only; `RlsContext` is used only by `TenantTx`/`IdentityService` (enforced by `ArchitectureTest`). The `TenantContext`/`TenantTransactionListener` names above are the original design.

---

## 5. Public API contract (`/api/v1`)

### 5.0 General conventions

- Headers: `Authorization: Bearer <access token>` (except the public auth endpoints); optional `X-Trace-Id`, generated by core-api when missing and returned in the response.
- Success: `{"data": ..., "traceId": "..."}`. Lists: `{"data": [...], "page": {"cursor": "...", "hasMore": true}}` (cursor paging).
- Errors: `{"error": {"code": "DUPLICATE_DOCUMENT", "message": "<sentence for the user>", "details": {...}}, "traceId": "..."}`. Never return an internal exception's `e.getMessage()` (A8); unexpected errors return `500 INTERNAL_ERROR` with a fixed message, the details only in the log with the `traceId`.
- HTTP codes: `400 VALIDATION_FAILED`, `401 UNAUTHENTICATED`, `403 FORBIDDEN` (missing role on a resource one can see), `404 NOT_FOUND` (does not exist **or** is outside read access, so names are not revealed, ADR-007 / V2-24), `409` (business conflict), `413 FILE_TOO_LARGE`, `415 UNSUPPORTED_TYPE`, `422 QUOTA_EXCEEDED`, `429 RATE_LIMITED`.
  > **Discrepancy (checked 2026-11-13):** the code returns `409 QUOTA_EXCEEDED` (`DocumentService`), as §3.3 says; the `422` here is stale.
- The role in the "Access" columns is read from the token's `wrole`; endpoints do not re-read the membership on every request (§5.6). The membership is checked only when tokens are issued: `SUSPENDED` cannot get a new token; suspension through the API revokes the refresh chain immediately, so the next refresh returns `401 UNAUTHENTICATED` (§5.1, step 2), while `403 MEMBERSHIP_SUSPENDED` is returned on sign-in, workspace switch, token reissue and refresh of a chain not yet revoked (step 3); an access token already held stays usable until it expires (≤ 15 minutes, ADR-007 §5).

### 5.1 Authentication

| Method & path | Access | Purpose |
|---|---|---|
| `POST /api/v1/auth/google/nonce` | Public | Issue a nonce for Google Identity Services |
| `POST /api/v1/auth/google` | Public | Sign in with a Google ID token |
| `POST /api/v1/auth/refresh` | Refresh cookie | Rotate the refresh token, issue a new access token |
| `POST /api/v1/auth/switch-workspace` | Signed in | Issue a token for another workspace |
| `POST /api/v1/auth/logout` | Refresh cookie | Revoke the current refresh chain |
| `POST /api/v1/auth/dev-login` | Public, only profiles `local`/`test` | Sign in without Google for tests and eval |
| `GET /.well-known/jwks.json` | Public | RS256 public key for ai-service |

**`POST /api/v1/auth/google/nonce`** → `200 {"data": {"nonce": "<base64url 128 bit>"}}` and `Set-Cookie: sp_nonce=<nonce>.<exp>.<HMAC-SHA256>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=300`. Nothing is stored in the DB.

**`POST /api/v1/auth/google`**

```json
// Request
{ "idToken": "<Google ID token>", "invitationToken": "<optional, from the invitation link>" }
// 200
{
  "data": {
    "accessToken": "<JWT>",
    "expiresIn": 900,
    "user": { "id": "…", "email": "a@acme.com", "displayName": "An" },
    "workspace": { "id": "…", "name": "An's workspace", "kind": "PERSONAL", "role": "OWNER" },
    "pendingInvitations": [ { "id": "…", "workspaceName": "Acme", "role": "MEMBER" } ]
  }
}
```

Checks in order, ported from `GoogleTokenVerifierService` with `nonce` added (A9): signature through Google's JWKS (cached per `Cache-Control`), `iss ∈ {accounts.google.com, https://accounts.google.com}`, `aud = GOOGLE_CLIENT_ID`, `exp` (at most 60 s clock skew), `email_verified = true`, `nonce` matching an unexpired `sp_nonce` cookie with a valid HMAC. Any failure → `401 INVALID_GOOGLE_TOKEN` with a generic message; the specific reason is only logged. The `sp_nonce` cookie is cleared after use.

With `invitationToken` the invitation (§5.3) is applied in the same transaction; on an email mismatch → sign-in still succeeds into the default workspace, the response includes `"invitationError": "EMAIL_MISMATCH"`, and the invitation stays (UC-02).

**Access token** (RS256, `kid` per key pair, lifetime `SOPILOT_ACCESS_TTL=PT15M`):

```json
{
  "iss": "sopilot-core", "aud": ["sopilot-core", "sopilot-ai"],
  "sub": "<user id>", "wid": "<workspace id>", "wrole": "OWNER|ADMIN|MEMBER",
  "wdept": "<department id or null>", "jti": "<uuid>", "iat": 0, "exp": 0
}
```

No email or name in the token. The signing key is read from a PEM file mounted through env (`SOPILOT_JWT_PRIVATE_KEY_PATH`); profiles `local`/`test` generate a key pair when missing. JWKS publishes the current key and the previous one, so key rotation does not drop sessions. The previous key is published when `SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH` is set (V2-29, see §14).

**Refresh token:** a 256-bit random string, base64url, only its SHA-256 is stored. Cookie `sp_refresh; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, lifetime `SOPILOT_REFRESH_TTL=P14D`. The rotation and reuse-detection logic is ported from the old `RefreshTokenService`:

1. Find the token by hash, `FOR UPDATE`. Missing or expired → `401`.
2. The token already has `used_at` or `revoked_at` → **reuse**: revoke the whole `family_id` (`REUSE_DETECTED`), return `401`.
3. Re-read the membership of `(workspace_id, user_id)`: gone → revoke the chain (`MEMBERSHIP_LOST`), `401 MEMBERSHIP_LOST`; `SUSPENDED` → revoke the chain (`SUSPENDED`), `403 MEMBERSHIP_SUSPENDED`. The frontend sends the user to pick another workspace. Suspension, removal or leaving through the API already revoked the chain when the status changed, so a later refresh stops at step 2 with `401 UNAUTHENTICATED`; step 3 is the safety net when the status changed but the chain was not revoked (V2-26).
4. Mark the old token `used_at`, issue a new one in the same `family_id`, with an access token whose `wrole`/`wdept` are **re-read from the DB** (ADR-007 §4.5).

Refresh/logout requests must carry an `Origin` header equal to the frontend origin; otherwise `403`. This is the second CSRF defense next to `SameSite=Strict`.

**`POST /api/v1/auth/switch-workspace`** `{ "workspaceId": "…" }` → checks an `ACTIVE` membership, revokes the current refresh token, issues a new token pair for that workspace, updates `users.last_active_workspace_id`. `404` if not a member.

**`POST /api/v1/auth/dev-login`** `{ "email": "...", "displayName": "..." }`: the bean exists only with `@Profile({"local","test"})`; in other profiles the endpoint returns `404` because it is not registered. Creates an identity with `issuer = "sopilot-dev"`, `subject = email`, then follows the same JIT flow as Google.

### 5.2 Workspaces (FR-03)

| Method & path | Access | Notes |
|---|---|---|
| `GET /api/v1/workspaces` | Signed in | My workspaces (`ACTIVE` or `SUSPENDED` memberships, with status) |
| `POST /api/v1/workspaces` | Signed in | Create a `TEAM` workspace with the creator as OWNER; the response includes a token for the new workspace |
| `GET /api/v1/workspaces/current` | Member | Details of the `wid` workspace, document count, storage used |
| `PATCH /api/v1/workspaces/current` | OWNER | Rename |
| `DELETE /api/v1/workspaces/current` | OWNER | Delete the workspace: soft delete, outbox `DOCUMENT_DELETED` per document, hard delete once ai-service confirms all of them |
| `PUT /api/v1/workspaces/current/domains/{domain}` | OWNER with `hd = domain` | P1, FR-05 |
| `DELETE /api/v1/workspaces/current/domains/{domain}` | OWNER | P1 |

Every administrative endpoint acts on the token's `wid` (`/current`) and takes no `workspaceId` in the path. This removes a whole class of cross-workspace IDOR bugs.

### 5.3 Members and invitations (FR-04, FR-22, FR-05, FR-24)

| Method & path | Access | Notes |
|---|---|---|
| `GET /api/v1/members` | OWNER, ADMIN | Filter by `status`, `departmentId`; search by name/email/employee code. A MEMBER sees only their own profile through `GET /api/v1/members/me` |
| `GET /api/v1/members/me` | Member | My profile in the workspace |
| `PATCH /api/v1/members/{userId}` | OWNER, ADMIN | Edit `displayName`, `employeeCode`, `jobTitle`, `departmentId`, `role` (per the §3.2 rules) |
| `POST /api/v1/members/{userId}/suspend` | OWNER, ADMIN (an ADMIN cannot suspend an OWNER) | Revokes all of the user's refresh tokens for this workspace |
| `POST /api/v1/members/{userId}/reactivate` | OWNER, ADMIN | |
| `DELETE /api/v1/members/{userId}` | OWNER, ADMIN | Remove from the workspace; conversations are kept (ADR-007 §4.2) |
| `POST /api/v1/members/leave` | Member | Leave the workspace; the last OWNER cannot leave (`409 LAST_OWNER`) |
| `GET /api/v1/invitations` | OWNER, ADMIN | Pending invitations |
| `POST /api/v1/invitations` | OWNER, ADMIN | Create an invitation; returns `inviteUrl` **only once** |
| `DELETE /api/v1/invitations/{id}` | OWNER, ADMIN | Revoke |
| `POST /api/v1/invitations/accept` | Signed in | `{invitationToken}` or `{invitationId}` (email invitations shown in `pendingInvitations`) |
| `POST /api/v1/invitations/import` | OWNER, ADMIN | P1, CSV; returns errors per row |

`POST /api/v1/invitations`:

```json
// Request
{ "email": "binh@acme.com", "role": "MEMBER", "displayName": "Bình",
  "departmentId": "…", "employeeCode": "NV-012", "jobTitle": "Kế toán" }
// 201
{ "data": { "id": "…", "expiresAt": "2026-10-27T10:00:00Z",
            "inviteUrl": "http://localhost:3000/invite#token=<random 256 bit>" } }
```

The token sits after `#` so it never reaches server logs or the `Referer` header. V2 sends no email (out of scope); the inviter sends the link. An email invitation also appears in `pendingInvitations` when the invitee signs in with that email, so a lost link can still be accepted.

Accepting an invitation: lock the invitation row (`FOR UPDATE` through a definer function), check it is not accepted, revoked or expired, and that `lower(google_email) = invitations.email`; create the membership with the profile copied from the invitation; if already a member, only mark the invitation as used. Errors: `409 INVITATION_EMAIL_MISMATCH` (the invitation stays), `410 INVITATION_EXPIRED`, `410 INVITATION_REVOKED`, `409 INVITATION_ALREADY_USED`.

### 5.4 Departments (FR-23)

| Method & path | Access | Notes |
|---|---|---|
| `GET /api/v1/departments` | Member | A MEMBER only needs names for display; returns only `ACTIVE` by default, `?includeArchived=true` for OWNER/ADMIN |
| `POST /api/v1/departments` | OWNER, ADMIN | `409 DEPARTMENT_NAME_TAKEN` |
| `PATCH /api/v1/departments/{id}` | OWNER, ADMIN | Rename, `status: ARCHIVED|ACTIVE` |
| `DELETE /api/v1/departments/{id}` | OWNER, ADMIN | `409 DEPARTMENT_IN_USE` with the counts of members, pending invitations and referencing documents |

A department move takes effect at the next refresh (≤ 15 minutes). Deactivating or deleting a department never changes `documents.visibility` (FR-23): documents restricted to an `ARCHIVED` department stay restricted.

### 5.5 Documents (FR-06, FR-07, FR-09)

| Method & path | Access | Notes |
|---|---|---|
| `POST /api/v1/documents` | OWNER, ADMIN | Multipart: `file`, `visibility` (default `WORKSPACE`), `departmentIds[]`, `title?`, `categoryId?`, `tags[]?` |
| `POST /api/v1/documents/{id}/versions` | OWNER, ADMIN | Upload a replacement for the document the user chose; `200` (repeated send while processing), `409 VERSION_IN_PROGRESS`, `409 DOCUMENT_UNCHANGED`, `409 DUPLICATE_DOCUMENT` per §3.3 |
| `POST /api/v1/documents/{id}/retry` | OWNER, ADMIN | Only when the latest version is `FAILED`; increments `attempt`, moves the version back to `UPLOADED`, creates an `INGEST_REQUESTED` outbox event carrying the new `attempt`. Calling it again once the version has left `FAILED` → `409 VERSION_NOT_FAILED` (a double click does not create two jobs) |
| `GET /api/v1/documents` | Member | Read-access filter (§5.6), filter by `status`, `categoryId`, `tag`, `q` (title) |
| `GET /api/v1/documents/{id}` | Member with read access | `404` if outside access |
| `GET /api/v1/documents/{id}/download-url` | Member with read access | `{url, expiresAt}`, a pre-signed S3 URL valid `≤ 300 s`, `Content-Disposition` with the original name |
| `GET /api/v1/documents/{id}/versions` | OWNER, ADMIN | Version history and `FAILED` reasons |
| `DELETE /api/v1/documents/{id}` | OWNER, ADMIN | Soft delete, outbox `DOCUMENT_DELETED`; the S3 file and the row are deleted once ai-service confirms |

The "OWNER, ADMIN" write access in this table is the original design; ADR-009 replaced it with the publisher rules of §15.

Upload checks: the file extension and magic bytes must match `PDF` (`%PDF-`) or `MD` (`.md`/`.markdown`, valid UTF-8, no NUL byte). DOCX is deferred until after the MVP (owner decision 2026-10-20) and TXT is dropped from the MVP (owner decision 2026-10-21): `.txt`, DOCX, images, `DOC`, `XLS(X)` are rejected immediately with `415 UNSUPPORTED_MEDIA_TYPE` and no job; the message tells the user to export DOCX to a PDF with a text layer, or rename TXT to `.md`. No server-side conversion (unlike the old system, AUDIT-ingestion §2.1). MD that is not UTF-8 → `415 INVALID_ENCODING`. Over 20 MB → `413` (the limit is set in `spring.servlet.multipart` and re-checked while streaming).

Multi-file selection (FR-30): the frontend sends up to 10 independent `POST /api/v1/documents` requests (at most 3 concurrently); there is no batch endpoint or all-or-nothing transaction; each request succeeds or fails on its own. Resending a file after a network error: if the earlier request was stored, the later one gets `409 DUPLICATE_DOCUMENT` with `{documentId, title, createdAt}` and the frontend shows "Already in the workspace". The MVP uses no client-side `Idempotency-Key`.

`FAILED` codes and the action suggested in the UI: `EMBEDDING_ERROR`, `RETRY_EXHAUSTED`, `OBJECT_NOT_FOUND`, `EXTRACTION_ERROR` → "Retry"; `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING`, `EMPTY_CONTENT`, `UNSUPPORTED_TYPE` → "Replace file" or "Delete" (retry is still allowed but is not the main action).

The returned `Document` object:

```json
{
  "id": "…", "title": "Quy trình mua hàng", "description": null,
  "category": { "id": "…", "name": "Mua sắm" }, "tags": ["ISO", "mua hàng"],
  "language": "vi", "visibility": "DEPARTMENTS", "departments": [ { "id": "…", "name": "Kế toán" } ],
  "status": "READY", "answerable": true,
  "latestVersion": { "id": "…", "versionNo": 3, "status": "PROCESSING", "failureCode": null, "failureMessage": null },
  "currentVersion": { "id": "…", "versionNo": 2, "originalName": "QT-MH-01.pdf", "fileType": "PDF",
                      "sizeBytes": 183422, "pageCount": 7, "docCode": "QT-MH-01", "revisionLabel": "03",
                      "effectiveDate": "2026-01-15", "warningCodes": ["PAGES_WITHOUT_TEXT"] },
  "fieldSources": { "title": "USER", "description": "SYSTEM", "category": "SUGGESTED", "tags": "SUGGESTED", "language": "SYSTEM" },
  "suggestions": { "title": "Quy trình mua hàng", "proposedCategoryName": "Mua sắm" },
  "suggestion": { "status": "READY", "description": "…", "proposedCategoryName": null },
  "createdBy": { "id": "…", "displayName": "An" }, "createdAt": "…", "updatedAt": "…"
}
```

`departments`, `fieldSources`, `suggestion` and `latestVersion.failure*` are returned only to OWNER/ADMIN. `currentVersion` is the version the FR-31 view shows (content from ai-service `GET /ai/v1/documents/{id}/versions/{currentVersion.id}/content`); when `latestVersion` differs from `currentVersion`, the frontend labels it "version N+1 processing / failed".

### 5.6 Metadata and visibility (FR-25..28)

| Method & path | Access | Notes |
|---|---|---|
| `PATCH /api/v1/documents/{id}` | OWNER, ADMIN | Edit `title`, `description`, `categoryId`, `tags[]`, `language`; edited fields get source `USER`. Does not call ai-service, except for `language` when BM25 is configured per language (currently not, see TECH-V2-ai-service §6.3) |
| `PUT /api/v1/documents/{id}/visibility` | OWNER, ADMIN | `{visibility, departmentIds[]}`; flow §2.3; response `{accessSync: APPLIED|PENDING}` |
| `POST /api/v1/documents/{id}/suggestion/apply` | OWNER, ADMIN | Accept the selected suggested fields: `{fields: ["description","category"]}`; the source becomes `USER` |
| `GET/POST/PATCH/DELETE /api/v1/categories[/{id}]` | Read: member; write: OWNER, ADMIN | Flat; `ARCHIVED` cannot be newly assigned |
| `GET /api/v1/tags` | Member | Tags are created when attached through `PATCH /documents/{id}` |

**The read-access filter in core-api** (lists, detail, download URL; ADR-007 §4.4), fully parameterized:

```sql
SELECT d.* FROM core.documents d
WHERE d.deleted_at IS NULL
  AND ( :wrole IN ('OWNER','ADMIN')
        OR d.visibility = 'WORKSPACE'
        OR (:wdept IS NOT NULL AND EXISTS (
              SELECT 1 FROM core.document_departments dd
              WHERE dd.document_id = d.id AND dd.department_id = :wdept)) )
```

RLS already limits the workspace; the condition above limits by role/department. `wrole` and `wdept` come from the token and the DB is not re-read on every request (consistent with ai-service; at most 15 minutes of lag, as in ADR-007).

**Applying suggestions (FR-28, V2-25):** on `PUT /internal/documents/{id}/suggestions`, core-api stores `document_suggestions`, then for every field **except the title** whose source is `SYSTEM` or `SUGGESTED`, writes the suggested value and sets the source to `SUGGESTED`. Fields with source `USER` are not touched. **A suggested title is only stored in `document_suggestions`, never applied automatically** (owner decision 2026-11-12): the first Markdown heading is often a section name, not the document name (a real run with `gitlab-meetings.md` produced "What to do before the meeting"). The suggested title, and a proposed category name when the document has no category, are returned in the `Document`'s `suggestions` (only to OWNER/ADMIN and the responsible publisher, like `fieldSources`; `null` when nothing differs from the current value or the title was set by `USER`). The UI pre-fills the title field with this value; the user saves through the existing `PATCH` (source `USER`), and clearing the field then saving keeps the current title. No new endpoint. A suggestion contains no `visibility` or departments and cannot change them (the DTO has no such fields). A category is accepted only as a `categoryId` belonging to the workspace and `ACTIVE`; a new category name is stored only as a proposal and never created automatically.

### 5.7 Audit (FR-20)

`GET /api/v1/audit-logs?action=&actorId=&from=&to=&cursor=` — OWNER only, newest first.

---

## 6. Language of user-facing messages and errors

`failure_message` and `error.message` are Vietnamese or English sentences according to the `Accept-Language` header (default `vi`). The list of error codes is the contract with the frontend; messages may change.

---

## 7. Outbox dispatcher

- The `OutboxDispatcher` bean has two paths:
  1. **Immediate push:** after commit (`@TransactionalEventListener(phase = AFTER_COMMIT)`), it sends the event just written on a dedicated executor. This is how ai-service is woken up (ADR-006 B1 constraint 3) and makes `ACCESS_UPDATED` nearly synchronous.
  2. **Periodic scan:** every `SOPILOT_OUTBOX_POLL=PT5S` it calls `core.claim_outbox_batch(20)` (`FOR UPDATE SKIP LOCKED` on `status = 'PENDING' AND next_attempt_at <= now()`) and sends each event.
- Retries: exponential backoff `2^attempts` seconds, capped at 10 minutes, with jitter; after `SOPILOT_OUTBOX_MAX_ATTEMPTS=20` the event becomes `DEAD` and is logged at `ERROR`. A document version whose `INGEST_REQUESTED` event is `DEAD` becomes `FAILED` with `failure_code = DISPATCH_FAILED` so the user can retry.
- A `4xx` from ai-service (except `408`, `429`) is a contract error: `DEAD` immediately, no endless retries.
- Idempotency: `outbox_events.id` is sent in the `Idempotency-Key` header; ai-service ignores keys it has already processed (TECH-V2-ai-service §8).
- Ordering: `ACCESS_UPDATED` carries `accessRevision`; ai-service applies it only when it is greater than the stored one, so out-of-order delivery cannot roll permissions back.

---

## 8. Contract between core-api and ai-service (shared source)

Every `/internal/**` endpoint requires the header `X-Internal-Token: <SOPILOT_INTERNAL_TOKEN>`, compared in constant time. Missing or wrong → `401`. Both services use the same token in both directions (one env variable). JSON bodies, `camelCase`.

### 8.1 core-api → ai-service

**`POST /internal/ingestions`** (`INGEST_REQUESTED`) → `202`; a repeated `Idempotency-Key`, or the same `(versionId)` with an `attempt` not greater than before → `202` without a new job. A greater `attempt` while the job is `FAILED` → the job goes back to the queue (retry, TECH-V2-ai-service §8).

```json
{
  "workspaceId": "…", "documentId": "…", "versionId": "…", "versionNo": 2,
  "objectKey": "workspaces/…/documents/…/versions/…", "sha256": "<hex>", "attempt": 0,
  "fileType": "PDF", "mimeType": "application/pdf",
  "originalName": "QT-MH-01.pdf", "title": "Quy trình mua hàng",
  "access": { "visibility": "DEPARTMENTS", "departmentIds": ["…"], "accessRevision": 3 },
  "suggest": { "enabled": true, "categories": [ { "id": "…", "name": "Mua sắm" } ], "tags": ["ISO"] }
}
```

ai-service writes (or upgrades) `rag.document_access` and creates `rag.ingestion_jobs` **in the same transaction**, so the access row always exists before any chunk can be retrieved (ADR-007 §4.5, V2-12).

**`PUT /internal/document-access/{documentId}`** (`ACCESS_UPDATED`) → `200 {"applied": true|false}` (`false` when `accessRevision` is not newer).

```json
{ "workspaceId": "…", "visibility": "WORKSPACE", "departmentIds": [], "accessRevision": 4 }
```

**`DELETE /internal/documents/{documentId}?workspaceId=…`** (`DOCUMENT_DELETED`) → `200` after deleting `document_access`, chunks, jobs and extraction results of every version; idempotent (`200` even when nothing is left). Citations in conversation history to a deleted document are hidden as if access were lost.

### 8.2 ai-service → core-api

**`PATCH /internal/documents/{documentId}/versions/{versionId}/status`**

```json
{ "workspaceId": "…", "status": "READY", "attempt": 0,
  "pageCount": 7, "detectedLanguage": "vi", "chunkCount": 41,
  "embedding": { "provider": "local", "model": "BAAI/bge-m3", "revision": "<hf commit>", "dim": 1024 },
  "extracted": { "docCode": "QT-MH-01", "revisionLabel": "03", "effectiveDate": "2026-01-15", "approvedBy": null },
  "warningCodes": ["PAGES_WITHOUT_TEXT"] }
// or
{ "workspaceId": "…", "status": "FAILED", "failureCode": "NO_TEXT_LAYER",
  "failureMessage": "PDF không có lớp chữ (bản scan). Hãy tải bản PDF có thể chọn chữ." }
```

Valid transitions: `UPLOADED → PROCESSING → READY | FAILED`, `FAILED → UPLOADED` (through core-api's `POST /retry`, `attempt + 1`), `FAILED → PROCESSING` (ai-service retries on its own within `SOPILOT_INGEST_MAX_ATTEMPTS`). A callback carrying an `attempt` older than the current one is ignored (`200`, no status change). An invalid transition (for example a version already `SUPERSEDED`) → `409`, and ai-service does not retry. On `READY`: set `current_version_id`, store `warning_codes`, move every older version to `SUPERSEDED`, and delete the previous version's S3 object after `SOPILOT_VERSION_RETENTION` (deleted immediately by default; can be kept if history is needed later).

**`PUT /internal/documents/{documentId}/suggestions`** (FR-28)

```json
{ "workspaceId": "…", "versionId": "…", "method": "LLM", "model": "openai/gpt-oss-20b", "promptVersion": "suggest-v1",
  "title": "Quy trình mua hàng", "description": "…", "categoryId": "…", "proposedCategoryName": null,
  "tags": ["mua hàng", "ISO"], "language": "vi" }
```

ai-service calls these endpoints through its own outbox (`rag.outbox_events`, TECH-V2-ai-service §3), with the same retry and idempotency rules as §7.

### 8.3 Reading files

ai-service reads objects directly from storage using the job's information (`objectKey`) with its own read-only credential (`SOPILOT_S3_AI_ACCESS_KEY`). ai-service never writes to storage.

---

## 9. Configuration (environment variables; real values only in `.env`)

| Variable | Default | Notes |
|---|---|---|
| `SPRING_PROFILES_ACTIVE` | none | `local` (dev), `test` (automated tests). Without a profile it runs in real mode: no dev login, and it refuses to start without `SOPILOT_JWT_PRIVATE_KEY_PATH` or `SOPILOT_NONCE_HMAC_KEY` |
| `SOPILOT_DB_URL`, `SOPILOT_DB_USER`, `SOPILOT_DB_PASSWORD` | — | Role `sopilot_core_app` |
| `GOOGLE_CLIENT_ID` | — | |
| `SOPILOT_JWT_PRIVATE_KEY_PATH`, `SOPILOT_JWT_KID` | generated in `local`/`test` | |
| `SOPILOT_ACCESS_TTL`, `SOPILOT_REFRESH_TTL` | `PT15M`, `P14D` | Access ≤ 15 minutes is an NFR |
| `SOPILOT_NONCE_HMAC_KEY` | — | |
| `SOPILOT_FRONTEND_ORIGIN` | `http://localhost:3000` | `Origin` check for refresh/logout, `inviteUrl` generation |
| `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_AI_BASE_URL` | —, `http://ai-service:8000` | |
| `SOPILOT_S3_ENDPOINT`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_ACCESS_KEY`, `SOPILOT_S3_SECRET_KEY` | — | A single bucket name for both services (avoids the `poliwise-documents`/`sopilot-documents` drift) |
| `SOPILOT_QUOTA_DOCS_PER_WORKSPACE`, `SOPILOT_QUOTA_BYTES_PER_WORKSPACE` | `50`, `209715200` | FR-09 (owner decision 2026-10-21), `0` = off; set `0` when loading a large eval/demo corpus |
| `SOPILOT_OUTBOX_POLL`, `SOPILOT_OUTBOX_MAX_ATTEMPTS` | `PT5S`, `20` | |
| `SOPILOT_DOMAIN_JOIN_ENABLED` | `false` | P1 |

The authoritative list of variables is `.env.example` and `services/core-api/README.md`.

---

## 10. Test strategy

| Layer | Content | Tools |
|---|---|---|
| Unit | Google token verification (one test per wrong claim, including `nonce`), refresh rotation and reuse detection, the last-OWNER rule, ADMIN not touching OWNER, version status transitions, applying suggestions by field source, the error mapper not leaking internal messages | JUnit 5, Mockito |
| Integration | Migrations run cleanly on an empty DB; RLS with the real `sopilot_core_app` role; JIT idempotent with two concurrent sign-in requests; SHA-256 dedup with two concurrent uploads; quota: a workspace with 48 documents receiving 10 concurrent uploads gives exactly 2 successes and 8 `409 QUOTA_EXCEEDED`, with no orphan S3 objects after the janitor; the §3.3 replacement rules (all 5 branches); two consecutive retries create one outbox event; `.txt`/DOCX → `415` without a job; outbox retry and `DEAD`; accepting an invitation with the wrong email | Testcontainers (Postgres + pgvector, MinIO), WireMock for Google JWKS and ai-service |
| Security (FR-19, core part) | Two workspaces whose documents contain different secret strings: every `/api/v1` endpoint called with workspace A's token returns none of B's data; a direct query with `app.workspace_id` unset returns 0 rows; a connection returned to the pool after A's transaction and reused for B's request sees none of A's data | Testcontainers, run in CI |
| Security (FR-29, core part) | A MEMBER outside the department: list, detail and download URL return `404`; a department move takes effect after refresh; `SUSPENDED` cannot refresh; deleting a department in use returns `409`; narrowing visibility sends `ACCESS_UPDATED` | Testcontainers |
| Contract | The §8 JSON is checked against sample files shared in `services/contracts/` (the same files ai-service uses in its tests) | JSON Schema |

`validate-build.ps1` and `run-tests.ps1` need a `core-api` scope (ADR-004 §5, V2-08/V2-11).

> **Implementation note (2026-11-13):** the tests use in-process fakes (`InMemoryStorage`, `RecordingAiClient`) rather than WireMock/Mockito in most places (see `.claude/rules/core-api.md`); the overall testing approach is in `docs/quality/testing-strategy.md`.

---

## 11. Open questions (owner decision 2026-10-20)

The owner approved the proposals for Q1, Q3, Q4 and Q5. Q2 was replaced by the decision to pause commercial quotas (PRD-V2 FR-09, §8.10).

| # | Question | Decision |
|---|---|---|
| Q1 | ADR-004 §4.1 puts **feedback and knowledge gaps** in core-api, but questions, answers, citations and refusal flags all live in `rag` (ai-service). In core-api it would need a copy of the question content over the outbox and could not itself check which user a `messageId` belongs to. | **Decided:** move FR-16/FR-17 to ai-service (`rag.message_feedback`, a knowledge-gap view, TECH-V2-ai-service §7.6). ADR-004 §4.1 and V2-13's `scope` were updated. |
| Q2 | Question quota: PRD FR-09 says **20 questions/user/day**, ticket V2-12 says **50**. Where is the question quota counted? | **Decided:** the question quota is paused (default `0`). When re-enabled it is counted in ai-service, because Q&A requests go straight there (TECH-V2-ai-service §7.4), with the PRD reference value of 20; core-api keeps only the document quota. |
| Q3 | Next.js rewrites or Caddy for a single origin? | Next.js rewrites (no extra container); switch to Caddy if V2-15 finds SSE buffered. |
| Q4 | Keep the old version's file after the new version is `READY`? | Delete it immediately (no version comparison feature in V2); configurable through `SOPILOT_VERSION_RETENTION`. |
| Q5 | Does sign-in need at least one invitation, or can anyone with Google get in? | Anyone gets in and has a personal workspace (PRD UC-01). Recorded because it differs completely from M1 (roster blocking with 403). |
| Q6 | Default document quota? (owner decision 2026-10-21) | 50 documents / 200 MB per workspace, configurable, `0` = off; the question quota stays off by default (Q2). Replaces the 2026-10-20 decision to disable it by default, for the document quota only. |
| Q7 | Accept a replacement while the previous version is still processing? (owner decision 2026-10-21) | No: the same bytes return the processing version, different bytes give `409 VERSION_IN_PROGRESS` (§3.3). Avoids a version queue and out-of-order activation. |

---

## 12. Not done in V2 (restated to avoid porting by mistake)

- Do not port `core.employee_roster`, `metadata.document_access_rules`, `password_reset_tokens`, OTP, or the password-hash column (ADR-005 §4.1, ADR-007).
- No RabbitMQ events; no reading other services' schemas.
- No invitation emails (the inviter shares the link).

---

## 13. Implementation notes for V2-12 and V2-23 (2026-11-06, owner approval 2026-11-09)

Places where the code differs from the specification above. The owner approved them during V2-12/V2-23 acceptance (2026-11-09); this table wins over the corresponding sections above.

| Item | TECH | Code | Reason |
|---|---|---|---|
| S3 PUT order (§2.2) | PUT before every DB step | Checks and row writes first, PUT **at the end** of the transaction, then commit | Conflicts (duplicate, quota, in progress) never touch storage, so no orphan objects; `StorageJanitor` cleans up when the commit fails after the PUT. In exchange the advisory lock is held during the PUT |
| Setting the RLS variables (§4.3) | A listener on `TransactionSynchronizationManager` | `TenantTx` wraps each transaction, taking the tenant from `AuthPrincipal` | Explicit, independent of synchronization registration order |
| Quota-exceeded code (§5.0 and §3.3) | `422` in §5.0, `409` in §3.3 and the ticket | `409 QUOTA_EXCEEDED` with `{kind, limit, used}` | Per ticket V2-12 and §3.3 |
| FK `invitations.department_id` (§3.2) | `ON DELETE RESTRICT` | `ON DELETE SET NULL (department_id)`; `DepartmentService` blocks while there are **pending** invitations | Used/revoked invitations are history and must not pin a department forever |
| Tables created early | `categories`, `document_departments` belong to V2-24 | Created in `V005` | `documents.category_id` and blocking department deletion need them; the API is still V2-24 |
| `failure_message` (§5.5, §6) | Per `Accept-Language` | A fixed Vietnamese sentence per code, stored at write time | The value is stored in the DB; a header-based locale would need translation at read time |
| Effective date (§8.2) | ISO `effectiveDate` | Non-ISO values are ignored | ai-service extracts it from free text and dead-letters every `4xx` |
| `PATCH /members/{userId}` (§5.3) | Has `role` | Does not accept `role` yet | Role changes and the full OWNER rules are V2-30 |

## 14. Implementation notes for V2-29 (2026-11-08, owner approval 2026-11-09)

Places where the code differs from the specification above. The owner approved them during V2-29 acceptance (2026-11-09); this table wins over the corresponding sections above.

| Item | TECH | Code | Reason |
|---|---|---|---|
| Workspace deletion (§5.2) | Soft delete, hard delete once ai-service confirms everything | Soft delete only (`workspaces.deleted_at`) and one `DOCUMENT_DELETED` event per document; the workspace row is **not yet hard-deleted** | Hard deletion inside the outbox hook would cascade-delete the very outbox row the dispatcher is updating. Needs a separate cleanup job. **Owner decision 2026-11-09: outside the MVP**, no ticket added (local only; the soft delete already blocks access and refresh) |
| Revoking refresh tokens when deleting a workspace | Not stated | Not revoked row by row; `findMembership` skips deleted workspaces, so the next refresh returns `401 MEMBERSHIP_LOST` and revokes the chain | Avoids the `workspace` module depending on `identity` (a cycle). Access tokens already issued live at most 15 minutes |
| Code location (§5.2) | Controller/service in `workspace/` | `WorkspaceController/Service` (list, `/current`) in `workspace/`; workspace creation and switching (token issuance) in `identity/WorkspaceSession*` | `ArchitectureTest` forbids cycles between modules: `identity` already depends on `workspace` |
| `WorkspaceRole` | Nested in `WorkspaceRepository` | A separate enum in `security/WorkspaceRole` | `security` depending on `workspace` would stop `workspace` from using `AuthPrincipal` (a cycle) |
| Revoking refresh on suspend, remove, leave | §5.3 mentions only suspension | Suspension, member removal and leaving the workspace all revoke the user's chain in that workspace | Blocking/removal takes effect at the very next refresh, without waiting for the membership re-read |
| `POST /auth/refresh` | Returns a new access token | Returns the same body as sign-in (`accessToken`, `user`, `workspace`) | The frontend restores the session after a page reload using only the cookie |
| Previous signing key (§5.1) | Published in JWKS | Variable `SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH` (PEM public key); core-api also accepts tokens signed with this key | Key rotation does not drop sessions; remove the variable once old access tokens have expired (15 minutes) |
| Domain join (§5.2, FR-05) | `PUT/DELETE /workspaces/current/domains/{domain}` | Not done | P1, outside V2-29's criteria |
| Column `refresh_tokens.workspace_id` (§3.1) | `workspace_id` | `target_workspace_id` | The tenant-isolation suite treats every table with a `workspace_id` column as a tenant table and requires RLS; this table is global (looked up by `token_hash` before the workspace is known). Renamed so the check does not need loosening; the table is added to `GLOBAL_TABLES` (the reviewed list) in `tests/tenant-isolation/isolation.py` |

## 15. Department publishers (ADR-009, approved, implemented in V2-36)

> **Status of this section:** the specification of [ADR-009](../decisions/adr-009-department-publishers.md) (`approved` 2026-11-10). This section **wins** over the "Access" column of the document write endpoints in §5.5 and §5.6 and over the `OWNER, ADMIN` check in the §2.2 and §2.3 diagrams. V2-36 implemented it (2026-11-11); deviations are in §17. `Q#` refers to the questions settled in ADR-009 §6.

### 15.1 Scope

- core-api and schema `core` only. ai-service, `rag.document_access`, the token claims (`wid`, `wrole`, `wdept`) and the §5.6 read filter are **unchanged**.
- Affected document write endpoints (the `principal.requireManager()` calls in `DocumentService`): `POST /documents`, `POST /documents/{id}/versions`, `POST /documents/{id}/retry`, `PATCH /documents/{id}`, `PUT /documents/{id}/visibility`, `POST /documents/{id}/suggestion/apply`, `DELETE /documents/{id}`; plus a new OWNER-only endpoint `PUT /documents/{id}/ownership` (§15.4, ADR-009 decision 8). Reads with admin fields: `GET /documents/{id}/versions` and the `Document` fields `departments`, `fieldSources`, `suggestion`, `latestVersion.failure*` (§5.5).
- Unchanged: `DocumentService.deleteAll` when the OWNER deletes the workspace (§5.2); categories, tags, departments, members (still OWNER/ADMIN); the `/internal/**` callbacks (the system, no human caller).

### 15.2 Logical DDL (migration `core/V009`, written with the `flyway-migration` skill in V2-36)

A sketch to agree on columns and constraints; not the migration file.

```sql
-- Department publisher: at most one person per department.
CREATE TABLE core.department_publishers (
    workspace_id  uuid NOT NULL,
    department_id uuid PRIMARY KEY,
    user_id       uuid NOT NULL,
    assigned_at   timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, user_id)       REFERENCES core.memberships(workspace_id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_department_publishers_user ON core.department_publishers(workspace_id, user_id);

-- Workspace publisher (WORKSPACE documents): at most one person per workspace. ADR-009 §6 Q0.
CREATE TABLE core.workspace_publishers (
    workspace_id uuid PRIMARY KEY,
    user_id      uuid NOT NULL,
    assigned_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, user_id) REFERENCES core.memberships(workspace_id, user_id) ON DELETE CASCADE
);

-- The document's owning department.
ALTER TABLE core.documents ADD COLUMN owner_department_id uuid;
ALTER TABLE core.documents
    ADD CONSTRAINT fk_documents_owner_department
        FOREIGN KEY (workspace_id, owner_department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT,
    -- The owning department must be in the list of reading departments; checked at commit because
    -- documents and document_departments are written in the same transaction.
    ADD CONSTRAINT fk_documents_owner_in_scope
        FOREIGN KEY (id, owner_department_id) REFERENCES core.document_departments(document_id, department_id)
        DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT ck_documents_owner_matches_visibility
        CHECK ((visibility = 'WORKSPACE') = (owner_department_id IS NULL));   -- ADR-009 §6 Q1
CREATE INDEX ix_documents_owner_department ON core.documents(workspace_id, owner_department_id)
    WHERE owner_department_id IS NOT NULL;
```

Notes:
- **Two-column FKs** per the schema convention (§3.2): the department and the membership must be in the same workspace as the publisher row. `department_publishers.workspace_id` needs no separate FK to `workspaces` because both two-column FKs already bind it; `workspace_publishers` binds the workspace through the FK to `memberships`.
- **`ON DELETE CASCADE` to `memberships`**: a member who leaves or is removed from the workspace loses the publisher role immediately (ADR-009 §4.1 item 4). Deleting a department (only possible without references, §5.4) takes the publisher row with it.
- **`fk_documents_owner_in_scope`** uses `document_departments`' existing PK `(document_id, department_id)`; `MATCH SIMPLE` skips it when `owner_department_id IS NULL` (`WORKSPACE` documents). Deleting the owning department's `document_departments` row (narrowing the list and dropping the owning department) is blocked at commit. Hard-deleting a document cascades on both sides, so the FK is not in the way. The migration must test the write order `documents` → `document_departments` when creating a `DEPARTMENTS` document (the FK is deferred until commit).
- **The publisher must belong to the department** cannot be expressed as an FK without blocking an ADMIN from moving departments (ADR-009 §3, rejected variant). Instead there are two layers in §15.3: delete the publisher row when the department changes, and re-check at write time.
- **No `uploaded_at` column**: `document_versions.uploaded_by` and `created_at` (the publication time) already exist since `core/V005` (ADR-009 §4.1 item 5). The API returns them in `GET /documents/{id}/versions` as `uploadedBy`, `uploadedAt`.
- **RLS and grants**: both new tables have `workspace_id`, enable `ENABLE` + `FORCE ROW LEVEL SECURITY` with the §4.2 `tenant_isolation` policy pattern, and grant DML to `sopilot_core_app`; the `tests/tenant-isolation` suite treats them as tenant tables automatically (they have a `workspace_id` column).
- **Backfill** (ADR-009 §4.4): `workspace_publishers` from `workspaces.created_by` if still an `ACTIVE` member, otherwise the `ACTIVE` OWNER with the earliest `joined_at`; soft-deleted workspaces are skipped. `department_publishers` stays empty. `owner_department_id` for existing `DEPARTMENTS` documents per ADR-009 §6 Q6; the `ck_documents_owner_matches_visibility` CHECK is added after the backfill step in the same migration.
- `core.create_personal_workspace(...)` (§4.2) and `POST /workspaces` also insert a `workspace_publishers` row for the creator in the same transaction. The `SECURITY DEFINER` function is changed with `CREATE OR REPLACE` in a new migration; `V003` is not edited.

### 15.3 The write check in core-api

A single component, `document/DocumentWritePolicy`, replaces `principal.requireManager()` on every document write endpoint. It runs **inside** the write operation's `TenantTx` transaction, after the document has been loaded through the read filter:

```text
requireCanWrite(principal, doc):            -- doc has passed the read filter; unreadable means 404 before this step
    m = membership(wid, principal.userId)   -- re-read from the DB, not the token's wrole/wdept
    if m is null or m.status != ACTIVE: 403 NOT_PUBLISHER
    if doc.owner_department_id is null:
        p = SELECT user_id FROM core.workspace_publishers
            WHERE workspace_id = :wid FOR SHARE
    else:
        p = SELECT user_id FROM core.department_publishers
            WHERE workspace_id = :wid AND department_id = :owner FOR SHARE
        if m.department_id != doc.owner_department_id: 403 NOT_PUBLISHER   -- layer 2: the publisher left the department
    if p is null or p != principal.userId: 403 NOT_PUBLISHER

requireCanCreate(principal, visibility, ownerDepartmentId, departmentIds):
    WORKSPACE   -> as the workspace branch above
    DEPARTMENTS -> ownerDepartmentId required (default = m.department_id), the department must be ACTIVE,
                   must be in departmentIds (400 OWNER_DEPARTMENT_NOT_IN_SCOPE), then as the department branch

requireCanDelete(principal, doc):           -- ADR-009 decision 8: the OWNER revokes
    m = membership(wid, principal.userId)
    if m.role == OWNER and m.status == ACTIVE: allow (actingAs = OWNER)
    else: requireCanWrite(principal, doc)

requireCanTransfer(principal):              -- PUT /documents/{id}/ownership
    m = membership(wid, principal.userId)
    if m.role != OWNER or m.status != ACTIVE: 403 FORBIDDEN
```

- `FOR SHARE` on the publisher row stops the OWNER from changing the publisher between the check and the commit; changing a publisher takes `FOR UPDATE` on the same row. With no row (the department has no publisher) the result is always `403`.
- The OWNER role in `requireCanDelete`/`requireCanTransfer` is re-read from `memberships` in the transaction, not taken from the token's `wrole`, so an OWNER who was just demoted cannot revoke while their token is still valid.
- Error order: a document that does not exist or is outside read access → `404 NOT_FOUND`; readable but not the responsible publisher → `403 NOT_PUBLISHER`. An ADMIN who is not a publisher gets `403` on every write endpoint; an OWNER who is not a publisher gets `403` on every write endpoint except `DELETE` and `PUT /ownership` (ADR-009 §6 Q4, Q5).
- `PUT /documents/{id}/visibility` (publisher): accepts only a `visibility` of the same type, and for `DEPARTMENTS` the `departmentIds` must contain the owning department; changing the type or dropping the owning department → `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`. That goes through `PUT /ownership` (§15.4). The read-access sync to ai-service keeps the §2.3 flow for both endpoints.
- `POST /documents` accepts an extra multipart field `ownerDepartmentId` (optional). A `DEPARTMENTS` upload without it takes the caller's membership department; a caller without a department → `400 VALIDATION_FAILED`.
- The admin fields of `Document` and `GET /documents/{id}/versions`: returned when `isManager()` **or** the caller is the document's responsible publisher (the same query as `DocumentWritePolicy`, without locking).
- A unit test (or `ArchitectureTest`) checks that no `requireManager()` remains in `DocumentService` except in `deleteAll`.

**Keeping "the publisher belongs to the department" when a membership changes** (in the same transaction as the membership change):

| Event | Handling of the publisher row |
|---|---|
| `PATCH /members/{userId}` changes `departmentId` | Delete the user's `department_publishers` rows for departments other than the new one; audit `PUBLISHER_UNASSIGNED` (reason `DEPARTMENT_CHANGED`) |
| Member removed, leaves the workspace | FK `ON DELETE CASCADE` deletes both kinds; audit is written before deleting the membership |
| Suspension | Keep the row; `requireCanWrite` refuses because `status != ACTIVE`, and the suspended person cannot get a token |
| `ARCHIVED` department | Keep the row: the publisher can still edit and delete existing documents; `requireCanCreate` refuses an `ARCHIVED` department |

### 15.4 Publisher assignment API

| Method & path | Access | Notes |
|---|---|---|
| `GET /api/v1/publishers` | Member | `{workspace: {userId, displayName} or null, departments: [{departmentId, name, publisher}]}`; only `ACTIVE` departments unless an OWNER/ADMIN sends `?includeArchived=true`. No emails returned |
| `PUT /api/v1/publishers/workspace` | OWNER | `{userId}`; `409 MEMBER_NOT_ACTIVE` if not an `ACTIVE` member |
| `DELETE /api/v1/publishers/workspace` | OWNER | The workspace has no publisher; `WORKSPACE` documents cannot be written until one is assigned |
| `PUT /api/v1/departments/{id}/publisher` | OWNER | `{userId}`; `409 PUBLISHER_NOT_IN_DEPARTMENT` (membership in another department), `409 MEMBER_NOT_ACTIVE`, `409 DEPARTMENT_ARCHIVED`; `404` if the department is not in the workspace |
| `DELETE /api/v1/departments/{id}/publisher` | OWNER | Idempotent (`204` even when there was none) |
| `PUT /api/v1/documents/{id}/ownership` | OWNER | Transfer responsibility (ADR-009 decision 8). Body `{visibility, ownerDepartmentId, departmentIds}`: `WORKSPACE` → empty `ownerDepartmentId` and `departmentIds`; `DEPARTMENTS` → `ownerDepartmentId` is an `ACTIVE` department within `departmentIds` (`400 OWNER_DEPARTMENT_NOT_IN_SCOPE`, `409 DEPARTMENT_ARCHIVED`). Writes `documents.visibility`, `owner_department_id` and `document_departments` in one transaction (the FK is deferred to commit), then `ACCESS_UPDATED` as for `PUT /visibility` (§2.3). Versions, status and chunks are unchanged. A target scope without a publisher can still receive the document; the response has `publisherAssigned: bool` so the frontend can remind the OWNER to assign one |

`GET /api/v1/members/me` adds `publisherOf: {workspace: bool, departmentId: uuid or null}` so the frontend can show or hide write buttons. The frontend uses it only for display; core-api still checks every request.

### 15.5 Audit

New actions `PUBLISHER_ASSIGNED`, `PUBLISHER_UNASSIGNED` (`target_type` `DEPARTMENT` or `WORKSPACE`, `details: {userId, previousUserId, reason}` with `reason ∈ {OWNER_ACTION, DEPARTMENT_CHANGED, MEMBER_REMOVED}`). The existing `DOCUMENT_*` actions gain `details.ownerDepartmentId` and `details.actingAs ∈ {WORKSPACE_PUBLISHER, DEPARTMENT_PUBLISHER, OWNER}` to record in which capacity the writer acted (`OWNER` appears only on deletes). New action `DOCUMENT_OWNERSHIP_CHANGED` with `details: {from: {visibility, ownerDepartmentId, departmentIds}, to: {...}}`.

### 15.6 Testing

| Layer | Content |
|---|---|
| Unit | The write-permission table: (OWNER, ADMIN, MEMBER) × (is / is not the publisher of the right scope) × the 7 write endpoints + `PUT /ownership`; an OWNER who is not a publisher passes only `DELETE` and `PUT /ownership`; `404` before `403`; `requireCanCreate` with `ownerDepartmentId` missing, outside `departmentIds`, or an `ARCHIVED` department |
| Integration (Testcontainers) | The right publisher can write; another department's publisher writing a shared document (readable) → `403`, an unreadable document → `404`; an ADMIN who is not a publisher → `403` on every write endpoint but can still manage departments and categories; the OWNER reassigns → the old publisher gets `403` and the new one can write on the next request without a refresh; an ADMIN calling the assignment API → `403`; a department move deletes the publisher row; member removal cascades; `fk_documents_owner_in_scope` blocks dropping the owning department; a publisher change concurrent with an upload does not let both through; the OWNER revokes a document of a department without a publisher; the OWNER transfers `DEPARTMENTS → WORKSPACE`, `WORKSPACE → DEPARTMENTS` and changes the owning department: the writer changes on the next request, `current_version_id` and chunks stay, `rag.document_access` is updated; a publisher calling `PUT /visibility` to change the type → `409`, calling `PUT /ownership` → `403` |
| Security (FR-29, reads) | Rerun the §10 read tests: the ADR-007 §4.4 read matrix is unchanged with publishers; publishers read no extra documents outside their department; `owner_department_id` does not appear in `ACCESS_UPDATED`/`INGEST_REQUESTED` payloads; both new tables pass the `tests/tenant-isolation` suite (RLS FORCE, negative control) |

## 16. Implementation notes for V2-30 (2026-11-11, pending owner approval)

Places where the code differs from the specification above. This table wins over the corresponding sections above once the owner approves V2-30's acceptance.

| Item | TECH | Code | Reason |
|---|---|---|---|
| Migration number | V2-36 planned `core/V008` (§15.2) | V2-30 uses `V008__invitation_acceptance.sql`; V2-36 moves to `V009` | V2-30 came first and needs a `SECURITY DEFINER` function to accept invitations (the invitee has no workspace yet to bind RLS to) |
| Accepting an invitation (§5.3) | Lock the row through a definer function | `core.accept_invitation(user, token_hash, invitation_id)` locks `FOR UPDATE`, reads the email from `core.users`, returns a result code; `core.pending_invitations_for_user` for `pendingInvitations` | Two concurrent requests serialize on the invitation row; the email is not taken from the request |
| Accepting an already used link | `409 INVITATION_ALREADY_USED` | The same user accepting again while still a member: `200` (idempotent, tokens reissued); another person, or someone removed from the workspace: `409` | Accepting a link twice must not show an error to the invitee |
| Accepting by `invitationId` | No error code stated | An invitation for another email returns `404`, indistinguishable from not existing | Does not reveal other people's invitations |
| A department `ARCHIVED` after the invitation | No new assignments to an `ARCHIVED` department | The membership is still created but without `department_id`; audit `INVITATION_ACCEPTED` carries `departmentDropped` | The invitee is not blocked by a later admin action |
| An expired, unrevoked invitation | One pending invitation per email | Creating a new invitation for the same email automatically revokes (`revoked_at`) the expired one | The unique index ignores expiry; otherwise an expired link would block re-inviting forever |
| Role read at write time | `wrole` from the token (§5.0) | Member and invitation **write** operations (and the invitation list) read the caller's role from the DB in the transaction (`ACTIVE` and OWNER/ADMIN); `GET /members` and the document read filter still use the token's `wrole`/`wdept` | An owner who was just demoted must not keep acting as OWNER (the same principle as ADR-009 decision 8) |
| Revoking sessions on role change | Not stated | A role change calls `RefreshTokenService.revokeForMembership(..., "MEMBERSHIP_LOST")`; the next refresh returns `401` and the user signs in again to get the new role | The `revoked_reason` constraint has no dedicated value; the constraint is not changed in V2-30 |
| Domain join via `hd` (FR-05) | P1 | **Deferred** | P1 may be deferred with a record, per the ticket; no `workspace_domains` yet |
| CSV invitation import (FR-24) | P1 | **Deferred** | As above; `POST /invitations/import` does not exist yet |
| Sending email | Out of scope | Not sent; the link-creation API always works | Per the ticket |
| `PATCH /members/{userId}` accepts `role` | The "Does not accept `role` yet" row in §13 | Accepts `role` (OWNER/ADMIN/MEMBER) per the §3.2 rules; the §13 row no longer holds | V2-30 does the rest of V2-23 |
| Read window after a role change | Not stated | A role change revokes refresh tokens but not the access token held: a just-demoted person still reads per the old `wrole` for up to 15 minutes (including `DEPARTMENTS` documents and admin fields). Writes/permission changes are unaffected because they read the role from the DB | The same limit as a department move (ADR-007 §4.5) |
| Email at invitation acceptance | `lower(google_email)` | Compared with `core.users.email`, set at first sign-in and never updated | There is no flow to update the Google email yet; an account that changed address must be re-invited with the old address or sign in again with the new account |

## 17. Implementation notes for V2-36 (2026-11-11, pending owner approval)

Places where the code differs from §15. This table wins over the corresponding section once the owner approves V2-36's acceptance.

| Item | TECH §15 | Code | Reason |
|---|---|---|---|
| Migration number | `V008` | `V009__department_publishers.sql` | V2-30 already used `V008` |
| The `suggestion/apply` endpoint | One of the 7 write endpoints | Not in the code (V2-24 has not built it) | `DocumentWritePolicy.requireCanWrite` is ready; add it when the endpoint is written |
| A caller without a department and no `ownerDepartmentId` (§15.3) | `400 VALIDATION_FAILED` | `403 NOT_PUBLISHER` | A person without a department cannot be a department publisher; an ADMIN/OWNER who is not a publisher must get `403` on every write endpoint (ticket) |
| Creating a `DEPARTMENTS` document with an `ARCHIVED` owning department | The department must be `ACTIVE` | `400 VALIDATION_FAILED` on upload (as for an `ARCHIVED` reading scope); `409 DEPARTMENT_ARCHIVED` on `PUT /ownership` | Upload shares V2-24's reading-department list check |
| `Document` fields | Admin fields for the publisher | Adds `ownerDepartment {id, name}` (admin view only) | The frontend needs the owning department to show buttons |
| `GET /documents/{id}/versions` | Adds `uploadedBy`, `uploadedAt` | `uploadedBy {id, displayName}`, `uploadedAt`; **drops `createdAt`** (same value) | Avoids two names for one value |
| Read access to `versions` | OWNER/ADMIN + the responsible publisher | Unreadable document: `404`; readable but not an admin view: `403 FORBIDDEN` | Keeps `404` before `403` |
| `PATCH /members/{userId}` changing department | Delete publisher rows for departments other than the new one | In the same transaction, with audit `PUBLISHER_UNASSIGNED` reason `DEPARTMENT_CHANGED`; the workspace publisher is kept | Per §15.3 |
| `GET /members/me` | `publisherOf` | `publisherOf: {workspace, departmentId}` at the same level as the profile (`@JsonUnwrapped`) | Keeps the old response compatible |
| Locking when assigning a publisher | Lock the publisher row | Assigning a publisher also locks the assignee's membership row `FOR SHARE` | A concurrent department move must not leave a publisher row for the old department (an FK only locks the key, it does not wait for updates of ordinary columns); two concurrency tests |
| Reading list when the owning department is `ARCHIVED` | The publisher can still edit and delete | `PUT /visibility` must keep the owning department, and `ARCHIVED` departments are refused in the list, so the publisher cannot change that document's reading list. Returns `409 OWNER_DEPARTMENT_ARCHIVED` with a message explaining the cause and the way out (the OWNER moves the document with `PUT /ownership` or restores the department). Owner decision 2026-11-11: keep the behaviour, only clarify the message | Safe (nobody gains read access), rare, with a way out; not worth an exception for `ARCHIVED` departments in the list |
| `V009` backfill | Assign `owner_department_id` | Stops with a clear message if a `DEPARTMENTS` document has no department; temporarily disables the `updated_at` trigger during the backfill | The migration must not break on the CHECK, and must not change `updated_at` of every department document |
