---
ticket_id: NEXT-01
title: "Chốt phạm vi sản phẩm và chính sách tài khoản kế thừa"
type: docs
scope: docs
priority: P1
size: M
status: todo
parent_plan: PLAN-NEXT
depends_on: []
---

# NEXT-01: Chốt phạm vi sản phẩm và chính sách tài khoản kế thừa

## Context
Audit 2026-10-14: F02, F05. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Có ma trận phạm vi cho mọi route hiện tại, chỉ rõ mục tiêu MVP và phần để sau.
- [ ] Chính sách existing user ngoài roster, admin bootstrap, password login, department/role được chủ sản phẩm chốt trước khi sửa auth.
- [ ] Mọi yêu cầu bỏ module có dependency map và tiêu chí regression.

## Implementation Guide
Lập bảng từng module/route hiện có: giữ, bỏ, sửa, nâng cấp, mới; ghi lý do và dependency API/event/table. Xác định persona và hành trình admin upload SOP → nhân viên hỏi đáp có citation. Đề xuất chính sách tài khoản cũ và admin bootstrap; không tự coi phương án đề xuất là quyết định đã duyệt.

## Files / Scope
- `docs/01-requirements/PRD-product-scope.md (tạo)`
- `docs/02-architecture/adr/ADR-003-legacy-account-access.md (tạo)`

## Verification
Đối chiếu `frontend/web/app`, các controller và PRD-M1; review tài liệu với chủ sản phẩm.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
