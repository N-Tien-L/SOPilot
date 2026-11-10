---
id: TECH-V2-DOCUMENT-ACCESS-SYNC
title: "Thiết kế kỹ thuật: Đồng bộ quyền truy cập tài liệu qua Outbox (core-api -> ai-service)"
status: approved
created: 2026-11-09
updated: 2026-11-10
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
  - docs/02-architecture/designs/TECH-V2-core-api.md
  - docs/02-architecture/designs/TECH-V2-ai-service.md
author: "Owner"
affected_services: [core-api, ai-service]
affected_schemas: [core, rag]
---

# TÀI LIỆU THIẾT KẾ KỸ THUẬT: ĐỒNG BỘ QUYỀN TRUY CẬP TÀI LIỆU (DOCUMENT ACCESS SYNC)

> **Mã tài liệu:** `TECH-V2-DOCUMENT-ACCESS-SYNC` | **Trạng thái:** `approved` (duyệt 2026-11-10, đối chiếu code sau V2-12/V2-23)  
> **Tham chiếu:** [ADR-004](../../02-architecture/adr/ADR-004-two-service-architecture.md), [ADR-007](../../02-architecture/adr/ADR-007-departments-member-profiles-document-access.md), [TECH-V2-core-api](TECH-V2-core-api.md) §2.3, §5.6, §7, §8, [TECH-V2-ai-service](TECH-V2-ai-service.md) §3.1, §6.1, §8

Tài liệu này gom luồng đồng bộ quyền vốn rải ở hai TECH service thành một chỗ để đọc. Khi có mâu thuẫn, contract ở TECH-V2-core-api §8 và code là nguồn đúng.

---

## 1. Tổng quan & Ranh giới Hệ thống (System Boundaries)

Hệ thống SOPilot V2 vận hành theo kiến trúc 2-service độc lập:
1. **`core-api`**: Là **nguồn sự thật duy nhất (Single Source of Truth)** về tài liệu, người dùng, phòng ban, phân quyền và phiên bản. Sở hữu schema `core`.
2. **`ai-service`**: Chịu trách nhiệm trích xuất văn bản, embedding, lưu trữ chunks và tìm kiếm ngữ nghĩa (RAG). Sở hữu schema `rag` và **hoàn toàn không truy cập schema `core`** (ADR-004 §4.3).

Để đảm bảo RAG truy xuất chính xác theo phân quyền (RBAC / Department filtering) mà không cần gọi ngược lại `core-api` trong thời gian thực khi inference, `ai-service` duy trì bảng bản sao trạng thái quyền: **`rag.document_access`** (mỗi tài liệu một dòng).

### Ranh giới đồng bộ:
- Mọi thay đổi về phạm vi truy cập hoặc trạng thái tồn tại của tài liệu từ `core-api` được đồng bộ sang `ai-service` thông qua **Transactional Outbox Pattern** với giao thức HTTP nội bộ.
- Cơ chế **ghi đè có kiểm tra thứ tự (`access_revision`)** để đảm bảo tính nhất quán (Eventual Consistency) và chống sự cố tin nhắn đến sai thứ tự (out-of-order delivery).
- Mỗi request nội bộ mang `X-Internal-Token` và `Idempotency-Key = outbox_events.id`; ai-service bỏ qua khóa đã xử lý.

| Thành phần | Schema sở hữu | Vai trò trong luồng |
|---|---|---|
| `core-api` (`DocumentService`, `OutboxService`) | `core` | Lưu thay đổi tài liệu, ghi sự kiện vào `core.outbox_events` trong cùng transaction. |
| `OutboxDispatcher` (trong `core-api`) | `core` | Ba đường gửi: `ACCESS_UPDATED` gửi thẳng trên thread của request ngay sau commit (`sendDirect`, timeout 2 s); các sự kiện khác được đẩy sau commit (`@TransactionalEventListener(phase = AFTER_COMMIT)` trên thread `outbox-wake`); quét định kỳ `sopilot.outbox.poll` (mặc định `PT5S`) qua `core.claim_outbox_batch(20)` cho mọi sự kiện đến hạn. Gửi bằng `HttpAiServiceClient`. |
| `ai-service` | `rag` | Nhận `POST /internal/ingestions`, `PUT /internal/document-access/{id}`, `DELETE /internal/documents/{id}`; ghi `rag.document_access`. |

---

## 2. Sơ đồ tuần tự tương tác (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Quản trị viên (OWNER/ADMIN)
    participant CoreAPI as core-api
    participant CoreDB as Postgres (schema core)
    participant Worker as OutboxDispatcher (core-api)
    participant AIService as ai-service
    participant AIDB as Postgres (schema rag)

    %% Kịch bản 1: Cập nhật quyền
    rect rgb(240, 248, 255)
    Note over Admin,AIDB: Kịch bản 1: Đổi phạm vi (PUT /api/v1/documents/{id}/visibility)
    Admin->>CoreAPI: Cập nhật phạm vi tài liệu (VD: giới hạn phòng ban)
    activate CoreAPI
    CoreAPI->>CoreDB: 1 transaction:<br/>1. UPDATE core.documents (visibility, access_revision + 1)<br/>2. Ghi lại core.document_departments<br/>3. UPDATE payload access của INGEST_REQUESTED còn PENDING (§7.1)<br/>4. INSERT core.outbox_events (ACCESS_UPDATED, PENDING, lease 60 s)<br/>5. INSERT core.audit_logs
    CoreDB-->>CoreAPI: Commit
    CoreAPI->>AIService: sendDirect (thread request, timeout 2 s): PUT /internal/document-access/{documentId}<br/>X-Internal-Token, Idempotency-Key = event id<br/>{ workspaceId, visibility, departmentIds, accessRevision }
    activate AIService
    AIService->>AIDB: UPDATE rag.document_access ... WHERE access_revision < :rev AND deleted_at IS NULL
    AIService-->>CoreAPI: 200 { "applied": true | false }
    deactivate AIService
    CoreAPI->>CoreDB: UPDATE core.outbox_events SET status = 'DELIVERED', delivered_at = now()
    CoreAPI-->>Admin: 200 { accessSync: APPLIED } (lỗi hoặc timeout: markRetry, trả PENDING)
    deactivate CoreAPI
    Note over Worker,AIService: Gửi thẳng thất bại thì Worker gửi lại khi tới next_attempt_at (hoặc khi lease hết).<br/>Lỗi mạng/5xx/408/429: backoff 2^attempts s (trần 10 phút, jitter), tối đa SOPILOT_OUTBOX_MAX_ATTEMPTS rồi DEAD.<br/>4xx khác: DEAD ngay (lỗi contract).
    end

    %% Kịch bản 2: Xóa tài liệu
    rect rgb(255, 245, 245)
    Note over Admin,AIDB: Kịch bản 2: Xóa tài liệu (DELETE /api/v1/documents/{id})
    Admin->>CoreAPI: Bấm xóa tài liệu
    activate CoreAPI
    CoreAPI->>CoreDB: 1 transaction:<br/>1. UPDATE core.documents SET deleted_at = now()<br/>2. INSERT core.outbox_events (DOCUMENT_DELETED, PENDING)<br/>3. INSERT core.audit_logs
    CoreDB-->>CoreAPI: Commit
    CoreAPI-->>Admin: 200 OK
    deactivate CoreAPI

    Worker->>AIService: DELETE /internal/documents/{documentId}?workspaceId={workspaceId}<br/>Idempotency-Key = event id
    activate AIService
    AIService->>AIDB: 1 transaction:<br/>1. SET deleted_at = now() trên document_access<br/>2. DELETE ingestion_jobs, chunks (chunk_terms cascade), extracted_documents, suggestion_jobs<br/>3. DELETE dòng document_access
    AIService-->>Worker: 200 { "deleted": true } (idempotent)
    deactivate AIService
    Worker->>CoreDB: status = 'DELIVERED'; hook xóa cứng core.documents và object S3
    end
```

> Cách tính `accessSync` theo TECH-V2-core-api §2.3, V2-24 hiện thực (cập nhật 2026-11-10): sự kiện `ACCESS_UPDATED` được ghi kèm lease 60 s (`next_attempt_at = now() + 60 s`, `OutboxService.enqueueLeased`) và không phát `Enqueued`, nên `outbox-wake` và vòng quét không gửi trùng. Sau commit, `OutboxDispatcher.sendDirect` gửi trên thread của request với timeout 2 s: 2xx → `DELIVERED`, trả `APPLIED`; lỗi thử lại được hoặc timeout → `markRetry`, trả `PENDING`; 4xx khác → `DEAD`, trả `PENDING`. Request không bị chặn quá 2 s.

---

## 3. Thiết kế Dữ liệu & Database Schema (Data Modeling)

### 3.1 Bảng `rag.document_access` (tại `ai-service`, migration `rag/V003`)
Bảng nắm giữ quyền hiện hành của từng tài liệu, mỗi tài liệu tương ứng một dòng duy nhất. Mọi truy vấn chunk đi qua CTE `allowed` dựng từ bảng này (§6).

```sql
CREATE TABLE rag.document_access (
    workspace_id      uuid NOT NULL,
    document_id       uuid PRIMARY KEY,
    visibility        text NOT NULL CHECK (visibility IN ('WORKSPACE', 'DEPARTMENTS')),
    department_ids    uuid[] NOT NULL DEFAULT '{}',
    access_revision   bigint NOT NULL,
    active_version_id uuid,                 -- Phiên bản đang được truy xuất (NULL = chưa có bản READY)
    title             text NOT NULL,        -- Ghi khi insert và khi kích hoạt phiên bản
    deleted_at        timestamptz,          -- Chặn truy xuất ngay trong transaction xóa
    updated_at        timestamptz NOT NULL DEFAULT now(),  -- trigger trg_document_access_updated
    CHECK (visibility = 'WORKSPACE' OR cardinality(department_ids) >= 1)
);
CREATE INDEX ix_document_access_ws ON rag.document_access (workspace_id);
CREATE INDEX ix_document_access_depts ON rag.document_access USING gin (department_ids);
-- RLS: ENABLE + FORCE, policy tenant_isolation trên rag.current_workspace().
```

Dòng được **tạo** bởi `POST /internal/ingestions` (upsert, chỉ áp dụng khi `access_revision` mới hơn). `PUT /internal/document-access` **không tạo** dòng mới.

### 3.2 Bảng `core.outbox_events` (tại `core-api`, migration `core/V005`)

```sql
CREATE TABLE core.outbox_events (
    id              uuid PRIMARY KEY,               -- cũng là Idempotency-Key gửi sang ai-service
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
-- RLS theo workspace_id; core.claim_outbox_batch(p_limit) (SECURITY DEFINER) lấy sự kiện đến hạn
-- của mọi workspace bằng FOR UPDATE SKIP LOCKED và đặt lease 60 s qua next_attempt_at.
```

Không có trạng thái `PROCESSING`: "đang gửi" là lease 60 s trên `next_attempt_at`, sự kiện vẫn `PENDING`.

---

## 4. Đặc tả Hợp đồng API Nội bộ (Internal API Contracts)

Header chung cho mọi endpoint dưới đây:

```http
Content-Type: application/json
X-Internal-Token: <SOPILOT_INTERNAL_TOKEN>
Idempotency-Key: <outbox_events.id (uuid)>
```

Thiếu/sai token → `401`. Thiếu `Idempotency-Key` hoặc body sai → `422` (core-api coi là lỗi contract, `DEAD` ngay).

### 4.1 Cập nhật phạm vi truy cập: `PUT /internal/document-access/{documentId}`
Được gửi cho sự kiện `ACCESS_UPDATED`.

- **Tính chất:** Idempotent, không tác động tới chunk (FR-26: đổi phạm vi không embed lại).
- **Request Body:**
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
- **Xử lý tại `ai-service`** (`db/repositories/access.py::update_access`, trong `tenant_tx`):
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
- **Response:** luôn `200 {"applied": true | false}`. `false` khi: `accessRevision` không mới hơn, khóa idempotency đã thấy, tài liệu đã xóa, **hoặc ai-service chưa có dòng** (ingest chưa tới). core-api coi mọi `200` là `DELIVERED`.

### 4.2 Xóa tài liệu: `DELETE /internal/documents/{documentId}?workspaceId=...`
Được gửi cho sự kiện `DOCUMENT_DELETED`.

- **Tính chất:** Idempotent; lần lặp lại vẫn `200`.
- **Xử lý tại `ai-service`** (`access.delete_document`, một transaction):
  1. `UPDATE rag.document_access SET deleted_at = now()` (truy xuất đồng thời thấy tài liệu đã mất).
  2. `DELETE` các dòng của tài liệu trong `rag.ingestion_jobs` (đây là cách "hủy" job), `rag.chunks` (`chunk_terms` cascade), `rag.extracted_documents`, `rag.suggestion_jobs`.
  3. `DELETE` dòng `rag.document_access`.
  `rag.message_citations` được giữ để lịch sử hội thoại hiện `DOCUMENT_DELETED`.
- **Response:** `200 {"deleted": true}`.

---

## 5. Ví dụ Minh họa Toàn diện (Walkthrough Examples)

Giả sử tài liệu **"Quy trình thanh toán công tác phí"** có `documentId = "doc-8888"` (id rút gọn cho dễ đọc; thực tế là UUID).

### Ví dụ 1: Admin tạo tài liệu & Ingest bản đầu tiên
1. `core-api` ghi outbox `INGEST_REQUESTED`; dispatcher gửi `POST /internal/ingestions` kèm `access = {visibility: "WORKSPACE", departmentIds: [], accessRevision: 1}` và `title`.
2. `ai-service` upsert dòng đầu tiên vào `rag.document_access`:
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
3. Khi ingestion job xong, worker của `ai-service` kích hoạt phiên bản: `active_version_id = "ver-0001"`. Tài liệu bắt đầu phục vụ RAG.

### Ví dụ 2: Admin đổi phạm vi sang Phòng Kế toán & Nhân sự
1. **Admin** chọn `dept-acc` và `dept-hr`.
2. **`core-api`** tăng `access_revision = 2`, ghi lại `document_departments`, ghi outbox và audit trong một transaction:
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
3. **Dispatcher** gửi `PUT /internal/document-access/doc-8888` ngay sau commit.
4. **`ai-service`** ghi đè: `visibility = DEPARTMENTS`, `department_ids = {dept-acc, dept-hr}`, `access_revision = 2`; `active_version_id` và `title` giữ nguyên.

### Ví dụ 3: Out-of-order Delivery
1. Admin đổi `DEPARTMENTS` → `WORKSPACE` (`accessRevision = 3`).
2. Vài giây sau đổi lại chỉ `dept-board` (`accessRevision = 4`).
3. Sự kiện rev 3 lỗi tạm thời và chờ backoff; rev 4 tới trước → dòng thành `access_revision = 4`.
4. Rev 3 tới sau: `WHERE access_revision < 3` không khớp → `200 {"applied": false}`, dòng giữ trạng thái rev 4.

### Ví dụ 4: Xóa tài liệu
1. Admin xóa `doc-8888`; `core-api` đặt `deleted_at` và ghi `DOCUMENT_DELETED`.
2. Dispatcher gửi `DELETE /internal/documents/doc-8888?workspaceId=ws-1111`.
3. `ai-service` đặt `deleted_at`, xóa jobs/chunks/extraction/suggestion jobs rồi xóa dòng access, tất cả trong một transaction, trả `200 {"deleted": true}`.
4. core-api nhận `DELIVERED` rồi xóa cứng tài liệu và object S3.

---

## 6. Cơ chế Truy vấn Tìm kiếm RAG (RAG Retrieval Isolation)

ai-service tự xác minh access token RS256 của core-api qua `/.well-known/jwks.json` và lấy `wid`, `wrole`, `wdept` (một phòng ban hoặc `NULL`) từ token, không từ request. Mọi đường truy xuất (vector, BM25, mở rộng section, đọc lại trích dẫn) dùng một predicate duy nhất trong `retrieval/access_filter.py`:

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

> **Fail-closed:** tài liệu chưa có dòng `document_access`, đã xóa, hoặc chưa kích hoạt phiên bản thì không có trong `allowed`, nên không chunk nào của nó được trả. `workspace_id = :wid` lặp lại bên cạnh RLS (hai lớp, ADR-005).

core-api dùng predicate tương đương trên `core.documents` + `core.document_departments` cho danh sách, chi tiết, URL tải (TECH-V2-core-api §5.6); tài liệu ngoài quyền trả `404`.

---

## 7. Rủi ro đã biết và ràng buộc cho V2-24

1. **Race ingest–access (đã xử lý trong V2-24, `OutboxRepository.updatePendingIngestAccess`).** Payload `INGEST_REQUESTED` chụp `access` lúc enqueue. Nếu ingest còn `PENDING` (đang backoff vì ai-service lỗi) mà admin đổi phạm vi, `ACCESS_UPDATED` (rev mới) có thể tới trước, nhận `applied: false` vì chưa có dòng, rồi được đánh `DELIVERED`. Ingest tới sau sẽ tạo dòng với **rev cũ, phạm vi cũ** và không gì sửa lại: tài liệu đã thu hẹp về phòng ban có thể bị truy xuất toàn workspace. Hướng xử lý đề xuất (chỉ trong `core`): trong cùng transaction đổi phạm vi, cập nhật `payload->'access'` của các sự kiện `INGEST_REQUESTED` còn `PENDING` của tài liệu đó về phạm vi và revision mới. Bắt buộc có integration test cho kịch bản này. **Còn hở:** `sendDirect` chạy trên thread request, ngoài `synchronized dispatchDue`. Nếu dispatcher đã claim và đang gửi `INGEST_REQUESTED` (payload cũ đã nằm trong bộ nhớ) đúng lúc admin đổi phạm vi, `ACCESS_UPDATED` có thể tới trước, nhận `applied: false` vì chưa có dòng và được đánh `DELIVERED`; ingest tới sau tạo dòng với phạm vi cũ. Cửa sổ chỉ dài bằng một request ingest đang gửi; cần ticket riêng nếu muốn đóng.
2. **Tiêu đề trong `rag.document_access`** chỉ cập nhật khi insert và khi kích hoạt phiên bản. Sửa tiêu đề qua `PATCH /api/v1/documents/{id}` không gọi ai-service (TECH-V2-core-api §5.6), nên trích dẫn hiện tiêu đề cũ tới lần kích hoạt kế tiếp. Chấp nhận cho MVP; ghi vào báo cáo V2-24.
3. **Trễ phòng ban của người dùng:** `wdept` đến từ token (≤ 15 phút); đổi phòng ban có hiệu lực ở lần refresh kế tiếp (ADR-007).

---

## 8. Chiến lược Kiểm thử (Testing Strategy)

1. **Unit (core-api):** đổi phạm vi ghi `documents`, `document_departments`, outbox `ACCESS_UPDATED` và audit trong một transaction (lỗi thì rollback cả hai); `DEPARTMENTS` rỗng hoặc phòng ban khác workspace bị từ chối.
2. **Unit/integration (ai-service, đã có):** `PUT /internal/document-access` trả `applied: false` khi `accessRevision` ≤ hiện tại, khi khóa lặp, khi chưa có dòng.
3. **Integration (core-api, Testcontainers + ai-service mock):** dispatcher gửi đúng path/header/body; ai-service lỗi → outbox thử lại rồi `DELIVERED`; 4xx → `DEAD`; gửi lại cùng payload 3 lần không đổi trạng thái; race §7.1 cho ra `access` mới nhất.
4. **Bảo mật (FR-29, V2-26):** tài liệu cho `dept-finance`; MEMBER `dept-marketing` không thấy trong danh sách/chi tiết/URL tải (`404`) và không nhận chunk hay trích dẫn từ tài liệu đó; OWNER/ADMIN vẫn thấy.
