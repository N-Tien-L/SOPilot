---
id: V2-21
title: "ai-service: tách phần khung khỏi nội dung và trích metadata SOP"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-16, V2-25]
branch: "feat/ai-qa-boilerplate-metadata"
assignee: pair
---

# TICKET V2-21: Tách khung, giữ ruột

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 4 và 8, PRD-V2 FR-08. Phần khung (header/footer lặp, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt, bảng sửa đổi) đang bị embed như nội dung. Bỏ chúng khỏi index nhưng giữ thông tin hữu ích làm metadata.

## 2. Tiêu chí Hoàn thành
- [ ] Phát hiện header/footer lặp qua các trang PDF và header/footer của DOCX; loại khỏi nội dung.
- [ ] Nhận diện khối quốc hiệu/tiêu ngữ, số/ký hiệu, nơi nhận, khối chữ ký, bảng Soạn thảo/Soát xét/Phê duyệt, bảng theo dõi sửa đổi; loại khỏi nội dung được chunk.
- [ ] Trích metadata khi có: mã số, lần ban hành, ngày ban hành/hiệu lực, người phê duyệt; lưu theo version tài liệu.
- [ ] Không xóa nội dung thật: trên corpus V2-19, tỷ lệ khung lọt vào nội dung và tỷ lệ nội dung bị xóa nhầm đều được báo cáo; owner chốt ngưỡng.

## 3. Hướng dẫn
- Bước xử lý trên cấu trúc của V2-20, trước bước chunk của V2-22.
- Schema metadata theo TECH-V2; nếu thêm cột thì migration trong `infrastructure/db/migrations/` và cập nhật `.agent/context/database/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Header/footer lặp; khối quốc hiệu; bảng phê duyệt; trích mã số và lần ban hành | `uv run pytest tests/unit` |
| Eval | Chấm trên corpus V2-19 | theo V2-19 |
