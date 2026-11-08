---
id: V2-20
title: "ai-service: Docling (ADR-008), biểu diễn có cấu trúc và Markdown chuẩn có offset (PDF/MD)"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-03
author: "Owner"
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-19]
blocks: [V2-09, V2-21, V2-22]
branch: "feat/ai-structured-extraction"
assignee: pair
---

# TICKET V2-20: Trích xuất có cấu trúc

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 2 và 3, PRD-V2 FR-08. Code cũ có 3 bộ trích xuất và làm mất số trang, cấu trúc heading, số thứ tự, vị trí bảng. Thay bằng một module duy nhất xuất cây tài liệu có kiểu (heading, đoạn, danh sách, bảng) kèm số trang và vị trí ký tự.

Owner chốt 2026-10-21 ([AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md), TECH-V2-ai-service §5.2, §11 Q7–Q8): PDF chuyển thẳng từ cấu trúc của **Docling** (ADR-008, chốt cùng ngày) sang `StructuredDocument`; Markdown qua parser vào cùng biểu diễn; ai-service tự render **Markdown chuẩn** sau làm sạch và ghi offset trên đó. Không trích plain text rồi dựng lại, không chuỗi fallback, không OCR, không LLM viết lại nội dung. TXT bỏ khỏi MVP.

## 2. Tiêu chí Hoàn thành
- [x] Dựng khung `services/ai-service` (TECH-V2-ai-service §1.1, "Thứ tự dựng khung"): `pyproject.toml` (uv, Python ≥ 3.11, extra `pdf` cho Docling, ghim phiên bản theo ADR-008), layout `src/sopilot_ai/` với `docproc/` thuần (không import DB/web), `tests/unit`, ruff. Thêm scope `ai` vào `scripts/validate-build.ps1` và `scripts/check-conventions.ps1`, scope `ai-service` vào `scripts/run-tests.ps1`, và cập nhật bảng scope trong `AGENTS.md` trong cùng thay đổi. *Xong 2026-10-26: `pyproject.toml`, `src/sopilot_ai/docproc`, `tests/unit`, scope `ai`/`ai-service` trong scripts và AGENTS.md.*
- [x] Sửa 2026-10-21 (owner chốt [ADR-008](../../02-architecture/adr/ADR-008-pdf-extraction-docling.md): **Docling**, `approved`, chưa có số đo): ticket này **xác nhận Docling**, không còn so sánh hai thư viện. Trên tập con V2-19 (hoặc fixture synthetic gắn nhãn, theo AUDIT-markdown-normalization §6.3) kiểm các ràng buộc cứng của ADR-008 §5: (1) offline trên CPU, model nạp từ `SOPILOT_PDF_ARTIFACTS_PATH`; (2) OCR tắt hoàn toàn (trang ảnh cho 0 ký tự); (3) số trang thật cho mọi phần tử, và `furniture` hoặc đủ thông tin trang cho `V2-21`; (4) tiếng Việt NFC không mất dấu; (5) giấy phép MIT. Đo thêm: thư viện có trả **span ô gộp** (`cell_spans`: hàng, cột, rowspan, colspan) hay không, trên bảng có ô gộp của V2-19; thời gian và RAM đỉnh mỗi trang trên máy owner; heading/bảng theo họ tài liệu. Ghi số đo thật, phiên bản Docling ghim và hạn chế (nếu có) vào bảng §6 của ADR-008; phần chưa đo ghi là chưa đo. Timebox tối đa 2 ngày (trần cũ của PLAN); xong sớm thì chuyển sang adapter. *Xong một phần 2026-10-26: số đo ở ADR-008 §6. Chưa chứng minh chạy offline với model tải trước; thời gian vượt mục tiêu khởi đầu ở tài liệu nhiều bảng (báo owner).*
- [x] Sửa 2026-10-21: **ràng buộc cứng nào của Docling không đạt thì dừng và hỏi owner**: ADR-008 chuyển `draft`, không tự đổi sang PyMuPDF hay thêm chuỗi fallback (AGPL cần owner xác nhận, PLAN-V2 §4). Không có `cell_spans` hay thời gian/RAM vượt mục tiêu khởi đầu không tự làm ADR quay lại `draft`: ghi vào ADR-008 §5–§6 và báo owner. Runtime chỉ phụ thuộc Docling, cô lập trong `extract/pdf.py`.
- [x] Chỉ nhận PDF/MD; từ chối DOCX/TXT trước khi parse (`UNSUPPORTED_TYPE`). Không triển khai extractor hoặc chuyển đổi DOCX/TXT.
- [x] PDF có lớp chữ: giữ số trang; thứ tự đọc đúng với trang nhiều cột; bảng giữ cấu trúc hàng/cột, đúng vị trí trong thân; ô gộp không bị lặp trong Markdown chuẩn. Sửa 2026-10-21: adapter điền `DocElement.cell_spans` (TECH-V2-ai-service §5.2) cho mọi ô gộp để `V2-22` lặp giá trị xuống từng hàng; thư viện không trả span thì `cell_spans = None` và hạn chế được ghi vào ADR-008, không đoán giá trị. Test: fixture bảng 4 cột có ô "Trách nhiệm" gộp dọc qua 2 hàng cho `cell_spans` đúng. Bảng kéo qua nhiều trang là một phần tử có `page_end > page` và `row_pages` cho từng hàng (TECH-V2-ai-service §5.2).
- [x] MD: parser CommonMark + GFM; giữ heading, list, bảng; bỏ frontmatter (lưu làm metadata) và shortcode Hugo; HTML nhúng giữ dạng văn bản; không phải UTF-8 → `INVALID_ENCODING`.
- [x] PDF không có lớp chữ → `FAILED NO_TEXT_LAYER` với câu VI/EN cố định; PDF mã hóa → `ENCRYPTED_PDF`; file hỏng → `CORRUPT_FILE`. OCR tắt: test trang chỉ có ảnh cho 0 ký tự và không gọi engine OCR nào.
- [x] Renderer Markdown chuẩn (TECH-V2-ai-service §5.2) có `normalizer_version`: heading `#` theo cấp, list giữ số thứ tự nguồn, bảng GFM có đúng số hàng/cột của phần tử nguồn, ô gộp ghi một lần. Render hai lần cùng đầu vào cho cùng chuỗi. Renderer đặt `row_spans` cho từng hàng của mọi bảng.
- [x] Source mapping: với mọi phần tử nội dung của mọi fixture và mọi file corpus đã có, `markdown[char_start:char_end]` bằng đoạn render của phần tử (bất biến, kiểm bằng property test); `page` thuộc `1..page_count` với PDF, `None` với MD; `page_index` liên tiếp, không chồng nhau, bảng nhiều trang chia tại ranh giới hàng; `row_spans` tăng dần, nằm trong offset của bảng và mỗi đoạn chứa đúng các ô của hàng tương ứng; offset UTF-16 đúng với chuỗi có emoji/ký tự ngoài BMP.
- [x] Unicode: đầu ra NFC; fixture tiếng Việt (có đủ dấu thanh, `đ`, chữ hoa có dấu) và tiếng Anh ra đúng chuỗi kỳ vọng ở cả PDF và MD; fixture có ký tự lỗi sinh cảnh báo `UNMAPPED_GLYPHS` (V2-21).
- [x] Fixture heading/bảng tự tạo (PDF xuất từ Word tiếng Việt: heading đánh số 2 cấp, list `a)`, bảng 4 cột có ô gộp và bảng kéo qua 2 trang): heading đúng thứ tự và cấp, bảng đúng vị trí trong thân và đúng số hàng/cột. Không đặt yêu cầu khớp tuyệt đối trên corpus thật.
- [x] Báo cáo chỉ số trên corpus V2-19 theo họ tài liệu (heading precision/recall, bảng, thời gian/RAM mỗi trang); ngưỡng do owner chốt sau khi xem baseline, không đặt trước. *Xong 2026-10-26 (ADR-008 §6.1): text heading recall 0,96–1,00 nhưng cấp heading phẳng; bảng recall 0,40 VI và 0,00 EN; ô gộp 0/2 VI. Chấm trên nhãn trang chọn do Claude duyệt theo ủy quyền owner; owner chưa tự đọc lại và chưa chốt ngưỡng.*

## 3. Hướng dẫn
- **File:** package Python thuần, không phụ thuộc DB/web, trong `services/ai-service` theo cấu trúc của TECH-V2 (V2-03). V2-09 import lại.
- Tham khảo lỗi cũ: `services/ingestion-service/src/services/extractors/`, `preview_extractor.py`.

## 3a. Công cụ đo (2026-10-26)
- `eval/predict_extraction.py` chạy `docproc` trên corpus có nhãn và ghi predictions; `python -m sopilot_eval.extraction --selected-pages` chấm trên trang đã chọn (chế độ mới; chế độ `evaluate` vẫn từ chối nhãn một phần). Adapter thêm `DocElement.header_rows` (số hàng tiêu đề cột mà Docling đánh dấu).

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | PDF nhiều trang, bảng giữa thân, ô gộp, bảng nhiều trang (`page_end`, `row_pages`, `row_spans`); MD (frontmatter, GFM, HTML nhúng); renderer và bất biến offset; Unicode VI/EN; từ chối DOCX/TXT, PDF scan, mã hóa, hỏng | `uv run pytest tests/unit` |
| Xác nhận | Docling trên tập con V2-19, máy owner: ràng buộc cứng, `cell_spans`, thời gian/RAM; kết quả vào bảng §6 của ADR-008 | script trong `eval/` |
| Eval | Script chấm V2-19 trên toàn corpus, lưu kết quả vào báo cáo | theo V2-19 |

### Đóng ticket 2026-11-03
Owner chốt `done`. Bằng chứng: tất cả tiêu chí đã tick; `validate-build.ps1 -Scope ai` xanh (compileall + ruff), `run-tests.ps1 -Scope ai-service -Type unit`: 96 test pass (2026-11-03).
