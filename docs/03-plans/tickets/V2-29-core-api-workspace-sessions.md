---
id: V2-29
title: "core-api: workspace CRUD, chuyển workspace và refresh session"
type: feat
status: done
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
- [x] Workspace CRUD, liệt kê và chuyển workspace theo membership; không truy cập workspace khác chỉ bằng ID. (tạo TEAM, liệt kê, `/current` đọc/đổi tên/xóa mềm; đổi workspace trả `404` khi không là thành viên; quản trị luôn dùng `wid` của token. **Xóa cứng** dòng workspace sau khi ai-service xác nhận chưa làm, xem TECH §14)
- [x] Token ≤ 15 phút gắn `workspace_id`, role và chỗ cho `wdept`; refresh kiểm trạng thái membership và nhận giá trị hiện hành.
- [x] Refresh token xoay vòng, phát hiện replay và thu hồi session theo TECH; không log token, lỗi không lộ nội bộ. (kèm kiểm `Origin`, thu hồi khi tạm khóa/xóa/rời)
- [x] RLS context được đặt trong transaction, connection trả pool không giữ tenant cũ. (`TenantTx` như V2-12; `TenantIsolationIT` dùng pool 1 connection)
- [x] JWKS công bố khóa hiện hành và khóa trước đó (TECH §5.1) để xoay khóa ký không làm rớt phiên; V2-11 mới có khóa hiện hành. (`SOPILOT_JWT_PREVIOUS_PUBLIC_KEY_PATH`; verifier chọn khóa theo `kid`)
- [x] Lời mời/OWNER policy của V2-30 dùng lại dịch vụ workspace/session này, không nhân đôi logic. (chỉ kiểm được khi làm V2-30; chuyển thành tiêu chí của V2-30. Điểm tái sử dụng: `WorkspaceSessionService.switchTo`, `RefreshTokenService.revokeForMembership`)

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

## 5. Bằng chứng triển khai (2026-11-08, nghiệm thu 2026-11-09)

Owner nghiệm thu 2026-11-09, chuyển `done`. Code ở commit `6ec8dde`, `622359e`, merge vào `develop` (`e127c07`). Chỗ lệch TECH ở TECH-V2-core-api §14 được duyệt; **xóa cứng dòng workspace** owner chốt là ngoài MVP (chạy local, xóa mềm đã chặn truy cập và refresh), không thêm ticket. Kiểm lại khi nghiệm thu: `./mvnw -B verify` trên `develop` (`c71138b`) -> 78 unit + 101 integration, 0 lỗi (`SessionWorkspaceIT` 23); GitHub Actions trên `develop` xanh (`Poliwise CI` run 42506269350, `Tenant isolation (FR-19)` run 42506269294, 2026-11-08). Đọc lại `RefreshTokenService`, `WorkspaceSessionService`, `WorkspaceService`, `V006`: token chỉ lưu SHA-256, khóa dòng khi xoay, dùng lại token cũ thu hồi cả family và việc thu hồi được commit (trả kết quả từ chối thay vì ném lỗi), membership đọc lại mỗi lần refresh và bỏ qua workspace đã xóa.

- **Ghi chú review (không chặn):** (1) xoay vòng chặt: hai tab gửi cùng cookie refresh gần như đồng thời thì lần thứ hai bị coi là dùng lại và cả phiên bị đăng xuất; frontend (V2-15) cần gộp các lần refresh đồng thời thành một. (2) `RefreshTokenService.revokeForWorkspace` hiện không được gọi (xóa workspace dựa vào `findMembership` theo TECH §14).

- **Code:** `services/core-api/src/main/java/com/sopilot/core/identity/` (`RefreshTokenService`, `RefreshTokenRepository`, `WorkspaceSessionService`, `WorkspaceSessionController`, `AuthController`), `workspace/` (`WorkspaceService`, `WorkspaceController`), `security/` (`SigningKeyProvider`, `AccessTokenVerifier`, `WorkspaceRole`); migration `V006__refresh_tokens_and_workspace_soft_delete.sql`.
- **Lệnh:** `./mvnw verify` trong `services/core-api` -> 78 unit + 101 integration, 0 lỗi (mới: `SessionWorkspaceIT` 23 test trên Postgres thật, `SigningKeyRotationTest` 5 test). `tests/tenant-isolation` -> 31 passed. `./scripts/check-migrations.ps1` -> đạt.
- **Phủ:** xoay vòng và token mới cùng family; dùng lại token cũ thu hồi cả chuỗi (kể cả token kế nhiệm); token lạ/hết hạn; role đọc lại từ DB; tạm khóa (`403 MEMBERSHIP_SUSPENDED`) và mất membership (`401 MEMBERSHIP_LOST`); tạm khóa/xóa qua API thu hồi chuỗi ngay; `Origin` sai/thiếu -> `403`; cookie `HttpOnly; SameSite=Strict; Path=/api/v1/auth`; đăng xuất luôn `204`; đổi workspace (thành viên, không phải thành viên `404`, bị khóa `403`, thiếu bearer `401`); tạo workspace (kiểm tên, OWNER, token mới); chỉ OWNER đổi tên/xóa; workspace cá nhân không xóa được; xóa workspace sinh một `DOCUMENT_DELETED` mỗi tài liệu và chặn refresh; token ký bằng khóa trước đó vẫn được chấp nhận, khóa lạ hoặc `kid` giả bị từ chối.
- **Lệch/ghi chú:** xem TECH-V2-core-api §14. Đáng chú ý: cột `refresh_tokens.target_workspace_id` (không phải `workspace_id`) để bảng toàn cục không bị bộ cách ly coi là bảng tenant; `WorkspaceRole` chuyển sang `security`; tạo/đổi workspace nằm ở `identity` để `ArchitectureTest` không báo vòng.
- **Chưa làm:** xóa cứng dòng workspace (ngoài MVP, owner chốt 2026-11-09); domain join (FR-05, P1, tiêu chí của V2-30); xác nhận V2-30 dùng lại dịch vụ này (tiêu chí của V2-30); chưa chạy hai service thật cùng lúc. ~~Chưa có run GitHub Actions~~: đã xanh trên `develop` 2026-11-08.
- **Docs:** `services/core-api/README.md`, `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `.env.example`, TECH-V2-core-api §14, PLAN-V2.
