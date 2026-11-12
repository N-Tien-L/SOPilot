---
id: V2-16
title: "Dữ liệu demo và docker compose chạy bằng một lệnh"
type: feat
status: review
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: platform
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12, V2-21, V2-24, V2-36]
blocks: [V2-17]
branch: "feat/platform-demo-compose"
assignee: pair
---

# TICKET V2-16: Demo data và chạy một lệnh

## 1. Bối cảnh & Mục tiêu
FR-21 và NFR tái lập: `docker compose up` dựng hệ thống cục bộ; bàn giao nghiên cứu chạy được trên máy người chấm.

## 2. Tiêu chí Hoàn thành
- [x] Script tạo workspace mẫu với bộ SOP công khai (dùng corpus V2-06), idempotent; số tài liệu và dung lượng nằm trong hạn mức mặc định 50 tài liệu/200 MB (PRD-V2 FR-09, owner chốt 2026-10-21), hoặc README ghi rõ biến hạn mức cần đặt; có ít nhất hai phòng ban, thành viên mẫu và một tài liệu giới hạn phòng ban để demo UC-10.
- [ ] Một lệnh dựng: Postgres, object storage, Flyway, core-api, ai-service, frontend (và embedding local nếu bật).
- [x] README ở gốc: yêu cầu máy (RAM/CPU), các bước, cấu hình `.env` từ `.env.example`, cách bật dev login không cần Google, cách chạy eval.
- [x] Hướng dẫn dùng LLM: API (Gemini/Groq) hoặc local, và hành vi khi thiếu key (báo lỗi rõ ràng, không treo).
- [ ] Thử trên môi trường sạch (máy hoặc clone mới); ghi thời gian từ clone đến hỏi đáp được.
- [ ] Sửa 2026-10-21 (audit theo loại query, P1-7): đo TTFT đầu-cuối (P50/P95, mục tiêu PRD-V2 NFR: P95 < 3 s) trên stack local với khoảng 30 câu, **có và không có** bước viết lại câu hỏi (hội thoại mới và hội thoại có lịch sử); báo cáo ghi phần cứng, provider thật, số lần chạy và độ lệch. Chưa đạt thì ghi lại, không sửa mục tiêu trong ticket này.

## 2a. Bằng chứng và mục còn mở (2026-11-13)
- Compose một lệnh: `docker-compose.v2.yml` thêm `core-api`, `ai-service`, `ai-worker` (healthcheck tắt vì worker không có HTTP), `web`; Dockerfile `services/core-api/Dockerfile`, `services/ai-service/Dockerfile` (extra `local` + `pdf`). Biến bắt buộc dùng `${VAR:?}` nên compose dừng và nêu tên biến thiếu. Stack đã chạy trên máy owner (Postgres, MinIO, core-api, ai-service healthy).
- Seed `scripts/seed-demo.ps1`: workspace `SOPilot Demo Workspace`, phòng "Kỹ thuật" và "Nhân sự", hai thành viên được mời và **chấp nhận qua dev login** (`engineer@sopilot.local` là publisher "Kỹ thuật" theo ADR-009, `hr@sopilot.local`), 2 SOP toàn workspace + 1 SOP giới hạn "Kỹ thuật" từ `eval/datasets/sop-pilot` và `smoke` (tệp có trong git), 3 tài liệu, dưới hạn mức 50/200 MB. Chạy 2026-11-13 trên stack local: lần đầu tạo đủ, lần hai `0 uploaded, 3 already present`, exit 0; 3 tài liệu `READY`; engineer thấy 3 tài liệu, HR thấy 2 (UC-10). Sửa lỗi mã hóa của Windows PowerShell 5.1 (thân request ISO-8859-1 làm tên phòng thành `K? thu?t`); phòng tạo sai ở lần chạy trước đã đổi tên lại qua `PATCH /api/v1/departments/{id}`.
- README gốc: yêu cầu máy, cấu hình biến môi trường theo file mẫu ở gốc repo, dev login, LLM (Modal theo ADR-006 §4.4, thay cho Gemini/Groq của bản ticket gốc) và hành vi thiếu key, eval, đo TTFT. Yêu cầu "4 CPU, 8 GB RAM" là ước lượng, chưa đo trên máy sạch.
- Script đo TTFT `scripts/measure-ttft.ps1`: 15 câu hội thoại mới + 15 câu nối tiếp (có viết lại), TTFT phía client tới `delta`/`refusal` đầu tiên, P50/P95, độ lệch, phần cứng, ghi `eval/results/ttft/`. **Chưa chạy** (cần endpoint Modal thật đã làm nóng).
- **Còn mở (owner):** (1) thử trên máy sạch hoặc clone mới, ghi thời gian từ clone đến câu trả lời đầu tiên; (2) chạy `scripts/measure-ttft.ps1` với provider thật, ghi phần cứng, số lần chạy, độ lệch; chưa đạt P95 < 3 s thì ghi lại, không đổi mục tiêu; (3) hỏi một câu qua API trên stack compose và nhận câu trả lời có trích dẫn (mục 4); (4) image `web` vẫn nối gateway V1 tới `V2-15`, nên tiêu chí "một lệnh dựng cả frontend" chưa đạt về chức năng.

## 3. Hướng dẫn
- **File:** `docker-compose.v2.yml` (hoàn thiện từ V2-08), `scripts/seed-demo.ps1`, `README.md`.

## 4. Kiểm thử
`docker compose -f docker-compose.v2.yml up -d` rồi hỏi một câu qua UI hoặc API và nhận câu trả lời có trích dẫn. Ghi lệnh và kết quả.
