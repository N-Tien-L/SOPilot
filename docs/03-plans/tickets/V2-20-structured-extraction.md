---
id: V2-20
title: "ai-service: bộ trích xuất duy nhất ra văn bản có cấu trúc (DOCX/PDF/MD/TXT)"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-19]
blocks: [V2-09, V2-21, V2-22]
branch: "feat/ai-qa-structured-extraction"
assignee: pair
---

# TICKET V2-20: Trích xuất có cấu trúc

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 2 và 3, PRD-V2 FR-08. Code cũ có 3 bộ trích xuất và làm mất số trang, heading style, số thứ tự tự động, vị trí bảng. Thay bằng một module duy nhất xuất cây tài liệu có kiểu (heading, đoạn, danh sách, bảng) kèm số trang và vị trí ký tự.

## 2. Tiêu chí Hoàn thành
- [ ] Chọn thư viện (ví dụ Docling, hoặc PyMuPDF4LLM cho PDF + Mammoth/python-docx cho DOCX) dựa trên số đo trên corpus V2-19, có chạy được trên CPU; ghi quyết định thành ADR-008.
- [ ] DOCX: đọc theo thứ tự body (đoạn và bảng xen kẽ đúng chỗ), có số thứ tự tự động của Word, heading theo style; ô gộp không bị lặp.
- [ ] PDF có lớp chữ: giữ số trang; thứ tự đọc đúng với trang nhiều cột; bảng giữ cấu trúc hàng/cột.
- [ ] MD/TXT: giữ heading Markdown, bỏ frontmatter (lưu frontmatter làm metadata).
- [ ] PDF không có lớp chữ và file ảnh bị từ chối với lý do rõ; không có OCR.
- [ ] Đầu ra là cấu trúc có kiểu, xuất được sang Markdown; mỗi phần tử có `page` và vị trí ký tự.
- [ ] Đạt ngưỡng trên corpus V2-19 do owner chốt khi xem baseline (đề xuất: heading recall ≥ 0,9 trên DOCX có style).

## 3. Hướng dẫn
- **File:** package Python thuần, không phụ thuộc DB/web, trong `services/ai-service` theo cấu trúc của TECH-V2 (V2-03). V2-09 import lại.
- Tham khảo lỗi cũ: `services/ingestion-service/src/services/extractors/`, `preview_extractor.py`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | DOCX có bảng giữa văn bản, numbering tự động, ô gộp; PDF nhiều trang; từ chối PDF scan | `uv run pytest tests/unit` |
| Eval | Script chấm V2-19 trên toàn corpus, lưu kết quả vào báo cáo | theo V2-19 |
