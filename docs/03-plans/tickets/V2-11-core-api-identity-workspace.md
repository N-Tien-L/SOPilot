---
id: V2-11
title: "core-api: khung service, Google identity, JIT và workspace cá nhân"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-05
author: "Owner"
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
- [x] Xác minh Google ID token (RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`) **và kiểm tra `nonce`** (A9).
- [x] User JIT theo `(issuer, sub)`; workspace cá nhân tự tạo, idempotent (FR-02).
- [x] JWT ban đầu ≤ 15 phút gắn workspace cá nhân và role; một service ghi `users`/membership ban đầu. CRUD/chuyển workspace và refresh chuyển sang V2-29.
- [x] Dev login chỉ ở profile `local`/`test`.
- [x] Lỗi trả client không chứa `e.getMessage()` nội bộ (A8); không log token/secret.
- [x] Chỉ một service ghi `users`.
- [x] Token có chỗ cho claim `wdept` (giá trị điền ở V2-23); refresh và kiểm membership thuộc V2-29.

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

## 5. Bằng chứng triển khai (2026-11-04, nghiệm thu 2026-11-05)

Owner nghiệm thu 2026-11-05, chuyển `done`. Code ở commit `f25646b` trên nhánh `feat/user-core-api-identity`. Các mục "Chưa kiểm" dưới đây được chấp nhận còn mở: đăng nhập Google thật kiểm cùng V2-15, áp migration vào DB persistent làm khi chạy stack V2.

- **Code:** `services/core-api/` (Spring Boot 3.5.16, Java 21, wrapper Maven 3.9.12 chạy được); migration `infrastructure/db/migrations/core/V003__identity_and_personal_workspace.sql` (`users`, `external_identities`, `workspaces`, `memberships`, RLS, `core.create_personal_workspace`).
- **Port:** `GoogleIdTokenVerifier` từ V1 `GoogleTokenVerifierService` (V1 không sửa). Khác V1: kiểm `nonce` với cookie `sp_nonce` ký HMAC, lệch giờ 60 s, issuer chuẩn hóa, lỗi luôn `401 INVALID_GOOGLE_TOKEN` (V1 trả `e.getMessage()` cho client), log chỉ mã lý do.
- **Unit (`./mvnw test`, 41 test, xanh):** verifier với khóa RSA thật và JWKS cục bộ: sai chữ ký, HS256, `alg=none`, sai `iss`, sai `aud`, hết hạn (ngoài/ trong 60 s), `iat` tương lai, `email_verified=false`, nonce sai/thiếu/thiếu cookie, thiếu `sub`/`email`, chưa cấu hình client ID; nonce cookie (sửa nonce, kéo dài hạn, hết hạn, khóa khác); token workspace cá nhân (`wid`, `wrole`, `wdept` luôn có, TTL 900 s, chặn TTL > 15 phút, không có email/tên); HTTP: dev login `404` ở profile `prod`, `200` ở `test`; lỗi 500 không lộ message nội bộ.
- **Integration (`./mvnw verify`, 14 test, xanh, Testcontainers `pgvector/pgvector:0.8.0-pg16` + `01-roles.sh` thật + Flyway core đầy đủ, rag tới V002, kết nối bằng `sopilot_core_app`):** dev login lặp lại cùng user/workspace; 8 lần đăng nhập đầu đồng thời → 1 user, 1 identity, 1 workspace, 1 membership OWNER; cùng email khác issuer → 2 user; token xác minh qua `/.well-known/jwks.json`; không đặt tenant → 0 dòng; user chỉ thấy workspace của mình; không đọc/ghi workspace khác (RLS `WITH CHECK`); connection trong pool (pool = 1) không mang tenant sang transaction sau, kể cả sau rollback; `sopilot_core_app` không có quyền `rag`, không `CREATE` trong `core`, không tắt được RLS; `create_personal_workspace` là SECURITY DEFINER, không cấp cho `sopilot_ai_app`/PUBLIC, idempotent.
- **Script:** `./scripts/validate-build.ps1 -Scope core` và `./scripts/run-tests.ps1 -Scope core-api -Type all` xanh; `check-conventions.ps1 -Scope core` ánh xạ sang `services\core-api`.
- **Chưa kiểm:** đăng nhập Google thật trên trình duyệt (cần `GOOGLE_CLIENT_ID` và frontend V2-15); chạy V003 bằng container Flyway 10.20.1 của compose (test dùng Flyway 11 từ Spring Boot); chưa áp dụng vào DB persistent của owner.
- **Lệch so với TECH:** hàm `core.create_personal_workspace` nhận thêm `p_workspace_id` (UUIDv7 do app sinh, TECH §3); không đặt profile mặc định `local` (TECH §9 ghi mặc định `local`) để thiếu cấu hình thì dừng thay vì bật dev login; JWKS mới công bố khóa hiện hành, chưa có khóa trước đó (xoay khóa, cần khi có nhiều khóa). Owner đã duyệt cả ba (2026-11-05); TECH đã cập nhật §4.2, §5.1, §9, khóa trước đó trong JWKS chuyển sang V2-29.
- **Docs:** `.agent/context/authorization/v2-core-identity.md` (mới), `database/schema.md`, `database/tables/core.md`, `service-boundaries/responsibilities.md`, `service-boundaries/api-contracts.md`, `.agent/context/README.md`, `.env.example`, `services/core-api/README.md`.
