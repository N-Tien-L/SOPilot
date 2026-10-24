---
id: V2-08
title: "Khung Flyway và docker compose (Postgres/pgvector, object storage)"
type: chore
status: done
created: 2026-10-17
updated: 2026-10-25
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
- [x] Ba role DB theo TECH-V2-core-api §4.1: `sopilot_migrator` (owner schema `core` và `rag`), `sopilot_core_app` (chỉ `core`), `sopilot_ai_app` (chỉ `rag`); hai role ứng dụng không owner bảng, `NOBYPASSRLS`, để RLS có hiệu lực. Test: `sopilot_ai_app` không đọc được bảng `core` và ngược lại.
- [x] Migration `V001` tạo schema `core`, `rag`, extension `vector` (pgvector ≥ 0.8), hàm `core.current_workspace()` / `rag.current_workspace()` và grant mặc định; một migration mẫu chạy sạch trên DB trống. Bảng nghiệp vụ không thuộc ticket này: bảng `rag.*` do `V2-09` viết (và `V2-13`, `V2-25` cho bảng của mình), bảng `core.*` do `V2-11`, `V2-12`, `V2-23`, `V2-24`.
- [x] Chỉ publish port cần cho local; secret lấy từ `.env`, `.env.example` có giá trị giả.
- [x] Tách hẳn khỏi stack cũ (ADR-004 §4.5). `docker-compose.yml` cũ không khai báo `name:`, nên project mặc định là `sopilot` và volume là `sopilot_postgres_data`, container là `sopilot-postgres`. `docker-compose.v2.yml` phải đặt `name: sopilot-v2`; container (nếu đặt tên) có tiền tố `sopilot-v2-`; volume dùng khóa riêng (ví dụ `v2_postgres_data`, `v2_object_data`). Kiểm tra: `docker volume ls` sau khi `up` không có volume cũ nào bị mount vào container V2. *(Cấu hình: `name: sopilot-v2`, container `sopilot-v2-*`, volume thành `sopilot-v2_postgres_data`/`sopilot-v2_minio_data`; lần kiểm 2026-10-20 dùng tmpfs nên chưa chạy `docker volume ls` với `.env` thật.)*
- [x] Port host không trùng stack cũ (cũ đang dùng `3000`, `3001`). Ghi bảng port V2 trong `infrastructure/db/README.md`. Quy ước dev: mỗi lúc chỉ bật một stack; bật stack cũ chỉ khi cần đối chiếu hoặc port code. *(Postgres `55432`, MinIO `59000`/`59001`, chỉ bind `127.0.0.1`.)*
- [x] Không chạy `docker compose down -v` hay reset volume.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml`, `infrastructure/db/migrations/V001__*.sql`, `infrastructure/db/README.md`, `.env.example` (CREATE).

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi truy vấn `flyway_schema_history` và `\du`; `docker volume ls` để xác nhận volume V2 tách khỏi volume `sopilot_*` cũ. Ghi lệnh và kết quả.

### Kết quả 2026-10-20
Chạy trên project tạm `sopilot-v2-verify` với file env sinh mật khẩu ngẫu nhiên và override dữ liệu vào tmpfs, nên không tạo volume và không đụng `.env` thật:
- `up -d`: `postgres`, `minio` healthy; `flyway-core`, `flyway-rag`, `minio-init` thoát mã 0.
- Role: `sopilot_migrator`, `sopilot_core_app`, `sopilot_ai_app` đều `rolsuper = f`, `rolbypassrls = f`. Schema `core`, `rag` do `sopilot_migrator` sở hữu; extension `vector` 0.8.0.
- `core.flyway_schema_history` và `rag.flyway_schema_history` đều có `001` `success = t`.
- Probe RLS (trong một transaction, sau đó rollback): `sopilot_core_app` chỉ thấy dòng của workspace đang đặt; biến chưa đặt → 0 dòng; ghi dòng của workspace khác → `new row violates row-level security policy`; đọc `rag` → `permission denied for schema rag`; tạo bảng trong `core` → `permission denied`; `sopilot_ai_app` đọc `core` → `permission denied for schema core`.
- MinIO: bucket `sopilot-v2-documents` không cho truy cập ẩn danh; user `sopilot-core` (đọc/ghi) và `sopilot-ai` (chỉ đọc).
- Dừng bằng `down` (không `-v`); không còn container hay volume của project tạm.

Ghi chú: `.env.example` đã có sẵn nên khối biến V2 được thêm vào cuối file thay vì tạo file mới. Biến V2 có tiền tố `V2_`/`SOPILOT_S3_` để không đụng biến của stack cũ. Chưa chạy stack bằng `.env` thật của owner.

### Nghiệm thu 2026-10-25
Owner chốt phạm vi trong chat ("ok chốt"). Nghiệm thu hạ tầng local: cấu hình volume/network V2 tách V1, port loopback; Flyway, RLS, S3 và init lặp lại kiểm trên project tmpfs. Không đọc `.env`, không mount/reset volume hiện có hoặc áp migration lên DB của owner. Xem [biên bản nghiệm thu](../../04-reports/AUDIT-v2-05-v2-08-acceptance-2026-10-25.md).
