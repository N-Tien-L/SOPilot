---
id: V2-12
title: "core-api: tài liệu, upload, outbox, hạn mức, audit log"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-19
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
FR-06, 07, 09, 20. Thay knowledge-service, RabbitMQ bằng outbox + gọi HTTP sang ai-service.

## 2. Tiêu chí Hoàn thành
- [ ] Upload PDF/DOCX/MD/TXT ≤ 20 MB; chặn trùng SHA-256 trong workspace; chỉ OWNER/ADMIN tải lên/xóa, mọi member xem/tải (FR-06).
- [ ] Vòng đời `UPLOADED → PROCESSING → READY | FAILED`, thử lại, thay bản mới (xóa chunk cũ sau khi bản mới `READY`), xóa tài liệu xóa file và chunk (FR-07).
- [ ] Trùng chỉ xét bằng SHA-256 giữa các tài liệu khác nhau trong workspace, và thông báo tên tài liệu đã có. Bản mới của cùng tài liệu không bao giờ bị bỏ qua vì giống bản cũ; không có dedup ngữ nghĩa (AUDIT-ingestion-sop-data bước 9).
- [ ] Tài liệu mới có phạm vi `WORKSPACE` mặc định và dòng quyền ở ai-service trước khi `READY` (phạm vi `DEPARTMENTS` ở V2-24).
- [ ] Outbox đẩy sang ai-service bằng HTTP (để đánh thức), có retry; ai-service quét job tồn khi khởi động (FR-08).
- [ ] Hạn mức theo workspace (50 tài liệu, 200 MB) và theo user (50 câu hỏi/ngày), cấu hình bằng env (FR-09).
- [ ] Audit log: đăng nhập, đổi thành viên/role, upload/xóa; OWNER xem log workspace (FR-20).
- [ ] Mọi bảng có `workspace_id` + RLS; truy vấn lọc ở tầng ứng dụng.
- [ ] Lưu file qua API S3 chuẩn, bucket/endpoint từ env (tránh lệch tên bucket như drift cũ).

## 3. Hướng dẫn
- **File:** `services/core-api/` module documents/outbox/audit; migration `infrastructure/db/migrations/`.
- Nguồn tham khảo: `services/knowledge-service`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | quota, SHA-256 trùng, quyền theo role | `./mvnw test` |
| Integration | upload → outbox → ai-service (mock) → READY; xóa dọn chunk | `./mvnw verify` |
