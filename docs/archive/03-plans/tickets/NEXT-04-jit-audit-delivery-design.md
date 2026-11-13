---
id: NEXT-04
title: "Chốt contract và cơ chế delivery audit JIT"
type: docs
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

> **Đóng 2026-10-20 (V2-04):** `superseded` bởi [PLAN-V2](../../../execution/initiatives/v2-sopilot-mvp/PLAN.md); không làm tiếp. Audit log tối thiểu là FR-20, thiết kế ở TECH-V2-core-api §3.6, triển khai ở V2-12.

# NEXT-04: Chốt contract và cơ chế delivery audit JIT

## Context
Audit 2026-10-14: F03. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Có mapping JSON/action/audit columns và tương thích event cũ.
- [ ] Có giải pháp cho DB rollback, broker outage, duplicate event và retry.
- [ ] Có ticket implementation từng service với acceptance và thứ tự phụ thuộc, M1-06 xác minh SQL.

## Implementation Guide
Trace publisher → exchange/routing key → consumer → audit table. Thiết kế loginMethod GOOGLE_JIT, eventId/idempotency và lỗi publish/consumer. So sánh outbox với after-commit; after-commit đơn thuần không bảo đảm delivery. Sau khi review design, tách ticket migration/user publisher/feedback consumer; không gộp triển khai nhiều service trong ticket này.

## Files / Scope
- `services/user-service/src/main/java/com/poliwise/user/dto/event/UserRegisteredEvent.java`
- `services/user-service/src/main/java/com/poliwise/user/service/EmployeeRosterService.java`
- `services/feedback-service/src/main/java/com/poliwise/feedback (consumer audit cần xác định)`
- `docs/02-architecture/designs/TECH-jit-audit-delivery.md (tạo)`

## Verification
Review contract bằng source và PRD/M1-06; không đánh dấu delivery hoàn tất từ unit mock.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
