---
id: M1-04
title: "API Gateway: Định tuyến Roster & Google Auth Endpoints"
type: feat
status: review
created: 2026-09-27
updated: 2026-10-20
scope: gateway
priority: P1
size: S
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: [M1-02, M1-03]
blocks: [M1-05]
branch: "feat/gateway-roster-routes"
assignee: pair
---

> **Ghi chú 2026-10-20 (V2-04):** giữ nguyên trạng thái để lưu lịch sử; không làm tiếp trên kiến trúc cũ. Phần còn giá trị được port sang V2-11 (core-api) và V2-15 (frontend). Gateway bị bỏ trong V2 (ADR-004): route được thay bằng Next.js rewrites.

## Context
API Gateway (NestJS) là điểm tiếp nhận duy nhất từ Client. Cần mở các tuyến đường công khai cho Google Auth Verify và các tuyến đường bảo vệ (Admin only) cho Roster Management, hỗ trợ multipart file streaming upload tới `user-service`.

## Acceptance Criteria
- [x] Route `POST /api/v1/auth/google/verify` là `@Public()` và forward chính xác sang `auth-service`.
- [x] Route `POST /api/v1/users/roster/import` yêu cầu vai trò `ADMIN`, hỗ trợ multipart/form-data streaming tới `user-service`.
- [x] Route `GET /api/v1/users/roster/template` cho phép `ADMIN`/`MANAGER` tải file nhị phân template từ `user-service`.
- [x] Routes `GET /api/v1/users/roster` và `PUT/DELETE /api/v1/users/roster/:id` được phân quyền `ADMIN` và forward sang `user-service`.

## Implementation Guide
1. **Bổ sung routes trong ProxyController**
   - **File:** `services/api-gateway/src/proxy/proxy.controller.ts`
   - **Action:** MODIFY
   - **Details:** Thêm các handler method cho roster và auth/google/verify.

2. **Kiểm tra cấu hình multipart upload & body parser**
   - **File:** `services/api-gateway/src/main.ts`
   - **Action:** VERIFY & MODIFY
   - **Details:** Đảm bảo multipart/form-data không bị nuốt (swallowed) bởi json body-parser khi proxy sang downstream.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Integration | Proxy forward `POST /api/v1/auth/google/verify` nhận response từ auth-service | Jest / Supertest |
| Integration | Proxy forward `POST /api/v1/users/roster/import` kèm file Excel tới user-service | Jest / Supertest |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `services/api-gateway/src/proxy/proxy.controller.ts` | MODIFY | +45 |
