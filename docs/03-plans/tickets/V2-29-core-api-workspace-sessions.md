---
id: V2-29
title: "core-api: workspace CRUD, chuyển workspace và refresh session"
type: feat
status: review
created: 2026-10-24
updated: 2026-11-08
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
- [x] Workspace CRUD, liệt kê và chuyển workspace theo membership; không truy cập workspace khác chỉ bằng ID. (tạo TEAM, liệt kê, `/current` đọc/đổi tên/xóa mềm; đổi workspace trả `404` khi không là thành viên; quản trị luôn dùng `wid` của token. **Xóa cứng** dòng workspace sau khi ai-service xác nhận chưa làm, xem TECH §14)
- [x] Token ≤ 15 phút gắn `workspace_id`, role và chỗ cho `wdept`; refresh kiểm trạng thái membership và nhận giá trị hiện hành.
- [x] Refresh token xoay vòng, phát hiện replay và thu hồi session theo TECH; không log token, lỗi không lộ nội bộ. (kèm kiểm `Origin`, thu hồi khi tạm khóa/xóa/rời)
- [x] RLS context được đặt trong transaction, connection trả pool không giữ tenant cũ. (`TenantTx` như V2-12; `TenantIsolationIT` dùng pool 1 connection)
- [x] JWKS công bố khóa hiện hành và khóa trước đó (TECH §5.1) để xoay khóa ký không làm rớt phiên; V2-11 mới có khóa hiện hành. (`SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH`; verifier chọn khóa theo `kid`)
- [ ] Lời mời/OWNER policy của V2-30 dùng lại dịch vụ workspace/session này, không nhân đôi logic. **Chưa kiểm được:** chỉ xác nhận khi làm V2-30 (`WorkspaceSessionService.switchTo`, `RefreshTokenService.revokeForMembership` là điểm tái sử dụng).

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

## 5. Bằng chứng triển khai (2026-11-08, chờ owner nghiệm thu)

- **Code:** `services/core-api/src/main/java/com/sopilot/core/identity/` (`RefreshTokenService`, `RefreshTokenRepository`, `WorkspaceSessionService`, `WorkspaceSessionController`, `AuthController`), `workspace/` (`WorkspaceService`, `WorkspaceController`), `security/` (`SigningKeyProvider`, `AccessTokenVerifier`, `WorkspaceRole`); migration `V006__refresh_tokens_and_workspace_soft_delete.sql`.
- **Lệnh:** `./mvnw verify` trong `services/core-api` -> 78 unit + 101 integration, 0 lỗi (mới: `SessionWorkspaceIT` 23 test trên Postgres thật, `SigningKeyRotationTest` 5 test). `tests/tenant-isolation` -> 31 passed. `./scripts/check-migrations.ps1` -> đạt.
- **Phủ:** xoay vòng và token mới cùng family; dùng lại token cũ thu hồi cả chuỗi (kể cả token kế nhiệm); token lạ/hết hạn; role đọc lại từ DB; tạm khóa (`403 MEMBERSHIP_SUSPENDED`) và mất membership (`401 MEMBERSHIP_LOST`); tạm khóa/xóa qua API thu hồi chuỗi ngay; `Origin` sai/thiếu -> `403`; cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth`; đăng xuất luôn `204`; đổi workspace (thành viên, không phải thành viên `404`, bị khóa `403`, thiếu bearer `401`); tạo workspace (kiểm tên, OWNER, token mới); chỉ OWNER đổi tên/xóa; workspace cá nhân không xóa được; xóa workspace sinh một `DOCUMENT_DELETED` mỗi tài liệu và chặn refresh; token ký bằng khóa trước đó vẫn được chấp nhận, khóa lạ hoặc `kid` giả bị từ chối.
- **Lệch/ghi chú:** xem TECH-V2-core-api §14. Đáng chú ý: cột `refresh_tokens.target_workspace_id` (không phải `workspace_id`) để bảng toàn cục không bị bộ cách ly coi là bảng tenant; `WorkspaceRole` chuyển sang `security`; tạo/đổi workspace nằm ở `identity` để `ArchitectureTest` không báo vòng.
- **Chưa làm:** xóa cứng dòng workspace; domain join (FR-05, P1); xác nhận V2-30 dùng lại dịch vụ này; chưa chạy hai service thật cùng lúc và chưa có run GitHub Actions.
- **Docs:** `services/core-api/README.md`, `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `.env.example`, TECH-V2-core-api §14, PLAN-V2.
