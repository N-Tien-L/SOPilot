---
id: ADR-008
title: "V2: dùng Docling làm thư viện trích xuất PDF có lớp chữ"
status: approved
created: 2026-10-21
updated: 2026-10-21
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/02-architecture/designs/TECH-V2-ai-service.md
  - docs/03-plans/tickets/V2-20-structured-extraction.md
  - docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md
deciders: ["Owner"]
amends: []
supersedes: []
superseded_by: ""
---

# ADR-008: Docling làm thư viện trích xuất PDF

> **Trạng thái:** `approved` (2026-10-21) | **Ngày quyết định:** `2026-10-21` | **Người quyết định:** `Owner`
>
> **Chưa có số đo spike.** Quyết định này dựa trên thông tin tài liệu chính thức đã tra ngày 2026-10-21 và lựa chọn của owner; chưa thử Docling trên corpus V2-19, chưa đo tốc độ, RAM hay chất lượng tiếng Việt. `V2-20` xác nhận quyết định theo các ràng buộc cứng ở §4 và ghi số đo thật vào §6. Một ràng buộc cứng không đạt thì ADR này quay lại `draft` (§5).

---

## 1. Bối cảnh & vấn đề cần quyết định

- TECH-V2-ai-service §5.2 và PRD-V2 FR-08 yêu cầu **một** thư viện chuyển PDF có lớp chữ sang `StructuredDocument` (heading, đoạn, list, bảng, số trang thật, thứ tự đọc), từ đó ai-service tự render Markdown chuẩn có offset. Không trích plain text rồi dựng lại cấu trúc, không chuỗi fallback, không OCR, không LLM viết lại nội dung.
- Báo cáo [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) §6 đặt hai ứng viên: **Docling** (MIT) và **PyMuPDF 2.x** (AGPL-3.0 hoặc giấy phép thương mại), chọn bằng spike 2 ngày trong `V2-20`.
- Ngày 2026-10-21 owner chốt Docling mà không chờ spike so sánh.
- Ràng buộc chung: chạy local trên CPU (máy owner, 32 GB RAM), miễn phí, ai-service đã cần `torch` cho `bge-m3`, chỉ PDF có lớp chữ và Markdown trong MVP.

## 2. Tiêu chí đánh giá

Theo AUDIT-markdown-normalization §6.2:
1. Chạy offline trên CPU, model tải trước; không gọi mạng lúc xử lý.
2. OCR tắt được hoàn toàn và kiểm chứng được.
3. Mỗi phần tử có số trang thật; tách được header/footer hoặc đủ thông tin trang để `V2-21` tự tách.
4. Tiếng Việt NFC, không mất dấu.
5. Giấy phép MIT/Apache/BSD được ưu tiên; AGPL cần owner xác nhận.
6. Thêm 2026-10-21 (audit theo loại query): trả được span ô gộp (`cell_spans`) để chunk `PROCEDURE_STEP` lặp giá trị ô gộp xuống từng hàng (TECH-V2-ai-service §5.2, §5.4).
7. Chất lượng heading/bảng theo họ tài liệu, thời gian và RAM mỗi trang, công bảo trì: chỉ so sánh được sau khi có số đo.

## 3. Các phương án xem xét

### Phương án 1: Docling
- **Mô tả:** `DoclingDocument` có cây `body` và `furniture` (header/footer tách khỏi thân), thông tin provenance theo phần tử, layout model, thứ tự đọc, TableFormer cho bảng (`FAST`/`ACCURATE`).
- **Ưu điểm (+):** giấy phép MIT; `furniture` hỗ trợ `V2-21`; có `artifacts_path` và `docling-tools models download` để chạy offline; tùy chọn số luồng và giới hạn hàng đợi trang để giảm RAM; phụ thuộc `torch` trùng với ai-service nên chi phí thêm nhỏ hơn (nhận định, chưa đo).
- **Nhược điểm (-):** model tải lần đầu và nặng hơn; OCR là extra phải tắt bằng cấu hình; tên trường provenance cụ thể, giá trị mặc định `do_ocr`, kích thước image Docker và chất lượng tiếng Việt chưa kiểm chứng.

### Phương án 2: PyMuPDF 2.x (kèm layout)
- **Mô tả:** layout analysis không cần GPU, `page_chunks` trả `page_boxes` có lớp `section-header`, `table`, `page-header`, `page-footer`, `list-item`.
- **Ưu điểm (+):** nhẹ hơn về phụ thuộc theo mô tả của nhà phát hành; API quen thuộc.
- **Nhược điểm (-):** giấy phép AGPL-3.0 (hoặc thương mại), cần owner xác nhận và có nghĩa vụ nếu sau này cung cấp qua mạng; bản 2.0 phát hành 2026-10-19, API còn mới; OCR tự chạy nếu có engine, phải tắt.

### Đã loại theo phạm vi (không phải kết quả đo)
Marker và MinerU (giấy phép GPL/AGPL hoặc điều khoản model riêng, nặng hơn mục tiêu), `unstructured` (nhiều phụ thuộc, không mang lại cấu trúc bảng tốt hơn theo tài liệu đọc được).

## 4. Quyết định & biện luận

- **Phương án được chọn: Phương án 1, Docling**, đặt sau adapter `services/ai-service/src/sopilot_ai/docproc/extract/pdf.py`. Đây là nơi duy nhất phụ thuộc thư viện; `V2-21` và `V2-22` làm việc trên `StructuredDocument` nên không bị ràng buộc bởi lựa chọn.
- **Lý do:** (1) giấy phép MIT không cần quyết định pháp lý thêm, khác AGPL; (2) `furniture` tách sẵn header/footer, khớp bước tách khung của `V2-21`; (3) cấu hình offline có sẵn; (4) chi phí phụ thuộc `torch` đã nằm trong ai-service. Lý do thứ (4) và khả năng chạy trên CPU trong ngân sách thời gian là **nhận định, chưa đo**.
- **Cấu hình bắt buộc:** OCR tắt hoàn toàn và có test (trang ảnh cho 0 ký tự, không gọi engine OCR nào); model nạp từ `SOPILOT_PDF_ARTIFACTS_PATH` (TECH-V2-ai-service §10), không tải lúc xử lý; giới hạn luồng và hàng đợi trang cấu hình được; **ghim phiên bản** (bản tra ngày 2026-10-21 là `docling 2.140.0`, phát hành 2026-10-16; phiên bản ghim chính thức ghi ở §6 sau khi `V2-20` cài và chạy).
- **Chỉ một thư viện** trong runtime: không dùng PyMuPDF song song hay làm fallback.

## 5. Điều kiện xét lại (chưa có số đo spike)

`V2-20` xác nhận Docling bằng các kiểm chứng sau, trên tập con tối thiểu của `V2-19` (hoặc fixture synthetic nếu corpus chưa đủ, gắn nhãn synthetic):

1. **Ràng buộc cứng** (tiêu chí 1–5 ở §2): không đạt điều nào thì ADR này chuyển `draft` và `V2-20` dừng để hỏi owner, không tự đổi thư viện.
2. **Span ô gộp** (tiêu chí 6): đo trên bảng có ô gộp. Nếu Docling không trả span, `cell_spans = None`, chunker không đoán giá trị cho ô trống, và hạn chế này được ghi vào §6; đây không tự làm ADR quay lại `draft`.
3. **Thời gian và RAM:** mục tiêu khởi đầu (chưa có căn cứ đo): trích xuất PDF 20 trang không quá một nửa ngân sách 60 s của NFR, để chừa phần cho embed. Vượt rõ rệt thì báo owner, có thể mở lại so sánh với PyMuPDF 2.x (khi đó AGPL cần owner xác nhận, PLAN-V2 §4).
4. **Chất lượng heading/bảng tiếng Việt** theo họ tài liệu: báo cáo số đo, không có ngưỡng đặt trước (AUDIT-markdown-normalization §6.2 mục 6).

## 6. Kết quả xác nhận (điền ở V2-20)

| Mục | Kết quả | Ngày |
|---|---|---|
| Phiên bản Docling ghim | chưa đo | — |
| Offline CPU, model nạp từ `artifacts_path` | chưa đo | — |
| OCR tắt, trang ảnh cho 0 ký tự | chưa đo | — |
| Số trang thật cho mọi phần tử; `furniture` hay thông tin trang cho `V2-21` | chưa đo | — |
| NFC và dấu tiếng Việt trên PDF mẫu | chưa đo | — |
| Span ô gộp (`cell_spans`) | chưa đo | — |
| Thời gian và RAM đỉnh mỗi trang trên máy owner | chưa đo | — |
| Heading và bảng theo họ tài liệu (V2-19) | chưa đo | — |

## 7. Tác động & hệ quả

- **Tích cực:** bỏ spike so sánh nên `V2-20` bắt đầu thẳng vào adapter; giấy phép MIT; một nguồn cấu trúc cho PDF.
- **Đánh đổi chấp nhận:** quyết định trước khi có số đo; phụ thuộc nặng hơn (model, `torch`); nếu bước xác nhận của `V2-20` thất bại thì mất công chuyển adapter (nhỏ vì cô lập sau `extract/pdf.py`).
- **Hành động tiếp theo:**
  - `V2-20`: xác nhận Docling theo §5 và điền §6.
  - `V2-19`: gom tập con tối thiểu (≥ 6 PDF tiếng Việt, 2 PDF EPA, 1 PDF scan) để chạy xác nhận.
  - Cập nhật TECH-V2-ai-service §11 Q8, PRD-V2, PLAN-V2 (đã làm cùng ADR này).
