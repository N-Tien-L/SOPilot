---
id: M1-06
title: "Kiểm thử Tích hợp E2E & Xác thực Audit Trail"
type: test
status: superseded
created: 2026-10-15
updated: 2026-10-20
author: "Owner"
scope: tests
priority: P1
size: M
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: [M1-01, M1-02, M1-03, M1-04, M1-05]
blocks: []
branch: "test/m1-06-e2e-jit-verification"
assignee: pair
---

> **Đóng 2026-10-20 (V2-04):** `superseded` bởi [PLAN-V2](../../../execution/initiatives/v2-sopilot-mvp/PLAN.md); không làm tiếp. E2E của M1 không còn áp dụng; nghiệm thu V2 ở V2-14, V2-26 và V2-17 (parity).

## Context
Xác thực toàn diện luồng nghiệp vụ từ khâu HR nạp danh bạ, kiểm thử các trường hợp thành công/lỗi import, kiểm thử luồng đăng nhập 1-Click JIT của nhân viên, đối soát với RabbitMQ event và kiểm toán tại `feedback-service` (`analytics.audit_logs`).

## Acceptance Criteria
- [ ] Chạy thành công toàn bộ 15 test cases trong Test Suite của Milestone 1.
- [ ] Xác nhận luồng E2E: Admin nạp file -> User đăng nhập Google -> Tự động claim vào đúng phòng ban và role -> Vào thẳng trang chủ chatbot.
- [ ] Xác nhận luồng từ chối: Tài khoản không có trong danh bạ bị chặn 403 Forbidden và hiển thị thông báo hướng dẫn liên hệ HR.
- [ ] Xác nhận RabbitMQ phát và `feedback-service` tiêu thụ thành công `UserRegisteredEvent` (action: `USER_CREATE`, metadata: `loginMethod: GOOGLE_JIT`) và `UserAssignedToDepartmentEvent`.

## Implementation Guide
1. **Viết kịch bản E2E Test Suite**
   - **File:** `tests/e2e/jit-onboarding.spec.ts` (Playwright) hoặc Postman Collection `tests/postman/SOPilot_M1_JIT.postman_collection.json`
   - **Action:** CREATE
   - **Details:** Script tự động hóa kiểm thử API và UI.

2. **Viết script kiểm tra Audit Log trong Database**
   - **File:** `tests/scripts/verify-jit-audit-log.sql`
   - **Action:** CREATE
   - **Details:** Truy vấn `analytics.audit_logs` kiểm tra bản ghi tương ứng sau khi claim.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| E2E | Toàn bộ luồng Import -> Google Login -> JIT Provisioning -> Chat access | Playwright / Newman |
| Integration | Audit Log ghi nhận đúng action `USER_CREATE` và phòng ban liên kết | SQL Assertion |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `tests/e2e/jit-onboarding.spec.ts` | CREATE | +180 |
| `tests/scripts/verify-jit-audit-log.sql` | CREATE | +30 |
