---
id: V2-08
title: "Khung Flyway và docker compose (Postgres/pgvector, object storage)"
type: chore
status: review
created: 2026-10-17
updated: 2026-10-20
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
- [x] `docker-compose.v2.yml` (file riêng, không sửa compose cũ): Postgres 16 + pgvector (ghim phiên bản), object storage S3 ghim phiên bản (MinIO bản ghim hoặc SeaweedFS, theo V2-01), container Flyway chạy một lần.
- [x] Hai role DB: role migration (owner bảng) và role ứng dụng (không owner, để RLS có hiệu lực).
- [x] Migration `V001` tạo schema và extension; một migration mẫu chạy sạch trên DB trống.
- [x] Chỉ publish port cần cho local; secret lấy từ `.env`, `.env.example` có giá trị giả.
- [x] Không chạy `docker compose down -v` hay reset volume.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml`, `infrastructure/db/migrations/V001__*.sql`, `infrastructure/db/README.md`, `.env.example` (CREATE).

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi truy vấn `flyway_schema_history` và `\du`. Ghi lệnh và kết quả.

### Kết quả 2026-10-20
Chạy trên project tạm `sopilot-v2-verify` với file env sinh mật khẩu ngẫu nhiên và override dữ liệu vào tmpfs, nên không tạo volume và không đụng `.env` thật:
- `up -d`: `postgres`, `minio` healthy; `flyway-core`, `flyway-rag`, `minio-init` thoát mã 0.
- Role: `sopilot_migrator`, `sopilot_core_app`, `sopilot_ai_app` đều `rolsuper = f`, `rolbypassrls = f`. Schema `core`, `rag` do `sopilot_migrator` sở hữu; extension `vector` 0.8.0.
- `core.flyway_schema_history` và `rag.flyway_schema_history` đều có `001` `success = t`.
- Probe RLS (trong một transaction, sau đó rollback): `sopilot_core_app` chỉ thấy dòng của workspace đang đặt; biến chưa đặt → 0 dòng; ghi dòng của workspace khác → `new row violates row-level security policy`; đọc `rag` → `permission denied for schema rag`; tạo bảng trong `core` → `permission denied`; `sopilot_ai_app` đọc `core` → `permission denied for schema core`.
- MinIO: bucket `sopilot-v2-documents` không cho truy cập ẩn danh; user `sopilot-core` (đọc/ghi) và `sopilot-ai` (chỉ đọc).
- Dừng bằng `down` (không `-v`); không còn container hay volume của project tạm.

Ghi chú: `.env.example` đã có sẵn nên khối biến V2 được thêm vào cuối file thay vì tạo file mới. Biến V2 có tiền tố `V2_`/`SOPILOT_S3_` để không đụng biến của stack cũ. Chưa chạy stack bằng `.env` thật của owner.
