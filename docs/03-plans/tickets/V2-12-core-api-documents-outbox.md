---
id: V2-12
title: "core-api: tài liệu, upload, outbox, hạn mức tài liệu, thay bản an toàn, audit log"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-09
author: "Owner"
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-11]
blocks: [V2-13, V2-14, V2-16, V2-24, V2-31, V2-32]
branch: "feat/knowledge-core-api-documents"
assignee: pair
---

# TICKET V2-12: core-api (tài liệu)

## 1. Bối cảnh & Mục tiêu
FR-06, 07, 09, 20, 30, 31 (phần core-api). Thay knowledge-service, RabbitMQ bằng outbox + gọi HTTP sang ai-service. Sửa 2026-10-21 theo [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md): bỏ TXT, hạn mức tài liệu mặc định bật, quy tắc thay bản khi đang xử lý, thử lại mang `attempt`.

## 2. Tiêu chí Hoàn thành
- [x] DOCX hoãn sau MVP (owner chốt 2026-10-20, FR-06): upload trả `415`, không tạo job; hướng dẫn xuất PDF có lớp chữ, không chuyển đổi trên server.
- [x] Upload chỉ PDF có lớp chữ và MD (UTF-8) ≤ 20 MB; `.txt`, DOCX, ảnh → `415` không ghi S3, không tạo phiên bản/job, thông điệp hướng dẫn (TXT → `.md`, DOCX → PDF); MD không phải UTF-8 → `415 INVALID_ENCODING`; chặn trùng SHA-256 trong workspace; chỉ OWNER/ADMIN tải lên/xóa, mọi member xem/tải (FR-06).
- [x] Vòng đời `UPLOADED → PROCESSING → READY | FAILED`, thử lại, thay bản mới (xóa chunk cũ sau khi bản mới `READY`), xóa tài liệu xóa file và chunk (FR-07).
- [x] Trùng chỉ xét bằng SHA-256 giữa các tài liệu khác nhau trong workspace, và thông báo tên tài liệu đã có; không có dedup ngữ nghĩa (AUDIT-ingestion-sop-data bước 9).
- [x] Bản thay thế theo đủ 5 nhánh của TECH-V2-core-api §3.3, mỗi nhánh một test: đang xử lý + cùng bytes → `200` trả phiên bản đang xử lý; đang xử lý + khác bytes → `409 VERSION_IN_PROGRESS`; cùng SHA-256 với bản hiện hành `READY` → `409 DOCUMENT_UNCHANGED`, không tạo phiên bản/outbox/job (owner chốt 2026-10-20, PRD-V2 FR-07; thay tiêu chí cũ cho phép tạo bản mới giống bản cũ); trùng tài liệu khác → `409 DUPLICATE_DOCUMENT`; khác bytes → phiên bản mới. File khác bytes không bị từ chối vì gần giống.
- [x] Thay bản an toàn: trong lúc bản mới xử lý và khi bản mới `FAILED`, `current_version_id` và tài liệu vẫn hỏi đáp được theo bản cũ; khi bản mới `READY`, mọi bản cũ hơn (kể cả `FAILED`) chuyển `SUPERSEDED`.
- [x] Thử lại: `POST /retry` chỉ khi bản mới nhất `FAILED`, tăng `attempt`, gửi `attempt` trong payload ingest; gọi hai lần liên tiếp chỉ tạo một outbox (`409 VERSION_NOT_FAILED` lần hai); callback mang `attempt` cũ bị bỏ qua. Thử lại một file không chạm tới tài liệu khác.
- [x] Sửa tiêu đề/mô tả/category/tags không tạo outbox `INGEST_REQUESTED` (test đếm outbox). (title/description/language: có test đếm outbox; category/tags thuộc V2-24)
- [x] `Document` trả `currentVersion.warningCodes` và `latestVersion {id, versionNo, status, failureCode, failureMessage}` (TECH-V2-core-api §5.5) cho màn xem FR-31; `failureMessage` là câu cố định theo mã, không lộ lỗi nội bộ.
- [x] Tài liệu mới có phạm vi `WORKSPACE` mặc định và dòng quyền ở ai-service trước khi `READY` (phạm vi `DEPARTMENTS` ở V2-24). (payload ingest mang `access` `WORKSPACE`, `accessRevision` 1; `DEPARTMENTS` bị từ chối `400` cho tới V2-24. Chạy thật 2026-11-07: `rag.document_access` có `visibility=WORKSPACE`, `access_revision=1`, `active_version_id` đã đặt sau `READY`; thứ tự ghi dòng quyền so với `READY` chưa đo riêng)
- [x] Outbox đẩy sang ai-service bằng HTTP (để đánh thức), có retry; ai-service quét job tồn khi khởi động (FR-08).
- [x] Hạn mức tài liệu theo workspace cấu hình bằng env, **mặc định 50 tài liệu / 200 MB** (owner chốt 2026-10-21, thay mặc định tắt ngày 2026-10-20), `0` = tắt. Kiểm tra trong transaction với advisory lock theo workspace: workspace có 48 tài liệu nhận 10 upload đồng thời thì đúng 2 thành công, 8 nhận `409 QUOTA_EXCEEDED` kèm `{limit, used}`, không object S3 mồ côi sau janitor; thay phiên bản không tăng số tài liệu; test cả `0`. Hạn mức câu hỏi thuộc ai-service (V2-10), không làm ở đây (FR-09).
- [x] Audit log: đăng nhập, đổi thành viên/role, upload/xóa; OWNER xem log workspace (FR-20). (đổi role chưa có vì chưa có endpoint đổi role, V2-30)
- [x] Mọi bảng có `workspace_id` + RLS; truy vấn lọc ở tầng ứng dụng.
- [x] Lưu file qua API S3 chuẩn, bucket/endpoint từ env (tránh lệch tên bucket như drift cũ).

## 3. Hướng dẫn
- **File:** `services/core-api/` module documents/outbox/audit; migration `infrastructure/db/migrations/`.
- Nguồn tham khảo: `services/knowledge-service`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | quota (mặc định 50/200 MB, `0`), SHA-256 trùng, 5 nhánh bản thay thế, retry và `attempt`, magic bytes PDF/MD, từ chối TXT/DOCX, quyền theo role | `./mvnw test` |
| Integration (đồng thời) | 10 upload song song chạm hạn mức; 2 upload cùng SHA-256 song song | `./mvnw verify` |
| Integration | upload → outbox → ai-service (mock) → READY; xóa dọn chunk | `./mvnw verify` |

## 5. Bằng chứng triển khai (2026-11-06, nghiệm thu 2026-11-09)

Owner nghiệm thu 2026-11-09, chuyển `done`. Code ở commit `4113f63` (sửa region S3 ở `e96599c`), merge vào `develop` qua [PR #5](https://github.com/N-Tien-L/SOPilot/pull/5). 5 chỗ lệch TECH dưới đây được duyệt, ghi ở TECH-V2-core-api §13. Các mục "Chưa làm / chưa kiểm" được chấp nhận còn mở và thuộc ticket ghi kèm.

- **Kiểm lại khi nghiệm thu (2026-11-09):** `cd services/core-api && ./mvnw -B verify` -> 73 unit + 78 integration, 0 lỗi (gồm `DocumentLifecycleIT` 18, `DocumentConcurrencyIT` 7, `DocumentQuotaIT` 3, `DocumentQuotaDisabledIT` 1, `OutboxDispatcherIT` 10, `S3StorageClientIT` 5, `TenantIsolationApiIT` 8). Đọc lại `DocumentService`, `VersionStatusService`, `DocumentOutboxHooks`, `OutboxDispatcher`, `HttpAiServiceClient`: thứ tự khóa nhất quán (dòng tài liệu, SHA-256, hạn mức), callback cũ `attempt` bị bỏ qua, log chỉ ghi tên lớp lỗi và mã HTTP.
- **Nhận xét review (không chặn):** vài câu lệnh ghi trong `DocumentRepository` (`setStatus`, `markReady`, `markFailed`, `resetForRetry`, `activate`, `setLatestVersion`, `updateMetadata`, `metaSources`, `softDelete`, `maxVersionNo`) chỉ lọc theo `id`, không lặp `workspace_id`. Hiện không rò được vì mọi lời gọi chạy sau `lockDocument(workspace_id, id)` trong cùng `TenantTx` và RLS vẫn bật; cần bổ sung `workspace_id` cho đúng quy tắc hai lớp (CLAUDE.md ràng buộc 4); đã thêm thành tiêu chí của V2-24 (ticket sửa repository này).

- **Code:** `services/core-api/src/main/java/com/sopilot/core/{document,outbox,storage,audit,security,tenancy}/`; migration `infrastructure/db/migrations/core/V005__documents_outbox_audit.sql` (`categories`, `documents`, `document_versions`, `document_departments`, `outbox_events`, `audit_logs` append-only, `claim_outbox_batch`, `referenced_object_keys`). `JwtAuthFilter`/`InternalTokenFilter`/`TenantTx` là nền cho mọi endpoint (V2-11 chỉ phát token).
- **Lệnh:** `cd services/core-api && ./mvnw verify` -> 66 unit + 70 integration, 0 lỗi (trước đó 41 + 14). Riêng V2-12: `UploadValidatorTest` (8), `AccessTokenVerifierTest` (7), `HttpAiServiceClientTest` (4, server HTTP thật), `DocumentLifecycleIT` (18), `DocumentConcurrencyIT` (7), `DocumentQuotaIT` (3), `DocumentQuotaDisabledIT` (1), `OutboxDispatcherIT` (10), `S3StorageClientIT` (5, MinIO `RELEASE.2024-05-10T01-41-38Z` thật, URL ký sẵn tải được, tên file UTF-8 trong `Content-Disposition`).
- **Hạn mức:** workspace có 48 tài liệu nhận 10 upload đồng thời -> đúng 2 thành công, 8 `409 QUOTA_EXCEEDED`, 50 object trong storage, `StorageJanitor.sweep(0)` xóa 0 object. 4 upload cùng bytes song song -> 1 tài liệu, 3 `DUPLICATE_DOCUMENT`. 2 retry song song -> 1 outbox. 3 bản thay thế khác bytes song song -> 1 phiên bản, 2 `VERSION_IN_PROGRESS`. Hạn mức byte, thay bản không tăng số tài liệu, tài liệu xóa mềm không tính, `0` tắt hạn mức: có test.
- **Hợp đồng với ai-service:** payload `INGEST_REQUESTED` (lấy từ test) qua `sopilot_ai.ingest.schemas.IngestionRequest.model_validate` thành công; header `X-Internal-Token` và `Idempotency-Key` = id outbox; callback `PATCH .../status` nhận đúng các trường ai-service gửi (`workspaceId`, `status`, `attempt`, `embedding`, `extracted`, `warningCodes`, `failureCode`); `extracted.effectiveDate` không phải ISO bị bỏ qua thay vì `400` (ai-service dead-letter mọi `4xx`).
- **Lệch so với TECH-V2-core-api:** (1) PUT S3 chạy **cuối** transaction, ngay trước commit, thay vì trước mọi bước DB (§2.2): xung đột (trùng, hạn mức, đang xử lý) không bao giờ chạm storage; object mồ côi chỉ còn khi commit lỗi sau PUT, `StorageJanitor` dọn (hạn 1 giờ). Giữ advisory lock suốt lúc PUT, chấp nhận ở quy mô này. (2) `TenantTx` bọc từng transaction thay cho listener `TransactionSynchronizationManager` (§4.3). (3) `QUOTA_EXCEEDED` trả `409` theo ticket và §3.3 (§5.0 ghi `422`). (4) `failure_message` lưu câu tiếng Việt cố định theo mã (không theo `Accept-Language`). (5) `PATCH /documents/{id}` sửa title/description/language; category/tags/phạm vi hiển thị là V2-24.
- **Chạy thật (2026-11-07):** Postgres + MinIO từ `docker-compose.v2.yml` (Flyway áp V001-V005 core, V001-V003 rag), core-api (`mvnw spring-boot:run`, profile `local`) + ai-service API + worker chạy tay trên Windows; kịch bản `dev-login` hai người dùng hai workspace, 19 bước. Kết quả: MD `READY` (lần đầu 132 s vì nạp bge-m3 nguội), PDF qua Docling `READY` sau 10 s; trùng SHA-256 `409 DUPLICATE_DOCUMENT`; cùng bytes với bản hiện hành `409 DOCUMENT_UNCHANGED`; khác bytes -> bản mới `READY`, bản cũ `SUPERSEDED`; TXT và MD không UTF-8 `415`; `POST /retry` trên bản `FAILED` -> `200`, lần hai `409 VERSION_NOT_FAILED`, một outbox mới, kết quả `READY`; URL ký trả đúng bytes; token core-api được ai-service xác minh qua JWKS (`/ai/v1/documents/{id}/versions/{vid}/content` 200 cho chủ, `404` cho workspace khác, `401` không token); xóa tài liệu -> 0 chunk, 0 bản trích xuất, 0 dòng quyền, object S3 bị xóa, `DOCUMENT_DELETED` `DELIVERED`. **Lỗi tìm thấy và đã sửa:** worker ai-service không đọc được MinIO (mọi job `RETRY_EXHAUSTED`) vì minio-py gọi `GetBucketLocation` mà chính sách chỉ đọc `sopilot-ai-ro` chỉ có `s3:GetObject`; test mock của V2-09 không bắt được. Sửa bằng `SOPILOT_S3_REGION` (mặc định `us-east-1`) truyền vào `Minio(region=...)`, test `tests/unit/test_object_store.py`. Ghi chú Windows: `uvicorn` dùng `ProactorEventLoop` nên API ai-service lỗi psycopg async; chạy bằng wrapper `SelectorEventLoop` (worker đã tự đặt policy). LLM/hỏi đáp chưa chạy (V2-10).
- **Chưa làm / chưa kiểm:** hỏi đáp qua hai service (V2-10); `ACCESS_UPDATED` và phạm vi `DEPARTMENTS` (V2-24); `PUT /internal/documents/{id}/suggestions` (V2-25; ai-service chỉ gửi khi `suggest.enabled`, hiện luôn `false`); refresh/switch (V2-29); frontend (V2-31, V2-32).
- **Docs:** `.agent/context/{database/schema.md, database/tables/core.md, service-boundaries/api-contracts.md, authorization/v2-core-identity.md, README.md}`, `.env.example`, `services/core-api/README.md`.
