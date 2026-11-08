---
id: V2-15
title: "Frontend: khung V2, đăng nhập/workspace, chat và khoảng trống"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-24
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-13, V2-29, V2-30]
blocks: [V2-17, V2-31, V2-32, V2-33]
branch: "feat/web-v2-workspace-citations"
assignee: pair
---

# TICKET V2-15: Frontend V2

## 1. Bối cảnh & Mục tiêu
Giữ các component chat; bỏ trang admin hệ thống, analytics, roster, cây phòng ban V1, OnlyOffice, so sánh version, UI chọn model. Phòng ban phẳng V2 thuộc V2-33. Điều phối theo skill `frontend-delivery` (CLAUDE.md toàn cục). Sửa 2026-10-21 theo [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) §4: luồng nạp ≤ 10 file và màn "Nội dung hệ thống nhận diện" (PRD-V2 FR-30, FR-31, UC-12). Đã tách XL ngày 2026-10-24: upload V2-31, viewer V2-32, quản trị V2-33; giữ nguyên toàn bộ tiêu chí, không thêm phạm vi.

## 2. Tiêu chí Hoàn thành
- [ ] Đăng nhập Google; chọn/chuyển workspace; token giữ theo workspace (T8).
- [ ] Khung điều hướng: chat, tài liệu, thành viên + lời mời, khoảng trống tri thức, cài đặt workspace; màn chi tiết tài liệu/quản trị ở V2-31/V2-32/V2-33.
- [ ] Sửa 2026-10-21 (owner chốt D10, TECH-V2-ai-service §7.5): trích dẫn có `isCurrentVersion = false` hiện đoạn trích đã lưu kèm nhãn "Phiên bản cũ" và **không** mở trình xem (`/content` chỉ phục vụ phiên bản hiện hành). Hiển thị `refusal` theo `reason`: `NO_EVIDENCE` kèm tài liệu gần nhất, `OUT_OF_SCOPE` và `INPUT_INVALID` không kèm; hiển thị `done.warnings` (`NUMBER_NOT_IN_SOURCES`) dạng nhắc "kiểm tra lại số liệu với nguồn".
- [ ] Hiển thị từ chối "không tìm thấy" và trạng thái xử lý tài liệu.
- [ ] Xóa enum model OpenAI không dùng và mọi gọi tới gateway cũ.
- [ ] Sửa 61 lỗi lint hiện có hoặc loại bỏ cùng code bị cắt; `pnpm build` và `pnpm lint` xanh.
- [ ] **Kiểm tra bằng trình duyệt thật** các luồng đăng nhập/chọn workspace/chat/khoảng trống trong phạm vi ticket (bố cục màn hẹp); upload/viewer/quản trị nghiệm thu ở V2-31/V2-32/V2-33; báo rõ nếu chưa kiểm tra (build/lint không thay thế được).

## 3. Hướng dẫn
- **File:** `frontend/web/` theo `.claude/rules/frontend.md`; API client `frontend/web/lib/api.ts`; types `frontend/web/types`.
- **Giữ bản demo chạy được trong lúc chuyển (ADR-004 §4.5):** frontend sửa tại chỗ, nên khi bỏ gọi gateway cũ thì nó không còn chạy với stack cũ.
  - Chỉ bắt đầu nối API khi các ticket trong `depends_on` đã có endpoint chạy được trên `docker-compose.v2.yml`; trước đó chỉ làm phần UI không phụ thuộc backend (thu gọn trang, component trình xem) trên nhánh của ticket.
  - Đích của `rewrites` (TECH-V2-core-api §1.1) đọc từ env server-side (`CORE_API_URL`, mặc định `http://core-api:8080`; `AI_SERVICE_URL`, mặc định `http://ai-service:8000`) để chạy được cả trong compose lẫn `pnpm dev` trên host. Ghi vào `frontend/web/.env.example`.
  - Trước khi merge nhánh này vào `develop`, tạo tag `v1-final` trên `develop` (commit cuối frontend còn chạy với stack cũ). Bản demo dự phòng: `git checkout v1-final` + `docker-compose.yml` cũ. V2-17 dùng lại tag này.

## 4. Kiểm thử
```powershell
./scripts/validate-build.ps1 -Scope web
```
Cộng ghi chú các luồng đã thử tay trên trình duyệt.
