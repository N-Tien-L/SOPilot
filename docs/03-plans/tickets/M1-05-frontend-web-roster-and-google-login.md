---
id: M1-05
title: "Frontend Web: Giao diện Quản lý Roster & Google 1-Click Login"
type: feat
status: in-progress
created: 2026-10-15
updated: 2026-10-15
scope: web
priority: P1
size: L
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: [M1-04]
blocks: [M1-06]
branch: "feat/m1-05-web-roster-and-google-login"
assignee: pair
---

## Context
Checkpoint 2026-10-15: đã có UI login/403, roster, upload và API/types. Giữ acceptance chưa tick cho đến kiểm tra runtime. CSV backend còn thiếu; client ID phải được cấu hình trước khi build frontend. Xem `docs/04-reports/HANDOFF-implementation-2026-10-15.md`.

Xây dựng trải nghiệm người dùng hoàn chỉnh: nút "Sign in with Google" tại trang đăng nhập, xử lý 403 Forbidden bằng màn hình Access Denied thân thiện, và bổ sung Tab "Danh bạ chờ kích hoạt" kèm modal upload Excel tại trang Admin Quản lý Người dùng.

## Acceptance Criteria
- [ ] Trang `/login`: Tích hợp nút "Đăng nhập bằng Google Workspace" chính thức (Google Branding). Bấm mở Google Identity popup, gửi `idToken` lên backend và tự động đăng nhập khi thành công.
- [ ] Xử lý lỗi 403 `ROSTER_NOT_FOUND`: Hiển thị Error Card / màn hình Access Denied thân thiện ("Tài khoản của bạn chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR") kèm nút chọn tài khoản khác.
- [ ] Trang `/admin/users`: Thêm Tab "Nhân viên hoạt động" và "Danh bạ chờ kích hoạt". Tab Roster hiển thị danh sách PENDING kèm counter badge, phân trang, lọc phòng ban và tìm kiếm keyword.
- [ ] Nút "Tải file mẫu (.xlsx)": Tải file Excel mẫu 2 sheet từ API `/roster/template`.
- [ ] Modal "Nhập danh bạ Excel": Kéo thả upload file, hiển thị thanh loading, báo cáo chi tiết số lượng thành công và danh sách lỗi từng dòng nếu có.
- [ ] Bổ sung các phương thức gọi API trong `frontend/web/lib/api.ts` (`api.auth.googleVerify`, `api.roster.import`, `api.roster.list`, `api.roster.downloadTemplate`).

## Implementation Guide
1. **Bổ sung Google OAuth Provider & API Client**
   - **File:** `frontend/web/lib/api.ts`
   - **Action:** MODIFY
   - **Details:** Thêm các hàm API client cho `roster` và `auth.googleVerify`.

2. **Cập nhật màn hình `/login`**
   - **Files:**
     - `frontend/web/app/login/page.tsx`
     - `frontend/web/app/login/login.module.css`
   - **Action:** MODIFY
   - **Details:** Thêm Google One Tap / Google Button, state loading, và màn hình cảnh báo 403 Access Denied.

3. **Cập nhật màn hình `/admin/users`**
   - **Files:**
     - `frontend/web/app/admin/users/page.tsx`
     - `frontend/web/app/admin/users/components/RosterTab.tsx`
     - `frontend/web/app/admin/users/components/RosterUploadModal.tsx`
     - `frontend/web/app/admin/users/admin-users.module.css`
   - **Action:** CREATE / MODIFY
   - **Details:** Thêm tab navigation, table roster và modal upload.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Component | RosterUploadModal hiển thị lỗi khi upload file sai định dạng (không phải xlsx/csv) | React Testing Library / Jest |
| E2E | Bấm Google Sign-in gọi API verify và lưu token vào AuthStore | Playwright |
| Visual | Responsive trên mobile và desktop | Manual / Storybook |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `frontend/web/lib/api.ts` | MODIFY | +60 |
| `frontend/web/app/login/page.tsx` | MODIFY | +80 |
| `frontend/web/app/admin/users/page.tsx` | MODIFY | +70 |
| `frontend/web/app/admin/users/components/RosterTab.tsx` | CREATE | +160 |
| `frontend/web/app/admin/users/components/RosterUploadModal.tsx` | CREATE | +140 |
