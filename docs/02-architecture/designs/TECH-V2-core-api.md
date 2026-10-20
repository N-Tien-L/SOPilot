---
id: TECH-V2-CORE-API
title: "Thiết kế kỹ thuật core-api (V2): danh tính, workspace, thành viên, tài liệu, outbox"
status: approved
created: 2026-10-20
updated: 2026-10-21
refs:
  - docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md
  - docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - docs/02-architecture/designs/TECH-V2-ai-service.md
author: "Owner"
affected_services: [core-api, ai-service, frontend/web]
affected_schemas: [core]
---

# THIẾT KẾ KỸ THUẬT: core-api (V2)

> **Mã tài liệu:** `TECH-V2-CORE-API` | **Tham chiếu PRD:** `PRD-V2-SOPILOT-MVP` | **Trạng thái:** `approved` (owner duyệt 2026-10-20, V2-03; câu hỏi mở chốt ở §11)
>
> Tài liệu đi cặp với [TECH-V2-ai-service](TECH-V2-ai-service.md). Phần contract giữa hai service (§8) là nguồn chung; TECH-V2-ai-service chỉ dẫn lại, không định nghĩa lại.
>
> **Sửa 2026-10-21 (owner, [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md)):** bỏ TXT (§3.3, §5.5); quy tắc bản thay thế khi đang xử lý (§3.3, §11 Q7); hạn mức tài liệu mặc định 50/200 MB (§3.3, §9, §11 Q6); `attempt` trong payload ingest và callback để thử lại chạy thật (§5.5, §8); `warningCodes` và `latestVersion` cho màn xem FR-31 (§5.5, §8.2).

---

## 0. Phạm vi và quy ước

- core-api là service Spring Boot 3.x, Java 21 (PRD §8.1), viết mới ở `services/core-api`. Mã cũ (`auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`) chỉ để tham khảo và port có chọn lọc (ADR-004 §4.5).
- core-api là chủ duy nhất của schema `core` và là service duy nhất ghi `core.users` (sửa A7).
- Mọi bảng nghiệp vụ có `workspace_id` và bật RLS (ADR-005, ADR-007). Bảng toàn cục (`users`, `external_identities`) không có `workspace_id` và không bật RLS.
- Không có gateway, RabbitMQ hay Redis (ADR-004). Việc bất đồng bộ đi qua outbox Postgres.
- Thuật ngữ: **wid** = workspace đang hoạt động trong token; **wrole** = role trong workspace đó; **wdept** = phòng ban của membership hoặc rỗng.

### Truy vết tới yêu cầu

| Yêu cầu | Mục |
|---|---|
| FR-01, FR-02, A8, A9 | §3.1, §5.1 |
| FR-03 | §5.2 |
| FR-04, FR-22, UC-02, UC-07 | §3.2, §5.3 |
| FR-05 (P1) | §3.2, §5.3 |
| FR-23, UC-08 | §5.4 |
| FR-24 (P1) | §5.3 |
| FR-06, FR-07, UC-04 | §3.3, §5.5, §7 |
| FR-25, FR-26, FR-27, UC-09, UC-10, UC-11 | §3.4, §5.6, §8 |
| FR-28 (phần lưu và áp dụng gợi ý) | §5.6, §8.3 |
| FR-09 (hạn mức tài liệu, mặc định 50 tài liệu/200 MB từ 2026-10-21) | §3.3, §9 |
| FR-30 (chọn nhiều file) | §5.5 |
| FR-31 (màn xem nội dung nhận diện: nhãn phiên bản, mã cảnh báo) | §3.3, §5.5, §8.2 |
| FR-20 | §3.6, §5.7 |
| FR-16, FR-17 | TECH-V2-ai-service §7.6 (§11 Q1) |
| NFR cách ly tenant, FR-19, FR-29 | §4, §10 |

---

## 1. Tổng quan kiến trúc và thành phần bị ảnh hưởng

| Thành phần | Công nghệ | Ranh giới | Bản chất thay đổi |
|---|---|---|---|
| `services/core-api` | Spring Boot 3.x, Java 21, Spring Data JPA + JdbcTemplate, Flyway client | Schema `core`, object storage | Service mới |
| `infrastructure/db/migrations/core/` | Flyway, PostgreSQL 16 | Schema `core` | Chuỗi migration mới (V2-08) |
| Object storage | MinIO ghim phiên bản (local, CI) | Một bucket, tên lấy từ env | Dùng qua API S3 chuẩn |
| `services/ai-service` | FastAPI | Schema `rag` | Nhận job ingest, cập nhật quyền, gọi lại trạng thái (§8) |
| `frontend/web` | Next.js | — | Gọi `/api/**` (core-api) và `/ai/**` (ai-service) trên cùng origin |

### 1.1 Một origin cho trình duyệt

Môi trường V2 chỉ chạy local bằng `docker compose` (PRD §8.2). Next.js `rewrites` định tuyến:

| Đường dẫn trình duyệt | Đích |
|---|---|
| `/api/**`, `/.well-known/jwks.json` | `core-api:8080` |
| `/ai/**` | `ai-service:8000` |

Hệ quả: không cần CORS; cookie refresh dùng `SameSite=Strict`. Rủi ro đã biết: proxy của Next.js có thể đệm SSE. V2-15 phải kiểm tra stream đi qua rewrites từng token; nếu bị đệm thì thêm container Caddy làm reverse proxy (không đổi contract API).

`/internal/**` của cả hai service **không** được rewrite ra ngoài. Hai service gọi nhau bằng tên container trên network compose.

### 1.2 Cấu trúc module (modular monolith)

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

Package Java mới là `com.sopilot.core`. Không tái dùng `com.poliwise.*` cho code mới; mã cũ giữ nguyên tên package tới khi bị gỡ (V2-17).

---

## 2. Sơ đồ tuần tự

### 2.1 Đăng nhập Google lần đầu (UC-01, FR-01, FR-02)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (Next.js)
    participant G as Google Identity Services
    participant C as core-api
    participant DB as Postgres (core)

    B->>C: POST /api/v1/auth/google/nonce
    C-->>B: 200 {nonce} + Set-Cookie sp_nonce=<HMAC(nonce, exp)> (HttpOnly, 5 phút)
    B->>G: Hiện nút Sign in with Google (nonce)
    G-->>B: ID token (JWT RS256)
    B->>C: POST /api/v1/auth/google {idToken} + cookie sp_nonce
    C->>C: Xác minh chữ ký JWKS Google, iss, aud, exp, email_verified, nonce khớp cookie
    C->>DB: BEGIN; tìm external_identities theo (issuer, sub)
    alt Chưa có user
        C->>DB: INSERT users, external_identities (ON CONFLICT DO NOTHING rồi đọc lại)
        C->>DB: INSERT workspaces(kind=PERSONAL), memberships(OWNER, ACTIVE)
    end
    C->>DB: Áp dụng lời mời qua link (nếu có invitationToken) / domain join (P1)
    C->>DB: Chọn workspace: lời mời vừa nhận > last_active_workspace_id > PERSONAL
    C->>DB: INSERT refresh_tokens (hash, family_id, workspace_id); INSERT audit_logs(LOGIN); COMMIT
    C-->>B: 200 {accessToken, expiresIn, workspace} + Set-Cookie sp_refresh (HttpOnly, Secure, SameSite=Strict, Path=/api/v1/auth)
```

### 2.2 Upload tới `READY` (UC-04, FR-06, FR-07, FR-08)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant C as core-api
    participant S3 as Object storage
    participant DB as Postgres (core)
    participant A as ai-service

    B->>C: POST /api/v1/documents (multipart, Bearer wid/wrole)
    C->>C: Kiểm tra wrole ∈ {OWNER, ADMIN}, loại file, ≤ 20 MB, tính SHA-256 khi stream
    C->>S3: PUT workspaces/{wid}/documents/{docId}/versions/{verId}
    C->>DB: BEGIN; SET LOCAL app.workspace_id; khóa advisory (wid, sha256)
    C->>DB: Kiểm tra trùng SHA-256 với tài liệu khác; khóa advisory theo workspace và kiểm tra hạn mức tài liệu (mặc định 50/200 MB)
    C->>DB: INSERT documents, document_versions(UPLOADED), outbox(INGEST_REQUESTED), audit_logs; COMMIT
    C-->>B: 201 {document, version.status=UPLOADED}
    C->>A: (sau commit, outbox) POST /internal/ingestions
    A-->>C: 202 (ghi rag.document_access + rag.ingestion_jobs trong một transaction)
    A->>C: PATCH /internal/documents/{id}/versions/{verId}/status {PROCESSING}
    A->>C: PATCH ... {READY, pageCount, language, extracted, warningCodes}
    C->>DB: version READY, documents.current_version_id = verId, bản cũ SUPERSEDED
```

Nếu xóa object S3 thất bại sau khi transaction rollback, object mồ côi được dọn bởi job `StorageJanitor` (so khóa object với `document_versions`, chạy mỗi giờ). Không có trường hợp row DB trỏ tới object chưa ghi xong, vì PUT S3 diễn ra trước commit.

### 2.3 Đổi phạm vi hiển thị (UC-11, FR-25)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant C as core-api
    participant DB as Postgres (core)
    participant A as ai-service

    B->>C: PUT /api/v1/documents/{id}/visibility {visibility: DEPARTMENTS, departmentIds}
    C->>DB: BEGIN; cập nhật documents.visibility, document_departments; outbox(ACCESS_UPDATED, access_revision+1); audit; COMMIT
    C->>A: PUT /internal/document-access/{id} (gọi đồng bộ ngay sau commit, timeout 2 s)
    alt ai-service nhận
        A-->>C: 200 (chỉ áp dụng nếu access_revision mới hơn bản đang có)
        C->>DB: outbox DELIVERED
        C-->>B: 200 {accessSync: "APPLIED"}
    else Lỗi hoặc timeout
        C-->>B: 200 {accessSync: "PENDING"}
        Note over C,A: OutboxDispatcher thử lại với backoff tới khi ai-service nhận
    end
```

---

## 3. Thiết kế dữ liệu (schema `core`)

- **Migration:** `infrastructure/db/migrations/core/V0xx__*.sql`, Flyway với bảng lịch sử riêng `core.flyway_schema_history` (ADR-004 §4.4). Khung Flyway, role và compose thuộc V2-08.
- **Kiểu chung:** khóa chính `uuid` sinh ở ứng dụng (UUIDv7 để chèn theo thứ tự thời gian); thời gian `timestamptz`; email lưu dạng `citext` hoặc chữ thường + `CHECK (email = lower(email))`. Dùng `text` thay `varchar(n)` trừ khi giới hạn có nghĩa nghiệp vụ.
- **FK:** chỉ trong schema `core`. Không FK sang `rag`.
- Mỗi bảng có `updated_at` dùng chung trigger `core.touch_updated_at()`.
- DDL dưới đây nhóm theo chủ đề, không theo thứ tự chạy. Migration phải tạo `core.categories` trước `core.documents` (FK `category_id`).

### 3.1 Danh tính (toàn cục, không RLS)

```sql
CREATE TABLE core.users (
    id                       uuid PRIMARY KEY,
    email                    text NOT NULL CHECK (email = lower(email)),
    display_name             text,
    avatar_url               text,
    last_active_workspace_id uuid,            -- không FK để tránh vòng phụ thuộc khi xóa workspace
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
-- email không unique: định danh là (issuer, subject); email chỉ là thuộc tính (ADR-005 §4.1).

CREATE TABLE core.external_identities (          -- port từ init-db/012_google_identities.sql
    id            uuid PRIMARY KEY,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    issuer        text NOT NULL CHECK (length(trim(issuer)) > 0),
    subject       text NOT NULL CHECK (length(trim(subject)) > 0),
    email_at_link text NOT NULL,
    hosted_domain text,                           -- claim hd lúc liên kết gần nhất
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_external_identity_user UNIQUE (user_id, issuer)
);

CREATE TABLE core.refresh_tokens (
    id             uuid PRIMARY KEY,
    user_id        uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    workspace_id   uuid NOT NULL,                 -- workspace của access token sẽ được cấp
    family_id      uuid NOT NULL,                 -- chuỗi xoay vòng; dùng lại token cũ thì thu hồi cả chuỗi
    token_hash     bytea NOT NULL UNIQUE,         -- SHA-256 của token ngẫu nhiên 256 bit
    expires_at     timestamptz NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    used_at        timestamptz,                   -- đã đổi sang token mới
    revoked_at     timestamptz,
    revoked_reason text CHECK (revoked_reason IN ('LOGOUT','REUSE_DETECTED','MEMBERSHIP_LOST','SUSPENDED','EXPIRED_FAMILY'))
);
CREATE INDEX ix_refresh_tokens_family ON core.refresh_tokens(family_id);
```

`refresh_tokens.workspace_id` không bật RLS: bảng chỉ được đọc theo `token_hash` trong luồng refresh, trước khi biết workspace. Không có cột thiết bị/IP (quản lý phiên ngoài phạm vi, PRD §5).

### 3.2 Workspace, thành viên, lời mời, phòng ban

```sql
CREATE TABLE core.workspaces (
    id         uuid PRIMARY KEY,
    name       text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    kind       text NOT NULL CHECK (kind IN ('PERSONAL','TEAM')),
    created_by uuid NOT NULL REFERENCES core.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- Mỗi user đúng một workspace PERSONAL (FR-02, idempotent).
CREATE UNIQUE INDEX uq_personal_workspace ON core.workspaces(created_by) WHERE kind = 'PERSONAL';

CREATE TABLE core.departments (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)                     -- cho FK hai cột: phòng ban phải cùng workspace
);
CREATE UNIQUE INDEX uq_department_name ON core.departments(workspace_id, lower(name));

CREATE TABLE core.memberships (
    workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    role          text NOT NULL CHECK (role IN ('OWNER','ADMIN','MEMBER')),
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED')),
    display_name  text,
    email         text NOT NULL CHECK (email = lower(email)),  -- email lúc gia nhập, hiển thị trong danh sách
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
    role          text NOT NULL CHECK (role IN ('ADMIN','MEMBER')),   -- không mời thẳng làm OWNER
    display_name  text,
    employee_code text,
    job_title     text,
    department_id uuid,
    token_hash    bytea NOT NULL UNIQUE,
    invited_by    uuid NOT NULL REFERENCES core.users(id),
    expires_at    timestamptz NOT NULL,                               -- created_at + 7 ngày
    accepted_at   timestamptz,
    accepted_by   uuid REFERENCES core.users(id),
    revoked_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT
);
-- Một lời mời đang chờ cho mỗi email trong workspace.
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

Quy tắc không biểu diễn được bằng ràng buộc (kiểm tra ở service, trong transaction có `SELECT ... FOR UPDATE` trên các membership OWNER của workspace):
- Luôn còn ít nhất một `OWNER` có `status = 'ACTIVE'`.
- ADMIN không đổi role, tạm khóa hay xóa OWNER, và không nâng ai lên OWNER.
- Không gán mới vào phòng ban `ARCHIVED` (membership, lời mời).
- Workspace `PERSONAL` không đổi `kind`, không xóa được khi là workspace duy nhất của user.

### 3.3 Tài liệu và phiên bản

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
    language           text,                                   -- BCP-47 ngắn: 'vi', 'en'
    language_source    text NOT NULL DEFAULT 'SYSTEM' CHECK (language_source IN ('SYSTEM','SUGGESTED','USER')),
    visibility         text NOT NULL DEFAULT 'WORKSPACE' CHECK (visibility IN ('WORKSPACE','DEPARTMENTS')),
    access_revision    bigint NOT NULL DEFAULT 1,              -- tăng mỗi lần đổi phạm vi; ai-service bỏ qua bản cũ hơn
    current_version_id uuid,                                   -- phiên bản READY đang dùng để hỏi đáp
    latest_version_id  uuid,                                   -- phiên bản mới nhất (có thể đang xử lý)
    created_by         uuid NOT NULL REFERENCES core.users(id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    deleted_at         timestamptz,                            -- xóa mềm trong lúc chờ ai-service xóa chunk
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
    failure_message  text,                                     -- câu hiển thị cho người dùng, không chứa stack trace
    original_name    text NOT NULL,
    mime_type        text NOT NULL,
    file_type        text NOT NULL CHECK (file_type IN ('PDF','MD')),   -- TXT bỏ khỏi MVP 2026-10-21
    size_bytes       bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 20971520),
    sha256           bytea NOT NULL,
    object_key       text NOT NULL UNIQUE,
    page_count       int,
    detected_language text,
    doc_code         text,                                     -- mã số trích từ nội dung (V2-21)
    revision_label   text,                                     -- lần ban hành
    effective_date   date,
    embedding_model  text,                                     -- nguồn gốc embedding ai-service báo về
    embedding_revision text,
    chunk_count      int,
    warning_codes    text[] NOT NULL DEFAULT '{}',              -- mã cảnh báo trích xuất ai-service báo về (TECH-V2-ai-service §5.3a)
    attempt          int NOT NULL DEFAULT 0,                    -- tăng mỗi lần retry; gửi trong payload ingest để ai-service phân biệt thử lại với gửi lặp
    uploaded_by      uuid NOT NULL REFERENCES core.users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    processed_at     timestamptz,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_no),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_document_versions_sha ON core.document_versions(workspace_id, sha256);
```

Ghi chú:
- **Chặn trùng (FR-06, V2-12):** chỉ so SHA-256 với **phiên bản hiện hành của tài liệu khác** (`document_id <> :id`, `status <> 'SUPERSEDED'`, tài liệu chưa xóa). Không dùng unique index vì các phiên bản cũ đã `SUPERSEDED` của cùng tài liệu có thể trùng nhau. Chống race bằng `pg_advisory_xact_lock(hashtextextended(wid || sha256_hex, 0))`. Trùng thì `409 DUPLICATE_DOCUMENT` kèm `{documentId, title}` của tài liệu đã có (chỉ khi người gọi có quyền đọc tài liệu đó; OWNER/ADMIN luôn đọc được).
- **Quy tắc bản thay thế (FR-07, owner chốt 2026-10-20 và 2026-10-21),** xét theo thứ tự trong cùng transaction và advisory lock của tài liệu, `POST /documents/{id}/versions`:
  1. `latest_version_id` đang `UPLOADED`/`PROCESSING` và cùng SHA-256 → `200` trả phiên bản đó (gửi lặp cùng thao tác, không tạo phiên bản, outbox hay job).
  2. `latest_version_id` đang `UPLOADED`/`PROCESSING`, khác SHA-256 → `409 VERSION_IN_PROGRESS`. Lý do: hai phiên bản xử lý song song có thể kích hoạt sai thứ tự (bản cũ hơn `READY` sau bản mới hơn).
  3. Cùng SHA-256 với `current_version_id` (`READY`) → `409 DOCUMENT_UNCHANGED`, không ghi S3, không tạo phiên bản, outbox hay job.
  4. Cùng SHA-256 với phiên bản hiện hành của **tài liệu khác** → `409 DUPLICATE_DOCUMENT` như khi tạo mới.
  5. Ngược lại → tạo phiên bản mới. Không so sánh với phiên bản `FAILED`: tải lại đúng file của bản lỗi tạo phiên bản mới, tương đương thử lại. File khác bytes luôn được nhận dù nội dung gần giống; không dùng hash của Markdown hay so ngữ nghĩa.
- **Thay bản mới (FR-07):** `current_version_id` chỉ đổi khi bản mới `READY`; khi đó **mọi** phiên bản cũ hơn của tài liệu (kể cả `FAILED`) chuyển `SUPERSEDED` và ai-service đã xóa chunk của bản trước trong cùng transaction kích hoạt (TECH-V2-ai-service §5.6). Bản mới `FAILED` thì bản cũ vẫn phục vụ.
- **Trạng thái tài liệu hiển thị** = trạng thái của `latest_version_id`; tài liệu "hỏi đáp được" khi `current_version_id IS NOT NULL`.
- **Hạn mức (FR-09, owner chốt 2026-10-21: mặc định bật):** `SOPILOT_QUOTA_DOCS_PER_WORKSPACE=50`, `SOPILOT_QUOTA_BYTES_PER_WORKSPACE=209715200` (`0` = không giới hạn, bỏ qua bước đếm; eval hoặc demo lớn đặt `0`). Đếm tài liệu chưa xóa và tổng `size_bytes` của phiên bản không `SUPERSEDED` trong cùng transaction với `pg_advisory_xact_lock` theo workspace, nên N upload đồng thời không vượt hạn mức. Vượt thì `409 QUOTA_EXCEEDED` kèm `{limit, used}`; object S3 đã ghi được xóa ngay (lỗi thì `StorageJanitor` dọn). Phiên bản thay thế không tăng số tài liệu; dung lượng của nó được tính tạm cùng bản hiện hành cho tới khi bản cũ `SUPERSEDED`. Nâng hạn mức không đồng nghĩa hệ thống xử lý được kho lớn (chưa đo).
- **Khóa object:** `workspaces/{wid}/documents/{docId}/versions/{verId}`; tên file gốc chỉ lưu trong DB.

### 3.4 Phạm vi hiển thị, category, tags (ADR-007, FR-25..27)

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

-- Gợi ý metadata (FR-28) lưu riêng; chỉ áp dụng vào trường có nguồn khác USER.
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

Ràng buộc "`DEPARTMENTS` phải có ≥ 1 phòng ban" kiểm tra trong service khi ghi (cùng transaction) và bằng constraint trigger `DEFERRABLE INITIALLY DEFERRED` kiểm tra lúc commit. Category `ARCHIVED` không gán mới được; xóa category đưa tài liệu về "chưa phân loại" (`ON DELETE SET NULL (category_id)`, cần PostgreSQL ≥ 15) và không ảnh hưởng quyền.

### 3.5 Outbox

```sql
CREATE TABLE core.outbox_events (
    id             uuid PRIMARY KEY,                -- cũng là khóa idempotency gửi sang ai-service
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
    actor_id     uuid,                -- null nếu do hệ thống
    action       text NOT NULL,       -- LOGIN, MEMBER_INVITED, MEMBER_JOINED, MEMBER_ROLE_CHANGED, MEMBER_DEPARTMENT_CHANGED,
                                      -- MEMBER_SUSPENDED, MEMBER_REACTIVATED, MEMBER_REMOVED, MEMBER_PROFILE_UPDATED,
                                      -- DEPARTMENT_CREATED/RENAMED/ARCHIVED/DELETED, DOCUMENT_UPLOADED, DOCUMENT_VERSION_UPLOADED,
                                      -- DOCUMENT_DELETED, DOCUMENT_VISIBILITY_CHANGED, WORKSPACE_*
    target_type  text,
    target_id    uuid,
    details      jsonb NOT NULL DEFAULT '{}',   -- trước/sau; không chứa token, nội dung tài liệu
    trace_id     text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_workspace_time ON core.audit_logs(workspace_id, created_at DESC);
```

`LOGIN` ghi vào workspace được chọn khi đăng nhập. Audit ghi cùng transaction với thay đổi. Bảng chỉ INSERT: role ứng dụng không có quyền `UPDATE`, `DELETE` trên `core.audit_logs`.

---

## 4. Cách ly tenant: RLS và quản lý connection

### 4.1 Role database

| Role | Dùng bởi | Quyền |
|---|---|---|
| `sopilot_migrator` | Flyway (container chạy một lần) | Owner schema `core` và `rag` |
| `sopilot_core_app` | core-api | `SELECT/INSERT/UPDATE/DELETE` trên bảng `core` (trừ `audit_logs` chỉ `INSERT/SELECT`); không quyền trên `rag`; không owner bảng; `NOBYPASSRLS` |
| `sopilot_ai_app` | ai-service | Như trên nhưng chỉ schema `rag` |

Hai role ứng dụng tách schema ở mức database, nên "mỗi service chỉ ghi schema của mình" được kiểm tra bởi Postgres, không chỉ bằng quy ước. Mật khẩu lấy từ `.env` (V2-08).

### 4.2 Policy

Mọi bảng có `workspace_id` bật `ENABLE` và `FORCE ROW LEVEL SECURITY`. Hai biến phiên, đặt bằng `set_config(..., true)` (tương đương `SET LOCAL`) ở đầu mỗi transaction:

```sql
CREATE FUNCTION core.current_workspace() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$;
CREATE FUNCTION core.current_app_user() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

-- Mẫu cho bảng nghiệp vụ thông thường (documents, document_versions, departments, categories, tags,
-- document_tags, document_departments, document_suggestions, invitations, audit_logs, workspace_domains):
CREATE POLICY tenant_isolation ON core.documents
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

-- memberships: thấy membership trong workspace hiện tại, hoặc membership của chính mình ở mọi workspace
-- (để liệt kê "workspace của tôi" và chọn workspace khi đăng nhập).
CREATE POLICY membership_visibility ON core.memberships
    USING (workspace_id = core.current_workspace() OR user_id = core.current_app_user())
    WITH CHECK (workspace_id = core.current_workspace());

-- workspaces: workspace hiện tại, hoặc workspace mình là thành viên.
CREATE POLICY workspace_visibility ON core.workspaces
    USING (id = core.current_workspace()
           OR EXISTS (SELECT 1 FROM core.memberships m WHERE m.workspace_id = id AND m.user_id = core.current_app_user()))
    WITH CHECK (id = core.current_workspace());
```

Biến chưa đặt thì hàm trả `NULL`, so sánh trả `NULL`, không có dòng nào (fail closed).

**Những truy vấn bắt buộc vượt workspace** được gói trong hàm `SECURITY DEFINER` do `sopilot_migrator` sở hữu, có `SET search_path = core, pg_temp`, chỉ trả đúng cột cần, và chỉ `GRANT EXECUTE` cho `sopilot_core_app`:

| Hàm | Dùng khi |
|---|---|
| `core.find_invitation_by_token_hash(bytea)` | Chấp nhận lời mời trước khi biết workspace |
| `core.find_pending_invitations_by_email(text)` | Hiện lời mời đang chờ sau đăng nhập |
| `core.find_domain_workspaces(text)` | Domain join (P1) |
| `core.claim_outbox_batch(int)` | Dispatcher lấy việc của mọi workspace (`FOR UPDATE SKIP LOCKED`) |
| `core.create_personal_workspace(uuid user, text name, text email)` | JIT: tạo workspace + membership OWNER khi chưa có `wid` |

### 4.3 Đặt biến trong Spring

- `TenantContext` (request scope) giữ `userId`, `workspaceId` lấy từ access token đã xác minh, **không bao giờ** từ body hay query.
- `TenantTransactionListener` móc vào `TransactionSynchronizationManager` (hoặc `DataSource` proxy) để chạy `SELECT set_config('app.workspace_id', ?, true), set_config('app.user_id', ?, true)` ngay sau `BEGIN` của mọi transaction. Không có transaction thì không truy vấn được bảng RLS (controller gọi service `@Transactional`).
- Vì dùng `is_local = true`, giá trị mất khi transaction kết thúc; connection trả về pool không mang theo workspace cũ. FR-19 có test riêng cho điều này (§10).
- Job nền (outbox, janitor) đặt `app.workspace_id` theo từng sự kiện trước khi đọc/ghi bảng nghiệp vụ.

---

## 5. Hợp đồng API công khai (`/api/v1`)

### 5.0 Quy ước chung

- Header: `Authorization: Bearer <access token>` (trừ các endpoint auth công khai); `X-Trace-Id` tùy chọn, core-api sinh nếu thiếu và trả lại trong response.
- Thành công: `{"data": ..., "traceId": "..."}`. Danh sách: `{"data": [...], "page": {"cursor": "...", "hasMore": true}}` (phân trang theo cursor).
- Lỗi: `{"error": {"code": "DUPLICATE_DOCUMENT", "message": "<câu cho người dùng>", "details": {...}}, "traceId": "..."}`. Không bao giờ trả `e.getMessage()` của exception nội bộ (A8); lỗi không lường trước trả `500 INTERNAL_ERROR` với message cố định, chi tiết chỉ nằm trong log kèm `traceId`.
- Mã HTTP: `400 VALIDATION_FAILED`, `401 UNAUTHENTICATED`, `403 FORBIDDEN` (thiếu role trên tài nguyên mình được thấy), `404 NOT_FOUND` (không tồn tại **hoặc** ngoài quyền đọc, để không lộ tên, ADR-007 / V2-24), `409` (xung đột nghiệp vụ), `413 FILE_TOO_LARGE`, `415 UNSUPPORTED_TYPE`, `422 QUOTA_EXCEEDED`, `429 RATE_LIMITED`.
- Role trong cột "Quyền" đọc từ `wrole` của token; mọi endpoint (trừ auth) yêu cầu membership `ACTIVE`. `SUSPENDED` không lấy được token (§5.2).

### 5.1 Xác thực

| Method & path | Quyền | Mục đích |
|---|---|---|
| `POST /api/v1/auth/google/nonce` | Public | Phát nonce cho Google Identity Services |
| `POST /api/v1/auth/google` | Public | Đăng nhập bằng ID token Google |
| `POST /api/v1/auth/refresh` | Cookie refresh | Xoay vòng refresh, cấp access token mới |
| `POST /api/v1/auth/switch-workspace` | Đã đăng nhập | Cấp token cho workspace khác |
| `POST /api/v1/auth/logout` | Cookie refresh | Thu hồi chuỗi refresh hiện tại |
| `POST /api/v1/auth/dev-login` | Public, chỉ profile `local`/`test` | Đăng nhập không cần Google cho test và eval |
| `GET /.well-known/jwks.json` | Public | Public key RS256 cho ai-service |

**`POST /api/v1/auth/google/nonce`** → `200 {"data": {"nonce": "<base64url 128 bit>"}}` và `Set-Cookie: sp_nonce=<nonce>.<exp>.<HMAC-SHA256>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=300`. Không lưu DB.

**`POST /api/v1/auth/google`**

```json
// Request
{ "idToken": "<Google ID token>", "invitationToken": "<tùy chọn, từ link mời>" }
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

Kiểm tra theo thứ tự, port từ `GoogleTokenVerifierService` và bổ sung `nonce` (A9): chữ ký qua JWKS của Google (cache theo `Cache-Control`), `iss ∈ {accounts.google.com, https://accounts.google.com}`, `aud = GOOGLE_CLIENT_ID`, `exp` (lệch giờ tối đa 60 s), `email_verified = true`, `nonce` khớp cookie `sp_nonce` còn hạn và HMAC đúng. Sai bất kỳ bước nào → `401 INVALID_GOOGLE_TOKEN` với message chung; lý do cụ thể chỉ ghi log. Xóa cookie `sp_nonce` sau khi dùng.

`invitationToken` có thì áp dụng lời mời (§5.3) trong cùng transaction; email không khớp → vẫn đăng nhập thành công vào workspace mặc định, response kèm `"invitationError": "EMAIL_MISMATCH"`, lời mời giữ nguyên (UC-02).

**Access token** (RS256, `kid` theo cặp khóa, hạn `SOPILOT_ACCESS_TTL=PT15M`):

```json
{
  "iss": "sopilot-core", "aud": ["sopilot-core", "sopilot-ai"],
  "sub": "<user id>", "wid": "<workspace id>", "wrole": "OWNER|ADMIN|MEMBER",
  "wdept": "<department id hoặc null>", "jti": "<uuid>", "iat": 0, "exp": 0
}
```

Không đưa email hay tên vào token. Khóa ký đọc từ file PEM mount qua env (`SOPILOT_JWT_PRIVATE_KEY_PATH`); profile `local`/`test` tự sinh cặp khóa khi thiếu. JWKS công bố khóa hiện hành và khóa trước đó để xoay khóa không làm rớt phiên.

**Refresh token:** chuỗi ngẫu nhiên 256 bit, base64url, chỉ lưu SHA-256. Cookie `sp_refresh; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, hạn `SOPILOT_REFRESH_TTL=P14D`. Port logic xoay vòng và phát hiện dùng lại từ `RefreshTokenService` cũ:

1. Tìm token theo hash, `FOR UPDATE`. Không có hoặc hết hạn → `401`.
2. Token đã `used_at` hoặc `revoked_at` → **dùng lại**: thu hồi cả `family_id` (`REUSE_DETECTED`), trả `401`.
3. Đọc lại membership của `(workspace_id, user_id)`: không còn → thu hồi chuỗi (`MEMBERSHIP_LOST`), `401 MEMBERSHIP_LOST`; `SUSPENDED` → thu hồi chuỗi (`SUSPENDED`), `403 MEMBERSHIP_SUSPENDED`. Frontend chuyển người dùng sang chọn workspace khác.
4. Đánh dấu token cũ `used_at`, phát token mới cùng `family_id`, access token mang `wrole`/`wdept` **đọc lại từ DB** (ADR-007 §4.5).

Request refresh/logout phải có header `Origin` bằng origin của frontend; sai → `403`. Đây là lớp chống CSRF thứ hai cạnh `SameSite=Strict`.

**`POST /api/v1/auth/switch-workspace`** `{ "workspaceId": "…" }` → kiểm tra membership `ACTIVE`, thu hồi refresh hiện tại, phát cặp token mới cho workspace đó, cập nhật `users.last_active_workspace_id`. `404` nếu không là thành viên.

**`POST /api/v1/auth/dev-login`** `{ "email": "...", "displayName": "..." }`: bean chỉ tồn tại với `@Profile({"local","test"})`; ở profile khác endpoint trả `404` vì không được đăng ký. Tạo identity với `issuer = "sopilot-dev"`, `subject = email`, rồi đi cùng luồng JIT như Google.

### 5.2 Workspace (FR-03)

| Method & path | Quyền | Ghi chú |
|---|---|---|
| `GET /api/v1/workspaces` | Đã đăng nhập | Workspace của tôi (membership `ACTIVE` hoặc `SUSPENDED`, kèm trạng thái) |
| `POST /api/v1/workspaces` | Đã đăng nhập | Tạo workspace `TEAM`, người tạo là OWNER; response gồm token cho workspace mới |
| `GET /api/v1/workspaces/current` | Thành viên | Chi tiết workspace của `wid`, số tài liệu, dung lượng đã dùng |
| `PATCH /api/v1/workspaces/current` | OWNER | Đổi tên |
| `DELETE /api/v1/workspaces/current` | OWNER | Xóa workspace: xóa mềm, outbox `DOCUMENT_DELETED` cho từng tài liệu, xóa cứng khi ai-service xác nhận hết |
| `PUT /api/v1/workspaces/current/domains/{domain}` | OWNER có `hd = domain` | P1, FR-05 |
| `DELETE /api/v1/workspaces/current/domains/{domain}` | OWNER | P1 |

Mọi endpoint quản trị thao tác trên `wid` của token (`/current`), không nhận `workspaceId` trên path. Điều này loại bỏ cả lớp lỗi IDOR giữa workspace.

### 5.3 Thành viên và lời mời (FR-04, FR-22, FR-05, FR-24)

| Method & path | Quyền | Ghi chú |
|---|---|---|
| `GET /api/v1/members` | OWNER, ADMIN | Lọc `status`, `departmentId`, tìm theo tên/email/mã nhân viên. MEMBER chỉ thấy hồ sơ của chính mình qua `GET /api/v1/members/me` |
| `GET /api/v1/members/me` | Thành viên | Hồ sơ của tôi trong workspace |
| `PATCH /api/v1/members/{userId}` | OWNER, ADMIN | Sửa `displayName`, `employeeCode`, `jobTitle`, `departmentId`, `role` (theo quy tắc §3.2) |
| `POST /api/v1/members/{userId}/suspend` | OWNER, ADMIN (ADMIN không khóa OWNER) | Thu hồi mọi refresh của user cho workspace này |
| `POST /api/v1/members/{userId}/reactivate` | OWNER, ADMIN | |
| `DELETE /api/v1/members/{userId}` | OWNER, ADMIN | Xóa khỏi workspace; hội thoại giữ lại (ADR-007 §4.2) |
| `POST /api/v1/members/leave` | Thành viên | Rời workspace; OWNER cuối cùng không rời được (`409 LAST_OWNER`) |
| `GET /api/v1/invitations` | OWNER, ADMIN | Lời mời đang chờ |
| `POST /api/v1/invitations` | OWNER, ADMIN | Tạo lời mời; trả `inviteUrl` **một lần duy nhất** |
| `DELETE /api/v1/invitations/{id}` | OWNER, ADMIN | Thu hồi |
| `POST /api/v1/invitations/accept` | Đã đăng nhập | `{invitationToken}` hoặc `{invitationId}` (lời mời theo email hiện ở `pendingInvitations`) |
| `POST /api/v1/invitations/import` | OWNER, ADMIN | P1, CSV; trả lỗi theo dòng |

`POST /api/v1/invitations`:

```json
// Request
{ "email": "binh@acme.com", "role": "MEMBER", "displayName": "Bình",
  "departmentId": "…", "employeeCode": "NV-012", "jobTitle": "Kế toán" }
// 201
{ "data": { "id": "…", "expiresAt": "2026-10-27T10:00:00Z",
            "inviteUrl": "http://localhost:3000/invite#token=<random 256 bit>" } }
```

Token nằm sau `#` để không lọt vào log server hay header `Referer`. V2 không gửi email (ngoài phạm vi); người mời tự gửi link. Lời mời theo email cũng hiện trong `pendingInvitations` khi người được mời đăng nhập bằng đúng email, nên mất link vẫn nhận được.

Chấp nhận lời mời: khóa dòng lời mời (`FOR UPDATE` qua hàm definer), kiểm tra chưa nhận, chưa thu hồi, chưa hết hạn, và `lower(google_email) = invitations.email`; tạo membership với hồ sơ chép từ lời mời; nếu đã là thành viên thì chỉ đánh dấu lời mời đã dùng. Lỗi: `409 INVITATION_EMAIL_MISMATCH` (lời mời giữ nguyên), `410 INVITATION_EXPIRED`, `410 INVITATION_REVOKED`, `409 INVITATION_ALREADY_USED`.

### 5.4 Phòng ban (FR-23)

| Method & path | Quyền | Ghi chú |
|---|---|---|
| `GET /api/v1/departments` | Thành viên | MEMBER chỉ cần tên để hiển thị; mặc định chỉ trả `ACTIVE`, `?includeArchived=true` cho OWNER/ADMIN |
| `POST /api/v1/departments` | OWNER, ADMIN | `409 DEPARTMENT_NAME_TAKEN` |
| `PATCH /api/v1/departments/{id}` | OWNER, ADMIN | Đổi tên, `status: ARCHIVED|ACTIVE` |
| `DELETE /api/v1/departments/{id}` | OWNER, ADMIN | `409 DEPARTMENT_IN_USE` kèm số thành viên, lời mời chờ và tài liệu tham chiếu |

Chuyển phòng ban có hiệu lực ở lần refresh kế tiếp (≤ 15 phút). Ngừng hay xóa phòng ban không bao giờ đổi `documents.visibility` (FR-23): tài liệu giới hạn cho phòng ban `ARCHIVED` vẫn giới hạn.

### 5.5 Tài liệu (FR-06, FR-07, FR-09)

| Method & path | Quyền | Ghi chú |
|---|---|---|
| `POST /api/v1/documents` | OWNER, ADMIN | Multipart: `file`, `visibility` (mặc định `WORKSPACE`), `departmentIds[]`, `title?`, `categoryId?`, `tags[]?` |
| `POST /api/v1/documents/{id}/versions` | OWNER, ADMIN | Tải bản thay thế cho tài liệu người dùng đã chọn; `200` (gửi lặp khi đang xử lý), `409 VERSION_IN_PROGRESS`, `409 DOCUMENT_UNCHANGED`, `409 DUPLICATE_DOCUMENT` theo §3.3 |
| `POST /api/v1/documents/{id}/retry` | OWNER, ADMIN | Chỉ khi phiên bản mới nhất `FAILED`; tăng `attempt`, chuyển phiên bản về `UPLOADED`, tạo outbox `INGEST_REQUESTED` mang `attempt` mới. Gọi lại khi phiên bản đã rời `FAILED` → `409 VERSION_NOT_FAILED` (bấm hai lần không tạo hai job) |
| `GET /api/v1/documents` | Thành viên | Lọc quyền đọc (§5.6), lọc `status`, `categoryId`, `tag`, `q` (tiêu đề) |
| `GET /api/v1/documents/{id}` | Thành viên có quyền đọc | `404` nếu ngoài quyền |
| `GET /api/v1/documents/{id}/download-url` | Thành viên có quyền đọc | `{url, expiresAt}` URL ký sẵn S3, hạn `≤ 300 s`, `Content-Disposition` theo tên gốc |
| `GET /api/v1/documents/{id}/versions` | OWNER, ADMIN | Lịch sử phiên bản và lý do `FAILED` |
| `DELETE /api/v1/documents/{id}` | OWNER, ADMIN | Xóa mềm, outbox `DOCUMENT_DELETED`; xóa file S3 và row khi ai-service xác nhận |

Kiểm tra upload: đuôi file và magic bytes phải khớp `PDF` (`%PDF-`) hoặc `MD` (`.md`/`.markdown`, UTF-8 hợp lệ, không có byte NUL). DOCX hoãn sau MVP (owner chốt 2026-10-20) và TXT bỏ khỏi MVP (owner chốt 2026-10-21): `.txt`, DOCX, ảnh, `DOC`, `XLS(X)` bị từ chối ngay bằng `415 UNSUPPORTED_MEDIA_TYPE`, không tạo job; thông điệp hướng dẫn xuất DOCX sang PDF có lớp chữ, đổi TXT sang `.md`. Không chuyển đổi trên server (khác hệ thống cũ, AUDIT-ingestion §2.1). MD không phải UTF-8 → `415 INVALID_ENCODING`. Quá 20 MB → `413` (giới hạn đặt ở `spring.servlet.multipart` và kiểm tra lại khi stream).

Chọn nhiều file (FR-30): frontend gửi tối đa 10 request `POST /api/v1/documents` độc lập (tối đa 3 đồng thời), không có endpoint batch hay transaction toàn đợt; mỗi request thành công hay lỗi riêng. Gửi lại một file sau lỗi mạng: nếu request trước đã được lưu, request sau nhận `409 DUPLICATE_DOCUMENT` kèm `{documentId, title, createdAt}` và frontend hiện "Đã có trong workspace". MVP không dùng `Idempotency-Key` phía client.

Mã lỗi `FAILED` và hành động gợi ý trên giao diện: `EMBEDDING_ERROR`, `RETRY_EXHAUSTED`, `OBJECT_NOT_FOUND`, `EXTRACTION_ERROR` → "Thử lại"; `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING`, `EMPTY_CONTENT`, `UNSUPPORTED_TYPE` → "Thay file" hoặc "Xóa" (thử lại vẫn được phép nhưng không phải hành động chính).

Đối tượng `Document` trả về:

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
  "suggestion": { "status": "READY", "description": "…", "proposedCategoryName": null },
  "createdBy": { "id": "…", "displayName": "An" }, "createdAt": "…", "updatedAt": "…"
}
```

`departments`, `fieldSources`, `suggestion`, `latestVersion.failure*` chỉ trả cho OWNER/ADMIN. `currentVersion` là phiên bản màn xem FR-31 hiển thị (nội dung lấy từ ai-service `GET /ai/v1/documents/{id}/versions/{currentVersion.id}/content`); `latestVersion` khác `currentVersion` thì frontend gắn nhãn "phiên bản N+1 đang xử lý / lỗi".

### 5.6 Metadata và phạm vi hiển thị (FR-25..28)

| Method & path | Quyền | Ghi chú |
|---|---|---|
| `PATCH /api/v1/documents/{id}` | OWNER, ADMIN | Sửa `title`, `description`, `categoryId`, `tags[]`, `language`; trường được sửa chuyển nguồn sang `USER`. Không gọi ai-service, trừ `language` khi BM25 cấu hình theo ngôn ngữ (hiện không, xem TECH-V2-ai-service §6.3) |
| `PUT /api/v1/documents/{id}/visibility` | OWNER, ADMIN | `{visibility, departmentIds[]}`; luồng §2.3; response `{accessSync: APPLIED|PENDING}` |
| `POST /api/v1/documents/{id}/suggestion/apply` | OWNER, ADMIN | Chấp nhận các trường gợi ý được chọn: `{fields: ["description","category"]}`; nguồn chuyển `USER` |
| `GET/POST/PATCH/DELETE /api/v1/categories[/{id}]` | Đọc: thành viên; ghi: OWNER, ADMIN | Phẳng; `ARCHIVED` không gán mới |
| `GET /api/v1/tags` | Thành viên | Tag tạo khi gắn qua `PATCH /documents/{id}` |

**Bộ lọc quyền đọc ở core-api** (danh sách, chi tiết, URL tải; ADR-007 §4.4), tham số hóa hoàn toàn:

```sql
SELECT d.* FROM core.documents d
WHERE d.deleted_at IS NULL
  AND ( :wrole IN ('OWNER','ADMIN')
        OR d.visibility = 'WORKSPACE'
        OR (:wdept IS NOT NULL AND EXISTS (
              SELECT 1 FROM core.document_departments dd
              WHERE dd.document_id = d.id AND dd.department_id = :wdept)) )
```

RLS đã giới hạn workspace; điều kiện trên giới hạn role/phòng ban. `wrole` và `wdept` lấy từ token, không đọc lại DB ở mỗi request (đồng nhất với ai-service; trễ tối đa 15 phút như ADR-007).

**Áp dụng gợi ý (FR-28, V2-25):** khi nhận `PUT /internal/documents/{id}/suggestions`, core-api lưu `document_suggestions`, rồi với từng trường có nguồn `SYSTEM` hoặc `SUGGESTED` thì ghi giá trị gợi ý và đặt nguồn `SUGGESTED`. Trường nguồn `USER` không bị đụng. Gợi ý không chứa và không thể đổi `visibility` hay phòng ban (DTO không có các trường này). Category chỉ nhận `categoryId` thuộc workspace và `ACTIVE`; tên category mới chỉ lưu dạng đề xuất, không tự tạo.

### 5.7 Audit (FR-20)

`GET /api/v1/audit-logs?action=&actorId=&from=&to=&cursor=` — chỉ OWNER, sắp xếp mới nhất trước.

---

## 6. Ghi nhận ngôn ngữ và lỗi cho người dùng

`failure_message` và `error.message` là câu tiếng Việt hoặc tiếng Anh theo header `Accept-Language` (mặc định `vi`). Danh sách mã lỗi là contract với frontend; message có thể đổi.

---

## 7. Outbox dispatcher

- Bean `OutboxDispatcher` có hai đường:
  1. **Đẩy ngay:** sau commit (`@TransactionalEventListener(phase = AFTER_COMMIT)`), gửi sự kiện vừa ghi trên executor riêng. Đây là cách đánh thức ai-service (ADR-006 B1 ràng buộc 3) và cho `ACCESS_UPDATED` gần như đồng bộ.
  2. **Quét định kỳ:** mỗi `SOPILOT_OUTBOX_POLL=PT5S`, gọi `core.claim_outbox_batch(20)` (`FOR UPDATE SKIP LOCKED` trên `status = 'PENDING' AND next_attempt_at <= now()`), gửi từng sự kiện.
- Thử lại: backoff lũy thừa `2^attempts` giây, trần 10 phút, kèm jitter; sau `SOPILOT_OUTBOX_MAX_ATTEMPTS=20` chuyển `DEAD` và ghi log mức `ERROR`. Phiên bản tài liệu có sự kiện `INGEST_REQUESTED` bị `DEAD` chuyển `FAILED` với `failure_code = DISPATCH_FAILED` để người dùng bấm thử lại.
- `4xx` từ ai-service (trừ `408`, `429`) là lỗi contract: chuyển `DEAD` ngay, không thử lại vô hạn.
- Idempotency: `outbox_events.id` gửi trong header `Idempotency-Key`; ai-service bỏ qua khóa đã xử lý (TECH-V2-ai-service §8).
- Thứ tự: `ACCESS_UPDATED` mang `accessRevision`; ai-service chỉ áp dụng khi lớn hơn bản đang có, nên giao lệch thứ tự không làm quyền quay về trạng thái cũ.

---

## 8. Contract giữa core-api và ai-service (nguồn chung)

Mọi endpoint `/internal/**` yêu cầu header `X-Internal-Token: <SOPILOT_INTERNAL_TOKEN>`, so sánh thời gian hằng. Thiếu hoặc sai → `401`. Hai service dùng cùng một token cho cả hai chiều (một biến env). Body JSON, `camelCase`.

### 8.1 core-api → ai-service

**`POST /internal/ingestions`** (`INGEST_REQUESTED`) → `202`; trùng `Idempotency-Key`, hoặc trùng `(versionId)` với `attempt` không lớn hơn lần trước → `202` không tạo job mới. `attempt` lớn hơn và job đang `FAILED` → job quay lại hàng đợi (thử lại, TECH-V2-ai-service §8).

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

ai-service ghi (hoặc nâng) `rag.document_access` và tạo `rag.ingestion_jobs` **trong cùng một transaction**, nên dòng quyền luôn có trước khi chunk nào được truy xuất (ADR-007 §4.5, V2-12).

**`PUT /internal/document-access/{documentId}`** (`ACCESS_UPDATED`) → `200 {"applied": true|false}` (`false` khi `accessRevision` không mới hơn).

```json
{ "workspaceId": "…", "visibility": "WORKSPACE", "departmentIds": [], "accessRevision": 4 }
```

**`DELETE /internal/documents/{documentId}?workspaceId=…`** (`DOCUMENT_DELETED`) → `200` sau khi xóa `document_access`, chunk, job, kết quả trích xuất của mọi phiên bản; idempotent (`200` cả khi không còn gì). Trích dẫn trong lịch sử hội thoại tới tài liệu đã xóa bị ẩn như mất quyền.

### 8.2 ai-service → core-api

**`PATCH /internal/documents/{documentId}/versions/{versionId}/status`**

```json
{ "workspaceId": "…", "status": "READY", "attempt": 0,
  "pageCount": 7, "detectedLanguage": "vi", "chunkCount": 41,
  "embedding": { "provider": "local", "model": "BAAI/bge-m3", "revision": "<hf commit>", "dim": 1024 },
  "extracted": { "docCode": "QT-MH-01", "revisionLabel": "03", "effectiveDate": "2026-01-15", "approvedBy": null },
  "warningCodes": ["PAGES_WITHOUT_TEXT"] }
// hoặc
{ "workspaceId": "…", "status": "FAILED", "failureCode": "NO_TEXT_LAYER",
  "failureMessage": "PDF không có lớp chữ (bản scan). Hãy tải bản PDF có thể chọn chữ." }
```

Chuyển trạng thái hợp lệ: `UPLOADED → PROCESSING → READY | FAILED`, `FAILED → UPLOADED` (do `POST /retry` của core-api, `attempt + 1`), `FAILED → PROCESSING` (ai-service tự thử lại trong giới hạn `SOPILOT_INGEST_MAX_ATTEMPTS`). Callback mang `attempt` cũ hơn `attempt` hiện tại bị bỏ qua (`200`, không đổi trạng thái). Chuyển sai (ví dụ phiên bản đã `SUPERSEDED`) → `409`, ai-service không thử lại. Khi `READY`: đặt `current_version_id`, lưu `warning_codes`, chuyển mọi bản cũ hơn sang `SUPERSEDED`, xóa object S3 của bản trước sau `SOPILOT_VERSION_RETENTION` (mặc định xóa ngay; giữ được nếu sau này cần lịch sử).

**`PUT /internal/documents/{documentId}/suggestions`** (FR-28)

```json
{ "workspaceId": "…", "versionId": "…", "method": "LLM", "model": "openai/gpt-oss-20b", "promptVersion": "suggest-v1",
  "title": "Quy trình mua hàng", "description": "…", "categoryId": "…", "proposedCategoryName": null,
  "tags": ["mua hàng", "ISO"], "language": "vi" }
```

ai-service gọi các endpoint này qua outbox của chính nó (`rag.outbox_events`, TECH-V2-ai-service §3), cùng quy tắc thử lại và idempotency như §7.

### 8.3 Đọc file

ai-service đọc object trực tiếp từ storage bằng thông tin trong job (`objectKey`) với credential chỉ đọc riêng (`SOPILOT_S3_AI_ACCESS_KEY`). ai-service không ghi storage.

---

## 9. Cấu hình (biến môi trường, giá trị thật chỉ ở `.env`)

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `SPRING_PROFILES_ACTIVE` | `local` | `local`, `test`, `prod` (prod hiện không dùng) |
| `SOPILOT_DB_URL`, `SOPILOT_DB_USER`, `SOPILOT_DB_PASSWORD` | — | Role `sopilot_core_app` |
| `GOOGLE_CLIENT_ID` | — | |
| `SOPILOT_JWT_PRIVATE_KEY_PATH`, `SOPILOT_JWT_KID` | tự sinh ở `local`/`test` | |
| `SOPILOT_ACCESS_TTL`, `SOPILOT_REFRESH_TTL` | `PT15M`, `P14D` | Access ≤ 15 phút là NFR |
| `SOPILOT_NONCE_HMAC_KEY` | — | |
| `SOPILOT_FRONTEND_ORIGIN` | `http://localhost:3000` | Kiểm tra `Origin` cho refresh/logout, sinh `inviteUrl` |
| `SOPILOT_INTERNAL_TOKEN`, `SOPILOT_AI_BASE_URL` | —, `http://ai-service:8000` | |
| `SOPILOT_S3_ENDPOINT`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_ACCESS_KEY`, `SOPILOT_S3_SECRET_KEY` | — | Một tên bucket duy nhất cho cả hai service (tránh drift `poliwise-documents`/`sopilot-documents`) |
| `SOPILOT_QUOTA_DOCS_PER_WORKSPACE`, `SOPILOT_QUOTA_BYTES_PER_WORKSPACE` | `50`, `209715200` | FR-09 (owner chốt 2026-10-21), `0` = tắt; đặt `0` khi nạp corpus eval/demo lớn |
| `SOPILOT_OUTBOX_POLL`, `SOPILOT_OUTBOX_MAX_ATTEMPTS` | `PT5S`, `20` | |
| `SOPILOT_DOMAIN_JOIN_ENABLED` | `false` | P1 |

---

## 10. Chiến lược kiểm thử

| Lớp | Nội dung | Công cụ |
|---|---|---|
| Unit | Xác minh Google token (mỗi claim sai một test, gồm `nonce`), xoay vòng refresh và phát hiện dùng lại, quy tắc OWNER cuối cùng, ADMIN không đụng OWNER, chuyển trạng thái phiên bản, áp dụng gợi ý theo nguồn trường, mapper lỗi không lộ message nội bộ | JUnit 5, Mockito |
| Integration | Migration chạy sạch trên DB trống; RLS với role `sopilot_core_app` thật; JIT idempotent khi hai request đăng nhập song song; chặn trùng SHA-256 khi hai upload song song; hạn mức: workspace có 48 tài liệu nhận 10 upload đồng thời thì đúng 2 thành công, 8 nhận `409 QUOTA_EXCEEDED`, không object S3 mồ côi sau janitor; quy tắc bản thay thế §3.3 (cả 5 nhánh); retry hai lần liên tiếp chỉ tạo một outbox; `.txt`/DOCX → `415` không tạo job; outbox thử lại và `DEAD`; chấp nhận lời mời sai email | Testcontainers (Postgres + pgvector, MinIO), WireMock cho Google JWKS và ai-service |
| Bảo mật (FR-19, phần core) | Hai workspace với tài liệu chứa chuỗi bí mật khác nhau: mọi endpoint `/api/v1` gọi bằng token workspace A không trả dữ liệu của B; truy vấn trực tiếp với `app.workspace_id` chưa đặt trả 0 dòng; connection được trả về pool sau transaction của A, lấy lại cho request của B không thấy dữ liệu A | Testcontainers, chạy trong CI |
| Bảo mật (FR-29, phần core) | MEMBER ngoài phòng ban: danh sách, chi tiết, URL tải trả `404`; chuyển phòng ban có hiệu lực sau refresh; `SUSPENDED` không refresh được; xóa phòng ban đang dùng bị `409`; thu hẹp phạm vi gửi `ACCESS_UPDATED` | Testcontainers |
| Contract | JSON của §8 kiểm tra bằng file mẫu dùng chung trong `services/contracts/` (cùng file ai-service dùng trong test của nó) | JSON Schema |

`validate-build.ps1` và `run-tests.ps1` cần scope `core-api` (ADR-004 §5, V2-08/V2-11).

---

## 11. Câu hỏi mở (owner chốt 2026-10-20)

Owner duyệt theo đề xuất cho Q1, Q3, Q4, Q5. Q2 được thay bằng quyết định tạm tắt hạn mức thương mại (PRD-V2 FR-09, §8.10).

| # | Câu hỏi | Quyết định |
|---|---|---|
| Q1 | ADR-004 §4.1 đặt **phản hồi và khoảng trống tri thức** ở core-api, nhưng câu hỏi, câu trả lời, trích dẫn và cờ từ chối đều nằm trong `rag` (ai-service). Để ở core-api thì core-api phải nhận bản sao nội dung câu hỏi qua outbox và không tự kiểm được `messageId` thuộc user nào. | **Chốt:** chuyển FR-16/FR-17 sang ai-service (`rag.message_feedback`, view khoảng trống tri thức, TECH-V2-ai-service §7.6). Đã sửa ADR-004 §4.1 và `scope` của V2-13. |
| Q2 | Hạn mức câu hỏi: PRD FR-09 ghi **20 câu/user/ngày**, ticket V2-12 ghi **50**. Hạn mức câu hỏi được đếm ở đâu? | **Chốt:** hạn mức câu hỏi tạm tắt (mặc định `0`). Khi bật lại, đếm ở ai-service vì request hỏi đáp đi thẳng tới đó (TECH-V2-ai-service §7.4), giá trị tham khảo 20 theo PRD; core-api chỉ giữ hạn mức tài liệu. |
| Q3 | Next.js rewrites hay Caddy làm một origin? | Next.js rewrites (không thêm container); chuyển sang Caddy nếu V2-15 thấy SSE bị đệm. |
| Q4 | Giữ file của phiên bản cũ sau khi bản mới `READY`? | Xóa ngay (không có tính năng so sánh version trong V2); cấu hình được qua `SOPILOT_VERSION_RETENTION`. |
| Q5 | Đăng nhập cần ít nhất một lời mời, hay ai có Google cũng vào được? | Ai cũng vào được và có workspace cá nhân (PRD UC-01). Ghi lại vì khác hẳn M1 (roster chặn 403). |
| Q6 | Hạn mức tài liệu mặc định? (owner chốt 2026-10-21) | 50 tài liệu / 200 MB mỗi workspace, cấu hình được, `0` = tắt; hạn mức câu hỏi vẫn mặc định tắt (Q2). Thay quyết định tắt mặc định ngày 2026-10-20 cho riêng hạn mức tài liệu. |
| Q7 | Nhận bản thay thế khi bản trước còn đang xử lý? (owner chốt 2026-10-21) | Không: cùng bytes trả phiên bản đang xử lý, khác bytes `409 VERSION_IN_PROGRESS` (§3.3). Tránh hàng đợi phiên bản và kích hoạt sai thứ tự. |

---

## 12. Không làm trong V2 (nhắc lại để tránh port nhầm)

- Không port `core.employee_roster`, `metadata.document_access_rules`, `password_reset_tokens`, OTP, cột password hash (ADR-005 §4.1, ADR-007).
- Không phát sự kiện RabbitMQ; không đọc schema của service khác.
- Không gửi email mời (người mời tự chia sẻ link).
