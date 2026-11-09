---
id: V2-30
title: "core-api: lời mời, thành viên và quy tắc OWNER"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-09
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
- [ ] Lời mời: link dùng một lần, hạn 7 ngày, thu hồi được; email không khớp hoặc lời mời hết hiệu lực bị từ chối.
- [ ] Chấp nhận lời mời tạo membership idempotent; hai request đồng thời không tạo trùng hoặc tái dùng link.
- [ ] (Chuyển từ V2-29) Chấp nhận lời mời và các thao tác OWNER dùng lại `WorkspaceSessionService.switchTo` (cấp token cho workspace mới) và `RefreshTokenService.revokeForMembership` (thu hồi phiên khi đổi role/xóa), không nhân đôi logic phiên.
- [ ] Luôn còn ≥ 1 OWNER; ADMIN không nâng/xóa OWNER; thao tác vượt workspace bị từ chối.
- [ ] (P1, có thể hoãn có ghi nhận) Domain join qua claim `hd` (FR-05).
- [ ] Không gửi email tự động nếu chưa được owner cho phép; API tạo link lời mời vẫn chạy được.

## 3. Hướng dẫn
1. Thêm controller/service trong `services/core-api/src/main/java/com/sopilot/core/member/`.
2. Thêm migration additive kế tiếp ở `infrastructure/db/migrations/core/` cho invitations/constraint nếu cần.
3. Bổ sung `services/core-api/src/test/` cho transaction và OWNER invariants; cập nhật API docs.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Unit: OWNER cuối, ADMIN nâng OWNER, email lệch, lời mời hết hạn/thu hồi.
- Integration: nhận link hai lần/đồng thời, hai OWNER tự rời cùng lúc, cách ly workspace.
- Lệnh: `./scripts/run-tests.ps1 -Scope core-api -Type all`, `./scripts/validate-build.ps1 -Scope core`, pre-commit.
