---
id: V2-16
title: "Dữ liệu demo và docker compose chạy bằng một lệnh"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: platform
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12, V2-21, V2-24]
blocks: [V2-17]
branch: "feat/platform-demo-compose"
assignee: pair
---

# TICKET V2-16: Demo data và chạy một lệnh

## 1. Bối cảnh & Mục tiêu
FR-21 và NFR tái lập: `docker compose up` dựng hệ thống cục bộ; bàn giao nghiên cứu chạy được trên máy người chấm.

## 2. Tiêu chí Hoàn thành
- [ ] Script tạo workspace mẫu với bộ SOP công khai (dùng corpus V2-06), idempotent; có ít nhất hai phòng ban, thành viên mẫu và một tài liệu giới hạn phòng ban để demo UC-10.
- [ ] Một lệnh dựng: Postgres, object storage, Flyway, core-api, ai-service, frontend (và embedding local nếu bật).
- [ ] README ở gốc: yêu cầu máy (RAM/CPU), các bước, cấu hình `.env` từ `.env.example`, cách bật dev login không cần Google, cách chạy eval.
- [ ] Hướng dẫn dùng LLM: API (Gemini/Groq) hoặc local, và hành vi khi thiếu key (báo lỗi rõ ràng, không treo).
- [ ] Thử trên môi trường sạch (máy hoặc clone mới); ghi thời gian từ clone đến hỏi đáp được.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml` (hoàn thiện từ V2-08), `scripts/seed-demo.ps1`, `README.md`.

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi hỏi một câu qua UI hoặc API và nhận câu trả lời có trích dẫn. Ghi lệnh và kết quả.
