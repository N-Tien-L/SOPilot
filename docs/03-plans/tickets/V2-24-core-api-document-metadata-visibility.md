---
id: V2-24
title: "core-api: metadata tài liệu, category/tags phẳng, phạm vi hiển thị theo phòng ban"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-10
author: "Owner"
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
- [x] `documents.visibility` mặc định `WORKSPACE`; `DEPARTMENTS` cần ≥ 1 phòng ban của cùng workspace (`document_departments`, FK `RESTRICT`).
- [x] Metadata người dùng sửa (OWNER/ADMIN): tiêu đề, mô tả ngắn, một category, nhiều tags, ngôn ngữ, phạm vi. Metadata hệ thống chỉ đọc. Mỗi trường người dùng sửa ghi nguồn (`USER | SUGGESTED | SYSTEM`) để gợi ý chạy nền không ghi đè.
- [x] Category và tags phẳng theo workspace; category ARCHIVED không gán mới; xóa category để tài liệu về "chưa phân loại", không ảnh hưởng quyền.
- [x] Đổi phạm vi: ghi DB, gọi ai-service cập nhật `rag.document_access` đồng bộ, outbox thử lại khi lỗi; audit ghi thay đổi.
- [x] Danh sách, tìm kiếm, chi tiết, xem trước, tải xuống lọc theo quyền ADR-007 §4.4; MEMBER không thấy tên tài liệu ngoài quyền (404, không 403 kèm tên).
- [x] Tải xuống/xem trước qua URL ký sẵn hạn ≤ 5 phút, chỉ phát sau khi kiểm tra quyền.
- [x] Không re-embed khi sửa tiêu đề, mô tả, category, tags hay phạm vi.
- [x] `PUT /api/v1/documents/{id}/visibility` trả `{accessSync: APPLIED|PENDING}` theo TECH-V2-core-api §2.3; request không bị chặn quá ~2 s chờ ai-service.
- [x] Race ingest–access (TECH-V2-DOCUMENT-ACCESS-SYNC §7.1): đổi phạm vi khi `INGEST_REQUESTED` của tài liệu còn `PENDING` thì ai-service cuối cùng giữ phạm vi và revision mới nhất (vd. cập nhật `payload->'access'` của sự kiện ingest còn chờ trong cùng transaction); có integration test.
- [x] (Chuyển từ V2-12, review 2026-11-09) Mọi câu lệnh ghi/đọc trong `DocumentRepository` lặp `workspace_id` trong `WHERE` (hiện `setStatus`, `markReady`, `markFailed`, `resetForRetry`, `activate`, `setLatestVersion`, `updateMetadata`, `metaSources`, `softDelete`, `maxVersionNo` chỉ lọc `id`), đúng quy tắc hai lớp RLS + lọc ứng dụng.

## 3. Hướng dẫn
- **Đã có từ V2-12, không làm lại:** bộ lọc đọc `VISIBLE` trong `DocumentRepository` (list/chi tiết/URL tải, `404`), `presign` 5 phút, payload `access` trong `INGEST_REQUESTED`, nhánh `ACCESS_UPDATED` của `HttpAiServiceClient`, `core.categories`, `core.document_departments`, các cột `*_source`. V2-24 nối API, mở `DEPARTMENTS` (hiện `requireWorkspaceVisibility` chặn khi upload) và bổ sung test.
- **Luồng đồng bộ:** [TECH-V2-DOCUMENT-ACCESS-SYNC](../../02-architecture/designs/TECH-V2-document-access-sync.md); contract ở TECH-V2-core-api §8. ai-service không cần sửa.
- **Migration:** `core/V007` cho `core.tags`, `core.document_tags` theo TECH-V2-core-api §3.4 (RLS, grant), qua skill `flyway-migration`.
- **File:** module documents/metadata trong `services/core-api/`; migration trong `infrastructure/db/migrations/`.
- Tham khảo: `services/metadata-service` (Category, Tag, DocumentMetadata), `frontend/web/app/admin/metadata/`. Không port `document_access_rules`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Ma trận quyền ADR-007 §4.4 trên service tài liệu; nguồn trường metadata; category xóa/archived | `./mvnw test` |
| Integration | Đổi phạm vi → ai-service (mock) nhận cập nhật; ai-service lỗi → outbox thử lại; URL ký sẵn hết hạn | `./mvnw verify` |

## 5. Duyệt sẵn sàng (2026-11-10)
Owner duyệt sẵn sàng triển khai: V2-12, V2-23 `done`; endpoint ai-service (`PUT /internal/document-access`, `DELETE /internal/documents`) và `access_filter.py` đã có; TECH-V2-DOCUMENT-ACCESS-SYNC `approved`.

## 6. Kết quả và nghiệm thu
- **Đã làm:** migration `core/V007` (`tags`, `document_tags`, RLS FORCE, grant); API `/api/v1/categories`, `GET /api/v1/tags`; `PATCH /documents/{id}` cho `categoryId`, `tags[]` (nguồn `USER`); upload nhận `visibility`, `departmentIds[]`, `title`, `categoryId`, `tags[]`; `PUT /documents/{id}/visibility` trả `{accessSync}`; cập nhật `payload->'access'` của `INGEST_REQUESTED` còn `PENDING` (race §7.1); `DocumentRepository` lặp `workspace_id` ở mọi câu lệnh.
- **Đồng bộ phạm vi:** sự kiện `ACCESS_UPDATED` ghi kèm lease 60 s (cùng cơ chế `claim_outbox_batch`), gửi trực tiếp trên luồng request với timeout 2 s ngay sau commit; 2xx → `DELIVERED`/`APPLIED`, lỗi hoặc timeout → `PENDING` và dispatcher gửi lại khi hết lease hay tới hạn backoff; 4xx khác 408/429 → `DEAD`.
- **Kiểm thử (2026-11-10):** `./mvnw verify` 102 unit + 113 integration, 0 lỗi; `check-migrations.ps1`, `check-docs.ps1` xanh. Test chính: `DocumentMetadataVisibilityIT`, `DocumentServiceTest`, `CategoryServiceTest`, `OutboxDispatcherIT`.
- **Lệch so với TECH-V2-core-api:** phòng ban rỗng, sai, khác workspace hoặc `ARCHIVED` và category `ARCHIVED` trả `400` (`VALIDATION_FAILED`, `CATEGORY_ARCHIVED`); TECH §5.6 không quy định mã. Category và tag không trả `documentCount`.
- **Nghiệm thu (owner, 2026-11-10):** `done`. Chưa chạy hai service thật với nhau (ai-service mock trong IT); frontend thuộc `V2-33`.
