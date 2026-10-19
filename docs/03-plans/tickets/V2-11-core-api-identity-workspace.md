---
id: V2-11
title: "core-api: Google login, JIT, workspace, thành viên, lời mời, dev login"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: user
priority: P0
size: XL
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-08]
blocks: [V2-12, V2-15, V2-23]
branch: "feat/user-core-api-identity"
assignee: pair
---

# TICKET V2-11: core-api (danh tính và workspace)

## 1. Bối cảnh & Mục tiêu
Service Spring Boot `services/core-api` hợp nhất auth, user, metadata (phần còn lại). Port `GoogleTokenVerifierService`, liên kết `(issuer, sub)` và xoay refresh token từ code M1; thêm tenant (ADR-005). Phạm vi FR-01 đến FR-05.

## 2. Tiêu chí Hoàn thành
- [ ] Xác minh Google ID token (RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`) **và kiểm tra `nonce`** (A9).
- [ ] User JIT theo `(issuer, sub)`; workspace cá nhân tự tạo, idempotent (FR-02).
- [ ] Workspace CRUD, liệt kê, chuyển workspace; token ≤ 15 phút gắn `workspace_id` và role; refresh xoay vòng + phát hiện dùng lại (FR-03).
- [ ] Lời mời: link một lần, hạn 7 ngày, thu hồi; email không khớp bị từ chối, lời mời còn hiệu lực. Luôn còn ≥ 1 `OWNER`; ADMIN không nâng/xóa `OWNER` (FR-04).
- [ ] Dev login chỉ ở profile `local`/`test`.
- [ ] Lỗi trả client không chứa `e.getMessage()` nội bộ (A8); không log token/secret.
- [ ] (P1, có thể hoãn) Domain join qua claim `hd` (FR-05).
- [ ] Chỉ một service ghi `users`.
- [ ] Token có chỗ cho claim `wdept` (giá trị điền ở V2-23); refresh kiểm tra trạng thái membership.

## 3. Hướng dẫn
- **File:** `services/core-api/` (CREATE); nguồn port: `services/auth-service/.../GoogleTokenVerifierService`, `AuthService`, `services/user-service`.
- Cập nhật `.agent/context/authorization/` và `service-boundaries/` trong ticket V2-17.
- Spring Boot/Java theo quyết định V2-01.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | verifier (token sai chữ ký, sai aud, hết hạn, nonce sai), quy tắc OWNER | `./mvnw test` |
| Integration | Postgres thật: JIT idempotent, lời mời, refresh replay | `./mvnw verify` |

Ghi chú: Maven wrapper từng lỗi (AUDIT 2026-10-14); xác nhận `./mvnw` chạy được trước.
