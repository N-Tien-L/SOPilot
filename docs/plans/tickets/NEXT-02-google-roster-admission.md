---
ticket_id: NEXT-02
title: "Áp dụng chính sách roster cho đăng nhập Google của tài khoản cũ"
type: fix
scope: auth
priority: P1
size: M
status: todo
parent_plan: PLAN-NEXT
depends_on: [NEXT-01]
---

# NEXT-02: Áp dụng chính sách roster cho đăng nhập Google của tài khoản cũ

## Context
Audit 2026-10-14: F02. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Existing active user ngoài roster bị xử lý đúng policy, không mặc nhiên bypass.
- [ ] New/claimed/deactivated/locked user và ngoại lệ admin có test riêng.
- [ ] Token/session chỉ phát sau khi đủ điều kiện; contract và status code có bằng chứng.

## Implementation Guide
Đọc ADR đã chốt ở NEXT-01. Thay nhánh existing user theo policy; không gọi claim lại cho roster đã CLAIMED. Nếu cần internal API kiểm tra eligibility, thiết kế contract và ticket user-service riêng trước. Giữ semantics revoked/lock/status và cập nhật `.agent/context/service-boundaries/api-contracts.md` nếu đổi API.

## Files / Scope
- `services/auth-service/src/main/java/com/poliwise/auth/service/AuthService.java`
- `services/auth-service/src/main/java/com/poliwise/auth/feign/UserServiceClient.java`
- `services/auth-service/src/test/java/com/poliwise/auth/service/AuthServiceTest.java`

## Verification
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-tests.ps1 -Scope auth-service -Type all`; sau đó chạy E2E M1-06.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
