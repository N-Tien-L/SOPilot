---
id: V2-24
title: "core-api: metadata tài liệu, category/tags phẳng, phạm vi hiển thị theo phòng ban"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-24
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-12, V2-23]
blocks: [V2-16, V2-25, V2-26, V2-33]
branch: "feat/knowledge-core-api-metadata-visibility"
assignee: pair
---

# TICKET V2-24: Metadata và phạm vi hiển thị tài liệu

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-25 (phần core-api), FR-26, FR-27; ADR-007 §4.1, §4.4, §4.5. Thay ACL tổng quát `metadata.document_access_rules` bằng hai phạm vi `WORKSPACE | DEPARTMENTS`.

## 2. Tiêu chí Hoàn thành
- [ ] `documents.visibility` mặc định `WORKSPACE`; `DEPARTMENTS` cần ≥ 1 phòng ban của cùng workspace (`document_departments`, FK `RESTRICT`).
- [ ] Metadata người dùng sửa (OWNER/ADMIN): tiêu đề, mô tả ngắn, một category, nhiều tags, ngôn ngữ, phạm vi. Metadata hệ thống chỉ đọc. Mỗi trường người dùng sửa ghi nguồn (`USER | SUGGESTED | SYSTEM`) để gợi ý chạy nền không ghi đè.
- [ ] Category và tags phẳng theo workspace; category ARCHIVED không gán mới; xóa category để tài liệu về "chưa phân loại", không ảnh hưởng quyền.
- [ ] Đổi phạm vi: ghi DB, gọi ai-service cập nhật `rag.document_access` đồng bộ, outbox thử lại khi lỗi; audit ghi thay đổi.
- [ ] Danh sách, tìm kiếm, chi tiết, xem trước, tải xuống lọc theo quyền ADR-007 §4.4; MEMBER không thấy tên tài liệu ngoài quyền (404, không 403 kèm tên).
- [ ] Tải xuống/xem trước qua URL ký sẵn hạn ≤ 5 phút, chỉ phát sau khi kiểm tra quyền.
- [ ] Không re-embed khi sửa tiêu đề, mô tả, category, tags hay phạm vi.

## 3. Hướng dẫn
- **File:** module documents/metadata trong `services/core-api/`; migration trong `infrastructure/db/migrations/`.
- Tham khảo: `services/metadata-service` (Category, Tag, DocumentMetadata), `frontend/web/app/admin/metadata/`. Không port `document_access_rules`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Ma trận quyền ADR-007 §4.4 trên service tài liệu; nguồn trường metadata; category xóa/archived | `./mvnw test` |
| Integration | Đổi phạm vi → ai-service (mock) nhận cập nhật; ai-service lỗi → outbox thử lại; URL ký sẵn hết hạn | `./mvnw verify` |
