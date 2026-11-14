---
id: NEXT-03
title: "Hoàn thiện import CSV theo PRD-M1"
type: fix
status: superseded
created: 2026-10-15
updated: 2026-10-20
author: "Owner"
scope: user
priority: P1
size: M
parent_plan: PLAN-NEXT
depends_on: []
---

> **Đóng 2026-10-20 (V2-04):** `superseded` bởi [PLAN-V2](../../../execution/initiatives/v2-sopilot-mvp/PLAN.md); không làm tiếp. Roster tạo trước bị bỏ (ADR-005); import thành viên từ CSV là FR-24 (P1) thuộc V2-23.

# NEXT-03: Hoàn thiện import CSV theo PRD-M1

## Context
Audit 2026-10-14: F01. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Một CSV UTF-8 hợp lệ được import đúng tên tiếng Việt, phòng ban và role.
- [ ] CSV lỗi trả báo cáo từng dòng theo cùng contract Excel; Excel không hồi quy.
- [ ] Upload qua gateway và UI được xác minh; giới hạn file được mô tả.

## Implementation Guide
Thêm parser CSV, tái sử dụng validation từng dòng và RosterImportResponse hiện hữu. Chốt encoding/delimiter/header được hỗ trợ trong contract; không tự loại CSV khỏi PRD. Kiểm tra UTF-8/BOM, quoted values, email/code trùng, department không tồn tại và file sai định dạng.

## Files / Scope
- `services/user-service/src/main/java/com/poliwise/user/service/RosterExcelService.java`
- `services/user-service/src/main/java/com/poliwise/user/controller/EmployeeRosterController.java`
- `services/user-service/src/test/java/com/poliwise/user/service/RosterExcelServiceTest.java`

## Verification
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-tests.ps1 -Scope user-service -Type all`; kiểm tra upload thật trên test stack.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
