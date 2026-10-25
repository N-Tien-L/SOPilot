---
id: V2-11
title: "core-api: khung service, Google identity, JIT và workspace cá nhân"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-24
scope: user
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-08]
blocks: [V2-12, V2-15, V2-23, V2-29]
branch: "feat/user-core-api-identity"
assignee: pair
---

# TICKET V2-11: core-api (danh tính và workspace)

## 1. Bối cảnh & Mục tiêu
Service Spring Boot `services/core-api` hợp nhất auth, user, metadata (phần còn lại). Port `GoogleTokenVerifierService`, liên kết `(issuer, sub)` từ code M1; xoay refresh token được port ở V2-29; thêm tenant (ADR-005). Phạm vi FR-01/FR-02; FR-03 chuyển V2-29, FR-04/FR-05 chuyển V2-30 (tách XL ngày 2026-10-24, giữ nguyên yêu cầu).

## 2. Tiêu chí Hoàn thành
- [ ] Xác minh Google ID token (RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`) **và kiểm tra `nonce`** (A9).
- [ ] User JIT theo `(issuer, sub)`; workspace cá nhân tự tạo, idempotent (FR-02).
- [ ] JWT ban đầu ≤ 15 phút gắn workspace cá nhân và role; một service ghi `users`/membership ban đầu. CRUD/chuyển workspace và refresh chuyển sang V2-29.
- [ ] Dev login chỉ ở profile `local`/`test`.
- [ ] Lỗi trả client không chứa `e.getMessage()` nội bộ (A8); không log token/secret.
- [ ] Chỉ một service ghi `users`.
- [ ] Token có chỗ cho claim `wdept` (giá trị điền ở V2-23); refresh và kiểm membership thuộc V2-29.

## 3. Hướng dẫn
- **Khung:** tạo `services/core-api/pom.xml`, Maven wrapper, `src/main/java/com/sopilot/core/`, `src/main/resources/application.yml`, `src/test/`; thêm scope `core`/`core-api` cho script build/test và ghi lệnh trong README service.
- **File:** `services/core-api/` (CREATE); nguồn port: `services/auth-service/.../GoogleTokenVerifierService`, `AuthService`, `services/user-service`.
- Cập nhật `.agent/context/authorization/` và `service-boundaries/` cùng thay đổi; V2-17 tổng hợp lại.
- Spring Boot/Java theo quyết định V2-01.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | verifier (token sai chữ ký, sai aud, hết hạn, nonce sai), token workspace cá nhân | `./mvnw test` |
| Integration | Postgres thật: JIT idempotent/concurrent, owner membership, schema isolation | `./mvnw verify` |

Ghi chú: Maven wrapper từng lỗi (AUDIT 2026-10-14); xác nhận `./mvnw` chạy được trước.
