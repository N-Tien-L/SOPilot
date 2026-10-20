---
id: V2-08
title: "Khung Flyway và docker compose (Postgres/pgvector, object storage)"
type: chore
status: todo
created: 2026-10-17
updated: 2026-10-17
scope: infra
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-09, V2-11]
branch: "chore/infra-v2-compose"
assignee: pair
---

# TICKET V2-08: Hạ tầng nền V2

## 1. Bối cảnh & Mục tiêu
Database mới (ADR-004 §4.4), migration bằng Flyway trong `infrastructure/db/migrations/`, chạy local và CI. Không động vào volume cũ.

## 2. Tiêu chí Hoàn thành
- [ ] `docker-compose.v2.yml` (file riêng, không sửa compose cũ): Postgres 16 + pgvector (ghim phiên bản), object storage S3 ghim phiên bản (MinIO bản ghim hoặc SeaweedFS, theo V2-01), container Flyway chạy một lần.
- [ ] Hai role DB: role migration (owner bảng) và role ứng dụng (không owner, để RLS có hiệu lực).
- [ ] Migration `V001` tạo schema và extension; một migration mẫu chạy sạch trên DB trống.
- [ ] Chỉ publish port cần cho local; secret lấy từ `.env`, `.env.example` có giá trị giả.
- [ ] Không chạy `docker compose down -v` hay reset volume.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml`, `infrastructure/db/migrations/V001__*.sql`, `infrastructure/db/README.md`, `.env.example` (CREATE).

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi truy vấn `flyway_schema_history` và `\du`. Ghi lệnh và kết quả.
