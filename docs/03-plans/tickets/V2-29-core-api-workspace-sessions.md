---
id: V2-29
title: "core-api: workspace CRUD, chuyển workspace và refresh session"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-09
author: "Owner"
scope: user
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-11]
blocks: [V2-15, V2-30]
branch: "feat/user-v2-29"
assignee: pair
---

# TICKET V2-29: core-api: workspace CRUD, chuyển workspace và refresh session

## 1. Bối cảnh & Mục tiêu
Tách phần FR-03 khỏi V2-11 XL. Theo TECH-V2-core-api §3.1–§3.2, §4, §5.1–§5.2; không đổi contract đã duyệt.

## 2. Tiêu chí Hoàn thành
- [ ] Workspace CRUD, liệt kê và chuyển workspace theo membership; không truy cập workspace khác chỉ bằng ID.
- [ ] Token ≤ 15 phút gắn `workspace_id`, role và chỗ cho `wdept`; refresh kiểm trạng thái membership và nhận giá trị hiện hành.
- [ ] Refresh token xoay vòng, phát hiện replay và thu hồi session theo TECH; không log token, lỗi không lộ nội bộ.
- [ ] RLS context được đặt trong transaction, connection trả pool không giữ tenant cũ.
- [ ] JWKS công bố khóa hiện hành và khóa trước đó (TECH §5.1) để xoay khóa ký không làm rớt phiên; V2-11 mới có khóa hiện hành.
- [ ] Lời mời/OWNER policy của V2-30 dùng lại dịch vụ workspace/session này, không nhân đôi logic.

## 3. Hướng dẫn
1. Port refresh rotation từ `services/auth-service` vào `services/core-api/src/main/java/com/sopilot/core/identity/`.
2. Thêm workspace controller/service/repository trong `services/core-api/src/main/java/com/sopilot/core/workspace/`.
3. Thêm migration kế tiếp trong `infrastructure/db/migrations/core/` cho session/workspace nếu chưa thuộc V2-11; không sửa migration đã chạy.
4. Thêm test trong `services/core-api/src/test/`, cập nhật README và API contract.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Unit: token sai/hết hạn, workspace không có membership, session bị thu hồi.
- Integration Postgres: refresh replay, chuyển workspace, rollback và tái sử dụng connection khác tenant.
- Lệnh: `./scripts/run-tests.ps1 -Scope core-api -Type all`, `./scripts/validate-build.ps1 -Scope core` (scope do V2-11 dựng), pre-commit.
