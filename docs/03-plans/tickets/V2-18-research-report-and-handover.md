---
id: V2-18
title: "Báo cáo nghiên cứu và gói bàn giao"
type: docs
status: todo
created: 2026-10-17
updated: 2026-10-24
author: "Owner"
scope: docs
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-04, V2-07, V2-14, V2-17, V2-27, V2-28]
blocks: []
branch: "docs/docs-research-handover"
assignee: owner
---

# TICKET V2-18: Bàn giao nghiên cứu

## 1. Bối cảnh & Mục tiêu
Đóng gói để người chấm chạy lại được kết quả.

## 2. Tiêu chí Hoàn thành
- [ ] Báo cáo trả lời RQ1–RQ3 (và RQ4, RQ5 nếu có) bằng số liệu từ `eval/results/`, kèm giới hạn: quy mô dữ liệu, quy trình người duyệt câu hỏi, phần cứng, những gì chưa đo.
- [ ] Mục tiêu NFR (recall@5 ≥ 0.80...) được chốt lại theo baseline và nêu đạt/không đạt trung thực.
- [ ] Hướng dẫn tái lập từng bảng số liệu bằng đúng lệnh, ghi commit và hash cấu hình.
- [ ] Danh sách hạn chế và hướng phát triển (rerank, deploy B1/B3, group, ...).
- [ ] Gói bàn giao: mã nguồn, README, dataset hoặc script tải, kết quả, báo cáo trong `docs/04-reports/`; không chứa secret hay `.env`.
- [ ] PLAN-V2: 32 ticket còn lại `done`, báo cáo V2-18 được review trước khi chuyển `done`; sau nghiệm thu PLAN là 33/33, bộ đếm khớp (sửa 2026-10-21: thêm `V2-28`). Báo cáo nêu kết quả bộ kiểm SOP tiếng Việt của `V2-28` như phần bổ sung, không như kết quả RQ.

## 3. Hướng dẫn
- **File:** `docs/04-reports/AUDIT-v2-final-<ngày>.md`, `docs/04-reports/RESEARCH-REPORT-v2.md` (CREATE). Tác giả ghi "Owner".

## 4. Kiểm thử
Người khác (hoặc môi trường sạch) chạy lại lệnh trong hướng dẫn và nhận số liệu khớp.
