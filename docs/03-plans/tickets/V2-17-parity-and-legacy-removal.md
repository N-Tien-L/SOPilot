---
id: V2-17
title: "Kiểm tra parity, gỡ 8 service cũ, cập nhật tài liệu hướng dẫn"
type: chore
status: todo
created: 2026-10-17
updated: 2026-10-21
scope: platform
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-14, V2-15, V2-16, V2-26]
blocks: [V2-18]
branch: "chore/platform-remove-legacy"
assignee: pair
---

# TICKET V2-17: Parity và gỡ code cũ

## 1. Bối cảnh & Mục tiêu
Chỉ gỡ khi V2 đạt parity. Gỡ trong một commit riêng để lịch sử rõ ràng.

## 2. Tiêu chí Hoàn thành
- [ ] Bảng parity: mỗi UC-01 đến UC-11 và FR P0 đạt/không đạt kèm bằng chứng.
- [ ] Điều kiện an toàn trước khi gỡ (ghi kết quả từng mục):
  - Không còn tham chiếu từ phần V2 sang V1: tìm `auth-service|user-service|knowledge-service|metadata-service|feedback-service|api-gateway|ai-qa-service|ingestion-service|init-db|:3001` trong `services/core-api`, `services/ai-service`, `frontend/web`, `eval/`, `scripts/`, `.github/workflows/`, `docker-compose.v2.yml`; mọi kết quả còn lại đã được xử lý.
  - Mỗi phần port ở ADR-004 §4.5 có test trong service mới và đang xanh.
  - Eval harness (`eval/`) và CI (`.github/workflows/ci.yml`) chạy xanh chỉ với stack V2.
  - `docker compose -f docker-compose.v2.yml up` từ volume trống chạy hết UC demo (V2-16) mà không bật container V1 nào.
  - Tag `v1-final` (V2-15) tồn tại và đã đẩy lên remote; thêm tag/nhánh mốc M1 nếu khác commit.
- [ ] Gỡ `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`, `api-gateway`, `ai-qa-service`, `ingestion-service`, `docker-compose.yml`, `docker-compose.dev.yml` cũ và phần hạ tầng chỉ V1 dùng (`infrastructure/init-db/`, `infrastructure/combined_init.sql`, `infrastructure/onlyoffice/`, `infrastructure/seed*` nếu V2-16 không dùng lại) — chỉ đúng đường dẫn cụ thể, không dùng xóa đệ quy bằng wildcard (AGENTS.md). Đổi tên `docker-compose.v2.yml` thành `docker-compose.yml` trong cùng thay đổi nếu owner đồng ý.
- [ ] Không xóa Docker volume V1 (`sopilot_postgres_data`, `sopilot_minio_data`, ...) trong ticket này; chỉ ghi lệnh dọn để owner tự chạy khi muốn (AGENTS.md: không `down -v`, không prune).
- [ ] Cập nhật `AGENTS.md` (bảng topology, quy tắc migration, script), `CLAUDE.md` (mục drift: xóa mục đã hết hiệu lực), `GEMINI.md`, `README.md`.
- [ ] Cập nhật `.agent/context/` (service-boundaries, database, authorization, events, storage, architecture/frontend) và `scripts/*.ps1` cho cấu trúc mới.
- [ ] `./scripts/pre-commit-check.ps1` PASS.
- [ ] Giữ mốc git (tag/nhánh) của M1 trước khi gỡ.

## 3. Hướng dẫn
Làm theo thứ tự: kiểm điều kiện an toàn → xác nhận tag → cập nhật script/doc → gỡ service → chạy pre-commit. Xóa luôn ghi chú "V2 transition" ở đầu `AGENTS.md`. Cần owner yêu cầu rõ ràng trước khi commit.

## 4. Kiểm thử
`./scripts/pre-commit-check.ps1`, `./scripts/check-services.ps1` (cập nhật cho 2 service).
