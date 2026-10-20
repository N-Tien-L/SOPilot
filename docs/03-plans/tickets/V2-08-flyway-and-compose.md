---
id: V2-08
title: "Khung Flyway và docker compose (Postgres/pgvector, object storage)"
type: chore
status: todo
created: 2026-10-17
updated: 2026-10-21
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
- [ ] Ba role DB theo TECH-V2-core-api §4.1: `sopilot_migrator` (owner schema `core` và `rag`), `sopilot_core_app` (chỉ `core`), `sopilot_ai_app` (chỉ `rag`); hai role ứng dụng không owner bảng, `NOBYPASSRLS`, để RLS có hiệu lực. Test: `sopilot_ai_app` không đọc được bảng `core` và ngược lại.
- [ ] Migration `V001` tạo schema `core`, `rag`, extension `vector` (pgvector ≥ 0.8), hàm `core.current_workspace()` / `rag.current_workspace()` và grant mặc định; một migration mẫu chạy sạch trên DB trống. Bảng nghiệp vụ không thuộc ticket này: bảng `rag.*` do `V2-09` viết (và `V2-13`, `V2-25` cho bảng của mình), bảng `core.*` do `V2-11`, `V2-12`, `V2-23`, `V2-24`.
- [ ] Chỉ publish port cần cho local; secret lấy từ `.env`, `.env.example` có giá trị giả.
- [ ] Tách hẳn khỏi stack cũ (ADR-004 §4.5). `docker-compose.yml` cũ không khai báo `name:`, nên project mặc định là `sopilot` và volume là `sopilot_postgres_data`, container là `sopilot-postgres`. `docker-compose.v2.yml` phải đặt `name: sopilot-v2`; container (nếu đặt tên) có tiền tố `sopilot-v2-`; volume dùng khóa riêng (ví dụ `v2_postgres_data`, `v2_object_data`). Kiểm tra: `docker volume ls` sau khi `up` không có volume cũ nào bị mount vào container V2.
- [ ] Port host không trùng stack cũ (cũ đang dùng `3000`, `3001`). Ghi bảng port V2 trong `infrastructure/db/README.md`. Quy ước dev: mỗi lúc chỉ bật một stack; bật stack cũ chỉ khi cần đối chiếu hoặc port code.
- [ ] Không chạy `docker compose down -v` hay reset volume.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml`, `infrastructure/db/migrations/V001__*.sql`, `infrastructure/db/README.md`, `.env.example` (CREATE).

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi truy vấn `flyway_schema_history` và `\du`; `docker volume ls` để xác nhận volume V2 tách khỏi volume `sopilot_*` cũ. Ghi lệnh và kết quả.
