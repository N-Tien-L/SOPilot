---
id: V2-12
title: "core-api: tài liệu, upload, outbox, hạn mức tài liệu, thay bản an toàn, audit log"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-21
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-11]
blocks: [V2-13, V2-14, V2-15, V2-16, V2-24]
branch: "feat/knowledge-core-api-documents"
assignee: pair
---

# TICKET V2-12: core-api (tài liệu)

## 1. Bối cảnh & Mục tiêu
FR-06, 07, 09, 20, 30, 31 (phần core-api). Thay knowledge-service, RabbitMQ bằng outbox + gọi HTTP sang ai-service. Sửa 2026-10-21 theo [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md): bỏ TXT, hạn mức tài liệu mặc định bật, quy tắc thay bản khi đang xử lý, thử lại mang `attempt`.

## 2. Tiêu chí Hoàn thành
- [ ] DOCX hoãn sau MVP (owner chốt 2026-10-20, FR-06): upload trả `415`, không tạo job; hướng dẫn xuất PDF có lớp chữ, không chuyển đổi trên server.
- [ ] Upload chỉ PDF có lớp chữ và MD (UTF-8) ≤ 20 MB; `.txt`, DOCX, ảnh → `415` không ghi S3, không tạo phiên bản/job, thông điệp hướng dẫn (TXT → `.md`, DOCX → PDF); MD không phải UTF-8 → `415 INVALID_ENCODING`; chặn trùng SHA-256 trong workspace; chỉ OWNER/ADMIN tải lên/xóa, mọi member xem/tải (FR-06).
- [ ] Vòng đời `UPLOADED → PROCESSING → READY | FAILED`, thử lại, thay bản mới (xóa chunk cũ sau khi bản mới `READY`), xóa tài liệu xóa file và chunk (FR-07).
- [ ] Trùng chỉ xét bằng SHA-256 giữa các tài liệu khác nhau trong workspace, và thông báo tên tài liệu đã có; không có dedup ngữ nghĩa (AUDIT-ingestion-sop-data bước 9).
- [ ] Bản thay thế theo đủ 5 nhánh của TECH-V2-core-api §3.3, mỗi nhánh một test: đang xử lý + cùng bytes → `200` trả phiên bản đang xử lý; đang xử lý + khác bytes → `409 VERSION_IN_PROGRESS`; cùng SHA-256 với bản hiện hành `READY` → `409 DOCUMENT_UNCHANGED`, không tạo phiên bản/outbox/job (owner chốt 2026-10-20, PRD-V2 FR-07; thay tiêu chí cũ cho phép tạo bản mới giống bản cũ); trùng tài liệu khác → `409 DUPLICATE_DOCUMENT`; khác bytes → phiên bản mới. File khác bytes không bị từ chối vì gần giống.
- [ ] Thay bản an toàn: trong lúc bản mới xử lý và khi bản mới `FAILED`, `current_version_id` và tài liệu vẫn hỏi đáp được theo bản cũ; khi bản mới `READY`, mọi bản cũ hơn (kể cả `FAILED`) chuyển `SUPERSEDED`.
- [ ] Thử lại: `POST /retry` chỉ khi bản mới nhất `FAILED`, tăng `attempt`, gửi `attempt` trong payload ingest; gọi hai lần liên tiếp chỉ tạo một outbox (`409 VERSION_NOT_FAILED` lần hai); callback mang `attempt` cũ bị bỏ qua. Thử lại một file không chạm tới tài liệu khác.
- [ ] Sửa tiêu đề/mô tả/category/tags không tạo outbox `INGEST_REQUESTED` (test đếm outbox).
- [ ] `Document` trả `currentVersion.warningCodes` và `latestVersion {id, versionNo, status, failureCode, failureMessage}` (TECH-V2-core-api §5.5) cho màn xem FR-31; `failureMessage` là câu cố định theo mã, không lộ lỗi nội bộ.
- [ ] Tài liệu mới có phạm vi `WORKSPACE` mặc định và dòng quyền ở ai-service trước khi `READY` (phạm vi `DEPARTMENTS` ở V2-24).
- [ ] Outbox đẩy sang ai-service bằng HTTP (để đánh thức), có retry; ai-service quét job tồn khi khởi động (FR-08).
- [ ] Hạn mức tài liệu theo workspace cấu hình bằng env, **mặc định 50 tài liệu / 200 MB** (owner chốt 2026-10-21, thay mặc định tắt ngày 2026-10-20), `0` = tắt. Kiểm tra trong transaction với advisory lock theo workspace: workspace có 48 tài liệu nhận 10 upload đồng thời thì đúng 2 thành công, 8 nhận `409 QUOTA_EXCEEDED` kèm `{limit, used}`, không object S3 mồ côi sau janitor; thay phiên bản không tăng số tài liệu; test cả `0`. Hạn mức câu hỏi thuộc ai-service (V2-10), không làm ở đây (FR-09).
- [ ] Audit log: đăng nhập, đổi thành viên/role, upload/xóa; OWNER xem log workspace (FR-20).
- [ ] Mọi bảng có `workspace_id` + RLS; truy vấn lọc ở tầng ứng dụng.
- [ ] Lưu file qua API S3 chuẩn, bucket/endpoint từ env (tránh lệch tên bucket như drift cũ).

## 3. Hướng dẫn
- **File:** `services/core-api/` module documents/outbox/audit; migration `infrastructure/db/migrations/`.
- Nguồn tham khảo: `services/knowledge-service`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | quota (mặc định 50/200 MB, `0`), SHA-256 trùng, 5 nhánh bản thay thế, retry và `attempt`, magic bytes PDF/MD, từ chối TXT/DOCX, quyền theo role | `./mvnw test` |
| Integration (đồng thời) | 10 upload song song chạm hạn mức; 2 upload cùng SHA-256 song song | `./mvnw verify` |
| Integration | upload → outbox → ai-service (mock) → READY; xóa dọn chunk | `./mvnw verify` |
