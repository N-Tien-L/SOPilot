---
id: V2-20
title: "ai-service: chọn thư viện PDF, biểu diễn có cấu trúc và Markdown chuẩn có offset (PDF/MD)"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-21
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
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 2 và 3, PRD-V2 FR-08. Code cũ có 3 bộ trích xuất và làm mất số trang, cấu trúc heading, số thứ tự, vị trí bảng. Thay bằng một module duy nhất xuất cây tài liệu có kiểu (heading, đoạn, danh sách, bảng) kèm số trang và vị trí ký tự.

Owner chốt 2026-10-21 ([AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md), TECH-V2-ai-service §5.2, §11 Q7–Q8): PDF chuyển thẳng từ cấu trúc của **một** thư viện sang `StructuredDocument`; Markdown qua parser vào cùng biểu diễn; ai-service tự render **Markdown chuẩn** sau làm sạch và ghi offset trên đó. Không trích plain text rồi dựng lại, không chuỗi fallback, không OCR, không LLM viết lại nội dung. TXT bỏ khỏi MVP.

## 2. Tiêu chí Hoàn thành
- [ ] Dựng khung `services/ai-service` (TECH-V2-ai-service §1.1, "Thứ tự dựng khung"): `pyproject.toml` (uv, Python ≥ 3.11, extra `pdf` cho thư viện ADR-008), layout `src/sopilot_ai/` với `docproc/` thuần (không import DB/web), `tests/unit`, ruff. Thêm scope `ai` vào `scripts/validate-build.ps1` và `scripts/check-conventions.ps1`, scope `ai-service` vào `scripts/run-tests.ps1`, và cập nhật bảng scope trong `AGENTS.md` trong cùng thay đổi.
- [ ] Spike chọn thư viện, timebox 2 ngày, so Docling và PyMuPDF 2.x trên tập con V2-19 (hoặc fixture synthetic theo AUDIT-markdown-normalization §6.3) theo tiêu chí TECH-V2-ai-service §11 Q8: ràng buộc cứng (offline trên CPU, OCR tắt được, số trang cho mọi phần tử, tiếng Việt NFC, giấy phép; AGPL cần owner xác nhận) rồi so heading/bảng theo họ, thời gian và RAM đỉnh mỗi trang trên máy owner, công bảo trì. Ghi số đo thật, phiên bản ghim và lựa chọn vào ADR-008; phần chưa đo ghi là chưa đo. Runtime chỉ phụ thuộc một thư viện, cô lập trong `extract/pdf.py`.
- [ ] Chỉ nhận PDF/MD; từ chối DOCX/TXT trước khi parse (`UNSUPPORTED_TYPE`). Không triển khai extractor hoặc chuyển đổi DOCX/TXT.
- [ ] PDF có lớp chữ: giữ số trang; thứ tự đọc đúng với trang nhiều cột; bảng giữ cấu trúc hàng/cột, đúng vị trí trong thân; ô gộp không bị lặp. Bảng kéo qua nhiều trang là một phần tử có `page_end > page` và `row_pages` cho từng hàng (TECH-V2-ai-service §5.2).
- [ ] MD: parser CommonMark + GFM; giữ heading, list, bảng; bỏ frontmatter (lưu làm metadata) và shortcode Hugo; HTML nhúng giữ dạng văn bản; không phải UTF-8 → `INVALID_ENCODING`.
- [ ] PDF không có lớp chữ → `FAILED NO_TEXT_LAYER` với câu VI/EN cố định; PDF mã hóa → `ENCRYPTED_PDF`; file hỏng → `CORRUPT_FILE`. OCR tắt: test trang chỉ có ảnh cho 0 ký tự và không gọi engine OCR nào.
- [ ] Renderer Markdown chuẩn (TECH-V2-ai-service §5.2) có `normalizer_version`: heading `#` theo cấp, list giữ số thứ tự nguồn, bảng GFM có đúng số hàng/cột của phần tử nguồn, ô gộp ghi một lần. Render hai lần cùng đầu vào cho cùng chuỗi. Renderer đặt `row_spans` cho từng hàng của mọi bảng.
- [ ] Source mapping: với mọi phần tử nội dung của mọi fixture và mọi file corpus đã có, `markdown[char_start:char_end]` bằng đoạn render của phần tử (bất biến, kiểm bằng property test); `page` thuộc `1..page_count` với PDF, `None` với MD; `page_index` liên tiếp, không chồng nhau, bảng nhiều trang chia tại ranh giới hàng; `row_spans` tăng dần, nằm trong offset của bảng và mỗi đoạn chứa đúng các ô của hàng tương ứng; offset UTF-16 đúng với chuỗi có emoji/ký tự ngoài BMP.
- [ ] Unicode: đầu ra NFC; fixture tiếng Việt (có đủ dấu thanh, `đ`, chữ hoa có dấu) và tiếng Anh ra đúng chuỗi kỳ vọng ở cả PDF và MD; fixture có ký tự lỗi sinh cảnh báo `UNMAPPED_GLYPHS` (V2-21).
- [ ] Fixture heading/bảng tự tạo (PDF xuất từ Word tiếng Việt: heading đánh số 2 cấp, list `a)`, bảng 4 cột có ô gộp và bảng kéo qua 2 trang): heading đúng thứ tự và cấp, bảng đúng vị trí trong thân và đúng số hàng/cột. Không đặt yêu cầu khớp tuyệt đối trên corpus thật.
- [ ] Báo cáo chỉ số trên corpus V2-19 theo họ tài liệu (heading precision/recall, bảng, thời gian/RAM mỗi trang); ngưỡng do owner chốt sau khi xem baseline, không đặt trước.

## 3. Hướng dẫn
- **File:** package Python thuần, không phụ thuộc DB/web, trong `services/ai-service` theo cấu trúc của TECH-V2 (V2-03). V2-09 import lại.
- Tham khảo lỗi cũ: `services/ingestion-service/src/services/extractors/`, `preview_extractor.py`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | PDF nhiều trang, bảng giữa thân, ô gộp, bảng nhiều trang (`page_end`, `row_pages`, `row_spans`); MD (frontmatter, GFM, HTML nhúng); renderer và bất biến offset; Unicode VI/EN; từ chối DOCX/TXT, PDF scan, mã hóa, hỏng | `uv run pytest tests/unit` |
| Spike | Hai thư viện trên cùng tập con, cùng máy; kết quả vào ADR-008 | script trong `eval/` |
| Eval | Script chấm V2-19 trên toàn corpus, lưu kết quả vào báo cáo | theo V2-19 |
