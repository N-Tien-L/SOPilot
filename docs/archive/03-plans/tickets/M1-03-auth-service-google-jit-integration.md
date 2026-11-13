---
id: M1-03
title: "Auth-Service: Google Token Verification & JIT Integration"
type: feat
status: superseded
created: 2026-09-27
updated: 2026-11-08
author: "Owner"
scope: auth
priority: P0
size: M
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: [M1-02]
blocks: [M1-04]
branch: "feat/auth-google-jit"
assignee: pair
---

> **Ghi chú 2026-10-20 (V2-04):** đóng `superseded` ngày 2026-11-08 (trạng thái cũ: `review`); giữ file làm lịch sử, không làm tiếp trên kiến trúc cũ. Phần còn giá trị được port sang [V2-11](../../../03-plans/tickets/V2-11-core-api-identity-workspace.md). Xác minh Google ID token và xoay vòng refresh token được giữ; claim JIT qua roster bị bỏ (ADR-005).

## Context
`auth-service` chịu trách nhiệm xác thực mật mã các token đăng nhập và phát hành JWT session. Ticket này triển khai xác thực Google ID Token với Google JWKS, gọi internal claim sang `user-service`, và cấp phát Access Token + Refresh Token chuẩn của hệ sinh thái SOPilot.

## Acceptance Criteria
- [x] Thêm cấu hình `auth.oauth.google.client-id` trong `application.yml` và properties.
- [x] Service `GoogleTokenVerifierService` xác thực chữ ký số RSA-256 từ `https://www.googleapis.com/oauth2/v3/certs`, cache public keys trong RAM (TTL 60 phút).
- [x] Kiểm tra chặt chẽ các claims: `aud == clientId`, `iss`, `exp > now`, `email_verified == true`.
- [x] Sử dụng OpenFeign Client `UserServiceClient` gọi sang `user-service:8082/internal/v1/roster/claim`.
- [x] Endpoint `POST /api/v1/auth/google/verify` nhận `{ idToken }`, xử lý claim, trả về Access Token, Refresh Token và User info.
- [x] Nếu `user-service` trả về `ROSTER_NOT_FOUND`, endpoint trả về HTTP 403 Forbidden kèm mã lỗi và thông điệp hướng dẫn liên hệ HR.
- [x] Ghi nhận thành công/thất bại vào bảng `core.login_history`.

## Implementation Guide
1. **Thêm Feign Client & Jose4j / Nimbus-JOSE-JWT dependency**
   - **File:** `services/auth-service/pom.xml`
   - **Action:** MODIFY
   - **Details:** Thêm OpenFeign và thư viện JWT/JWKS verifier.

2. **Tạo Feign Client kết nối user-service**
   - **File:** `services/auth-service/src/main/java/com/poliwise/auth/feign/UserServiceClient.java`
   - **Action:** CREATE
   - **Details:** Interface Feign gọi `POST /internal/v1/roster/claim` với header `X-Internal-Service-Token`.

3. **Xây dựng Google Token Verifier Service**
   - **File:** `services/auth-service/src/main/java/com/poliwise/auth/service/GoogleTokenVerifierService.java`
   - **Action:** CREATE
   - **Details:** Lấy và cache JWKS Google, verify RS256 signature và các claims.

4. **Tích hợp vào AuthController & AuthService**
   - **Files:**
     - `services/auth-service/src/main/java/com/poliwise/auth/controller/AuthController.java`
     - `services/auth-service/src/main/java/com/poliwise/auth/service/AuthService.java`
   - **Action:** MODIFY
   - **Details:** Thêm endpoint `POST /api/v1/auth/google/verify`, phát hành Access Token qua `JwtTokenProvider`, lưu Refresh Token vào `core.refresh_tokens`.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Unit | GoogleTokenVerifierService từ chối token có chữ ký sai hoặc sai audience | JUnit 5 + Mockito |
| Unit | GoogleTokenVerifierService từ chối token có `email_verified == false` | JUnit 5 |
| Integration | Luồng `POST /api/v1/auth/google/verify` mock Google JWKS và UserServiceClient trả về token hợp lệ | SpringBootTest |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `services/auth-service/pom.xml` | MODIFY | +15 |
| `services/auth-service/.../GoogleTokenVerifierService.java` | CREATE | +110 |
| `services/auth-service/.../UserServiceClient.java` | CREATE | +35 |
| `services/auth-service/.../AuthService.java` | MODIFY | +60 |
| `services/auth-service/.../AuthController.java` | MODIFY | +40 |
