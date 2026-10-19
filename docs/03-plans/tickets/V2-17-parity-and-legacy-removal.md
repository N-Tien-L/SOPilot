---
id: V2-17
title: "Kiểm tra parity, gỡ 8 service cũ, cập nhật tài liệu hướng dẫn"
type: chore
status: todo
created: 2026-10-17
updated: 2026-10-19
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
- [ ] Gỡ `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`, `api-gateway`, `ai-qa-service`, `ingestion-service` và compose cũ — chỉ đúng đường dẫn cụ thể, không dùng xóa đệ quy bằng wildcard (AGENTS.md).
- [ ] Cập nhật `AGENTS.md` (bảng topology, quy tắc migration, script), `CLAUDE.md` (mục drift: xóa mục đã hết hiệu lực), `GEMINI.md`, `README.md`.
- [ ] Cập nhật `.agent/context/` (service-boundaries, database, authorization, events, storage, architecture/frontend) và `scripts/*.ps1` cho cấu trúc mới.
- [ ] `./scripts/pre-commit-check.ps1` PASS.
- [ ] Giữ mốc git (tag/nhánh) của M1 trước khi gỡ.

## 3. Hướng dẫn
Làm theo thứ tự: tạo tag → cập nhật script/doc → gỡ service → chạy pre-commit. Cần owner yêu cầu rõ ràng trước khi commit.

## 4. Kiểm thử
`./scripts/pre-commit-check.ps1`, `./scripts/check-services.ps1` (cập nhật cho 2 service).
