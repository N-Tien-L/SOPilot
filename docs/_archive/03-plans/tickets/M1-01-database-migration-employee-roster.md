---
id: M1-01
title: "Database Schema Migration cho Employee Roster"
type: feat
status: done
created: 2026-09-25
updated: 2026-09-25
author: "Owner"
scope: infra
priority: P0
size: S
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: []
blocks: [M1-02]
branch: "feat/m1-01-db-employee-roster"
assignee: pair
---

## Context
Phục vụ tính năng Google 1-Click JIT Onboarding, hệ thống cần bảng `core.employee_roster` để lưu trữ danh bạ nhân sự do Admin/HR nạp trước. Bảng này đóng vai trò whitelist định danh, cho phép đối soát email khi nhân viên đăng nhập lần đầu.

## Acceptance Criteria
- [x] File migration `infrastructure/init-db/010_employee_roster.sql` chạy thành công trên PostgreSQL 16.
- [x] Bảng `core.employee_roster` có đầy đủ các trường: `employee_code`, `email`, `full_name`, `phone`, `position`, `department_id`, `role`, `status`, `is_claimed`, `claimed_at`, `claimed_user_id`, `import_batch_id`.
- [x] Unique index `LOWER(email)` và `employee_code` hoạt động chính xác (chặn trùng lặp hoa/thường).
- [x] Khóa ngoại `department_id` có ràng buộc `ON DELETE RESTRICT`.
- [x] Check constraints cho format email và tính nhất quán của trạng thái `is_claimed`.
- [x] Trigger `trg_employee_roster_updated_at` tự động cập nhật `updated_at`.

## Implementation Guide
1. **Kiểm tra và chuẩn hóa DDL script**
   - **File:** `infrastructure/init-db/010_employee_roster.sql`
   - **Action:** VERIFY & RUN
   - **Details:** Đảm bảo script hỗ trợ idempotency (`IF NOT EXISTS`), enum `core.roster_status` và trigger timestamp.

2. **Cập nhật script reset và bootstrap**
   - **File:** `infrastructure/init-db/reset-and-bootstrap.ps1`
   - **Action:** MODIFY
   - **Details:** Đảm bảo file `010_employee_roster.sql` được nạp trong chuỗi script khởi tạo môi trường dev.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Integration | Chạy migration trên PostgreSQL container | `docker-compose` / psql CLI |
| Unit | Thử INSERT trùng email khác hoa thường (`test@co.com` vs `Test@co.com`) văng lỗi unique constraint | SQL Script |
| Unit | Thử xóa department có nhân viên trong roster văng lỗi foreign key constraint | SQL Script |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `infrastructure/init-db/010_employee_roster.sql` | CREATE | +75 |
| `infrastructure/init-db/reset-and-bootstrap.ps1` | MODIFY | +5 |
