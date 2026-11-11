---
id: V2-30
title: "core-api: lời mời, thành viên và quy tắc OWNER"
type: feat
status: done
created: 2026-10-24
updated: 2026-11-11
author: "Owner"
scope: user
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-29]
blocks: [V2-15, V2-33]
branch: "feat/user-v2-30"
assignee: pair
---

# TICKET V2-30: core-api: lời mời, thành viên và quy tắc OWNER

## 1. Bối cảnh & Mục tiêu
Tách FR-04 và phần P1 FR-05 khỏi V2-11. Theo TECH-V2-core-api §3.2, §5.3 và ADR-005.

## 2. Tiêu chí Hoàn thành
- [x] Lời mời: link dùng một lần, hạn 7 ngày, thu hồi được; email không khớp hoặc lời mời hết hiệu lực bị từ chối.
- [x] Chấp nhận lời mời tạo membership idempotent; hai request đồng thời không tạo trùng hoặc tái dùng link.
- [x] (Chuyển từ V2-29) Chấp nhận lời mời và các thao tác OWNER dùng lại `WorkspaceSessionService.switchTo` (cấp token cho workspace mới) và `RefreshTokenService.revokeForMembership` (thu hồi phiên khi đổi role/xóa), không nhân đôi logic phiên.
- [x] Luôn còn ≥ 1 OWNER; ADMIN không nâng/xóa OWNER; thao tác vượt workspace bị từ chối.
- [ ] (P1, có thể hoãn có ghi nhận) Domain join qua claim `hd` (FR-05). **Hoãn (2026-11-11):** chưa làm; ghi ở TECH-V2-core-api §16.
- [x] Không gửi email tự động nếu chưa được owner cho phép; API tạo link lời mời vẫn chạy được.
- [x] (Chuyển từ V2-23) Lời mời mang hồ sơ (`display_name`, `employee_code`, `job_title`, `department_id`; bảng `core.invitations` đã có ở `V004`) và áp vào membership khi chấp nhận; không mời vào phòng ban `ARCHIVED`; `employee_code` trùng trong workspace bị từ chối. Integration: mời kèm hồ sơ → chấp nhận → token có `wdept`.
- [ ] (P1, có thể hoãn có ghi nhận; chuyển từ V2-23, FR-24) Import CSV tạo lời mời hàng loạt, báo lỗi theo dòng. **Hoãn (2026-11-11):** chưa làm; ghi ở TECH-V2-core-api §16.

## 3. Hướng dẫn
1. Thêm controller/service trong `services/core-api/src/main/java/com/sopilot/core/member/`.
2. Thêm migration additive kế tiếp ở `infrastructure/db/migrations/core/` cho invitations/constraint nếu cần.
3. Bổ sung `services/core-api/src/test/` cho transaction và OWNER invariants; cập nhật API docs.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Unit: OWNER cuối, ADMIN nâng OWNER, email lệch, lời mời hết hạn/thu hồi.
- Integration: nhận link hai lần/đồng thời, hai OWNER tự rời cùng lúc, cách ly workspace.
- Lệnh: `./scripts/run-tests.ps1 -Scope core-api -Type all`, `./scripts/validate-build.ps1 -Scope core`, pre-commit.

## 5. Ghi chú triển khai và bằng chứng (2026-11-11)

- Migration `core/V008__invitation_acceptance.sql` (hàm `SECURITY DEFINER` `accept_invitation`, `pending_invitations_for_user`); V2-36 chuyển sang `V009`.
- Mã: `member/InvitationController|Service|Repository`, `MemberService` (role, quy tắc OWNER, đọc role người gọi từ DB), `pendingInvitations` trong `IdentityService`.
- Chỗ lệch TECH ghi ở TECH-V2-core-api §16 (nhận lại link cùng người là `200`, đổi role thu hồi phiên bằng `MEMBERSHIP_LOST`, hoãn FR-05 và FR-24).
- Kiểm thử: `InvitationServiceTest` (unit), `InvitationIT`, `OwnerPolicyIT` (gồm nhận đồng thời, hai OWNER rời cùng lúc, OWNER bị hạ còn token cũ, cách ly workspace). `./scripts/run-tests.ps1 -Scope core-api -Type all` xanh; `check-migrations.ps1` xanh; `tests/tenant-isolation` 31 passed.
- Chưa kiểm: không gửi email (ngoài phạm vi), chưa có giao diện (V2-15/V2-33).
