---
id: V2-21
title: "ai-service: tách phần khung, trích metadata SOP và cảnh báo trích xuất"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-21
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-09, V2-16, V2-25]
branch: "feat/ai-qa-boilerplate-metadata"
assignee: pair
---

# TICKET V2-21: Tách khung, giữ ruột

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 4 và 8, PRD-V2 FR-08. Phần khung (header/footer lặp, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt, bảng sửa đổi) đang bị embed như nội dung. Bỏ chúng khỏi index nhưng giữ thông tin hữu ích làm metadata.

## 2. Tiêu chí Hoàn thành
- [ ] Phát hiện header/footer lặp qua các trang PDF (DOCX hoãn sau MVP theo FR-06); loại khỏi nội dung.
- [ ] Nhận diện khối quốc hiệu/tiêu ngữ, số/ký hiệu, nơi nhận, khối chữ ký, bảng Soạn thảo/Soát xét/Phê duyệt, bảng theo dõi sửa đổi; loại khỏi nội dung được chunk.
- [ ] Trích metadata khi có: mã số, lần ban hành, ngày ban hành/hiệu lực, người phê duyệt; lưu theo version tài liệu.
- [ ] Khối đã loại lưu trong `extracted_documents.boilerplate` dạng `{kind, page, text}`; không xuất hiện trong Markdown chuẩn, chunk hay index (test trên fixture có header/footer lặp và bảng phê duyệt); màn xem FR-31 liệt kê được chúng.
- [ ] Cảnh báo theo TECH-V2-ai-service §5.3a (`PAGES_WITHOUT_TEXT`, `UNMAPPED_GLYPHS`, `NO_HEADINGS_DETECTED`, `BOILERPLATE_REMOVED`, `CONVERTER_WARNING` nếu thư viện có): mỗi mã có fixture sinh ra nó và fixture sạch không sinh ra nó; không có điểm tin cậy tổng hợp; cảnh báo không làm `FAILED`.
- [ ] Không xóa nội dung thật: trên corpus V2-19, tỷ lệ khung lọt vào nội dung và tỷ lệ nội dung bị xóa nhầm đều được báo cáo; owner chốt ngưỡng.

## 3. Hướng dẫn
- Bước xử lý trên cấu trúc của V2-20, trước bước chunk của V2-22.
- Schema metadata theo TECH-V2; nếu thêm cột thì migration trong `infrastructure/db/migrations/` và cập nhật `.agent/context/database/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Header/footer lặp; khối quốc hiệu; bảng phê duyệt; trích mã số và lần ban hành | `uv run pytest tests/unit` |
| Eval | Chấm trên corpus V2-19 | theo V2-19 |
