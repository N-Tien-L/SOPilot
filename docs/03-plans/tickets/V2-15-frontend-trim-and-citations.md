---
id: V2-15
title: "Frontend: thu gọn, chọn workspace, trình xem trích dẫn"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: web
priority: P0
size: XL
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-12, V2-23, V2-24, V2-25]
blocks: [V2-17]
branch: "feat/web-v2-workspace-citations"
assignee: pair
---

# TICKET V2-15: Frontend V2

## 1. Bối cảnh & Mục tiêu
Giữ các component chat; bỏ trang admin hệ thống, analytics, roster, phòng ban, OnlyOffice, so sánh version, UI chọn model. Điều phối theo skill `frontend-delivery` (CLAUDE.md toàn cục).

## 2. Tiêu chí Hoàn thành
- [ ] Đăng nhập Google; chọn/chuyển workspace; token giữ theo workspace (T8).
- [ ] Trang: chat, tài liệu, thành viên + lời mời, khoảng trống tri thức, cài đặt workspace.
- [ ] Thành viên: hồ sơ (họ tên, mã nhân viên, chức danh, phòng ban), tạm khóa/mở khóa; phòng ban và category phẳng: tạo, đổi tên, ngừng sử dụng, xóa khi hợp lệ. Ẩn phòng ban ở workspace một thành viên.
- [ ] Tài liệu: sửa metadata, chọn phạm vi `WORKSPACE`/`DEPARTMENTS`, xem và chấp nhận/sửa gợi ý metadata; trạng thái gợi ý không chặn thao tác khác.
- [ ] Trình xem trích dẫn: bấm `[n]` mở đúng trang PDF / đúng đoạn, tô sáng nguồn (FR-14).
- [ ] Hiển thị từ chối "không tìm thấy" và trạng thái xử lý tài liệu.
- [ ] Xóa enum model OpenAI không dùng và mọi gọi tới gateway cũ.
- [ ] Sửa 61 lỗi lint hiện có hoặc loại bỏ cùng code bị cắt; `pnpm build` và `pnpm lint` xanh.
- [ ] **Kiểm tra bằng trình duyệt thật** các UC-01, 02, 04, 05, 07 đến 11; báo rõ nếu chưa kiểm tra (build/lint không thay thế được).

## 3. Hướng dẫn
- **File:** `frontend/web/` theo `.agent/rules/frontend.md`; API client `frontend/web/lib/api.ts`; types `frontend/web/types`.

## 4. Kiểm thử
```powershell
./scripts/validate-build.ps1 -Scope web
```
Cộng ghi chú các luồng đã thử tay trên trình duyệt.
