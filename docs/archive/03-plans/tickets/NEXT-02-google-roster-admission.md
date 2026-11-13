---
id: NEXT-02
title: "Áp dụng chính sách roster cho đăng nhập Google của tài khoản cũ"
type: fix
status: superseded
created: 2026-10-15
updated: 2026-11-08
author: "Owner"
scope: auth
priority: P1
size: M
parent_plan: PLAN-NEXT
depends_on: []
---

> **Ghi chú 2026-10-20 (V2-04):** đóng `superseded` ngày 2026-11-08 (trạng thái cũ: `review`); giữ file làm lịch sử, không làm tiếp trên kiến trúc cũ. Phần còn giá trị được port sang [V2-11](../../../execution/initiatives/v2-sopilot-mvp/tickets/V2-11-core-api-identity-workspace.md). Binding `(issuer, sub)` và xác minh Google ID token được giữ (ADR-004 §4.5); kiểm tra roster bị bỏ (ADR-005).

# NEXT-02: Áp dụng chính sách roster cho đăng nhập Google của tài khoản cũ

## Context
Policy auth ???c ng??i d?ng cho ph?p tri?n khai ng?y 2026-10-15, ghi t?i ADR-003-google-identity-and-roster-admission.md. ??y l? quy?t ??nh auth c? ph?m vi ri?ng, kh?ng ??nh d?u NEXT-01 (ma tr?n to?n s?n ph?m) done. Ph? thu?c NEXT-01 ???c g? cho ph?n auth ?? ch?t.

Audit 2026-10-14: F02. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [x] Existing active user ngoài roster bị xử lý đúng policy, không mặc nhiên bypass.
- [x] New/claimed/deactivated/locked user và ngoại lệ admin có test riêng.
- [x] Token/session chỉ phát sau khi đủ điều kiện; contract và status code có bằng chứng.

## Implementation Guide
Đọc ADR đã chốt ở NEXT-01. Thay nhánh existing user theo policy; không gọi claim lại cho roster đã CLAIMED. Nếu cần internal API kiểm tra eligibility, thiết kế contract và ticket user-service riêng trước. Giữ semantics revoked/lock/status và cập nhật `.agent/context/service-boundaries/api-contracts.md` nếu đổi API.

## Files / Scope
- `services/auth-service/src/main/java/com/poliwise/auth/service/AuthService.java`
- `services/auth-service/src/main/java/com/poliwise/auth/feign/UserServiceClient.java`
- `services/auth-service/src/test/java/com/poliwise/auth/service/AuthServiceTest.java`

## Verification
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-tests.ps1 -Scope auth-service -Type all`; sau đó chạy E2E M1-06.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.

## Evidence 2026-10-15
41 auth tests, 23 user tests, 42 gateway tests v? 28 HTTP/PostgreSQL checks pass. C? 3 batch x 6 login ??ng th?i, issuer canonicalization, ??i email, ch?ng kh?c subject, admin fallback, legacy mismatch v? refresh replay/expiration/logout. Xem docs/_archive/04-reports/AUDIT-google-admission-2026-10-15.md. Tr?ng th?i review kh?ng thay cho Google hosted UI ho?c to?n b? M1-06.
