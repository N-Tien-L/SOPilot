---
id: V2-19
title: "Corpus SOP thật (VI, EN; DOCX/PDF/MD) và bộ đo chất lượng trích xuất"
type: test
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-20]
branch: "test/tests-extraction-corpus"
assignee: pair
---

# TICKET V2-19: Corpus và bộ đo trích xuất SOP

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 1. Corpus eval của V2-06 chỉ có Markdown tiếng Anh nên không đo được trích xuất DOCX/PDF tiếng Việt. Cần một bộ nhỏ tài liệu thật, có nhãn cấu trúc, làm thước đo cho V2-20 đến V2-22.

Bộ này đo **trích xuất và cấu trúc**, không đo truy xuất; không trộn vào RQ1–RQ5.

## 2. Tiêu chí Hoàn thành
- [ ] 20–50 file, phủ ít nhất 5 họ: quy trình ISO 9001, văn bản hành chính (NĐ 30/2020, Chương/Điều/Khoản), SOP GMP/EPA, wiki/Markdown, tài liệu không theo chuẩn. Có cả DOCX và PDF có lớp chữ; thêm 2–3 PDF scan để kiểm tra từ chối.
- [ ] Mỗi file ghi nguồn, giấy phép và nhãn họ tài liệu trong `datasets/extraction/SOURCES.md`. File không được tái phân phối thì commit manifest + script tải, không commit file. Tài liệu nội bộ phải được xóa thông tin nhạy cảm trước khi đưa vào.
- [ ] Nhãn vàng cho mỗi file: danh sách heading theo thứ tự (kèm cấp), các bảng (vị trí, tiêu đề cột), các khối khung cần bỏ (header/footer, quốc hiệu, chữ ký, bảng phê duyệt, bảng sửa đổi), metadata kỳ vọng (mã số, lần ban hành, ngày hiệu lực) nếu có.
- [ ] Script chấm điểm một bộ trích xuất bất kỳ: độ khớp heading (precision/recall theo thứ tự), bảng đúng vị trí, tỷ lệ khung lọt vào nội dung, metadata đúng, thời gian xử lý.
- [ ] Owner duyệt nhãn của từng file.

## 3. Hướng dẫn
- **File:** `datasets/extraction/` (CREATE), script chấm trong `eval/` cạnh harness V2-05.
- Owner cung cấp hoặc chọn tài liệu; agent chuẩn bị định dạng nhãn và script.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Script chấm trên 2 file mẫu có nhãn tay | `uv run pytest` trong `eval/` |
