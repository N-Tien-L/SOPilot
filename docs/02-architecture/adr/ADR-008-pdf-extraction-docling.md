---
id: ADR-008
title: "V2: dùng Docling làm thư viện trích xuất PDF có lớp chữ"
status: approved
created: 2026-10-21
updated: 2026-10-21
author: "Owner"
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
| Phiên bản Docling ghim | `docling==2.142.1` (`docling-core 2.104.0`), extra `pdf` của `services/ai-service`. Lấy model lần đầu từ HuggingFace trên máy owner; vận hành offline dùng `SOPILOT_PDF_ARTIFACTS_PATH` (đường chạy này chưa kiểm riêng) | 2026-10-26 |
| Offline CPU, model nạp từ `artifacts_path` | Chạy CPU (`device=cpu`), không GPU. Cấu hình `artifacts_path` được truyền vào pipeline; Đã chạy 10 PDF (148 trang) với `HF_HUB_OFFLINE=1`, model lấy từ cache HuggingFace, không lỗi: không cần mạng lúc xử lý. **Chưa kiểm** đường `SOPILOT_PDF_ARTIFACTS_PATH` với thư mục tải bằng `docling-tools models download` (xem §6.2) | 2026-10-26 |
| OCR tắt, trang ảnh cho 0 ký tự | Đạt trên fixture synthetic: `do_ocr=False`, trang chỉ có ảnh cho 0 ký tự, không module OCR nào được import (`test_pdf.py`). PDF toàn trang ảnh (NĐ 30, 76 trang) bị chặn ở bước kiểm tra lớp chữ: `NO_TEXT_LAYER` | 2026-10-26 |
| Số trang thật cho mọi phần tử; `furniture` hay thông tin trang cho `V2-21` | Đạt: mọi phần tử có `page`; `page_index` liên tiếp. Docling tách `furniture` (header/footer) thành phần tử riêng: 0–124 phần tử mỗi file, được giữ với `role` header/footer/boilerplate cho V2-21 | 2026-10-26 |
| NFC và dấu tiếng Việt trên PDF mẫu | Đạt: 10/10 PDF có chữ ra NFC; fixture synthetic có đủ dấu thanh và `đ`. 2 ký tự `U+FFFD` trong `nb-qt03` (V2-21 sinh `UNMAPPED_GLYPHS`) | 2026-10-26 |
| Span ô gộp (`cell_spans`) | Docling **có trả** `row_span`/`col_span`: 56 ô gộp trong 10 PDF, ở 49 bảng có ít nhất một ô gộp. Không đo độ đúng so với nhãn (nhãn pilot chưa được owner duyệt). Trên một fixture reportlab có ô gộp dọc, Docling **không** nhận ra span (đặt chữ ở hàng sau, `row_span=1`): span không đáng tin tuyệt đối | 2026-10-26 |
| Thời gian và RAM đỉnh mỗi trang trên máy owner | AMD 16 luồng, 33,6 GB, CPU, 4 luồng Docling. 10 PDF, 148 trang: 1,0 đến 8,1 s/trang (trung vị khoảng 3,4); RAM đỉnh tiến trình 1,8 đến 2,1 GB gồm model (đỉnh theo tiến trình, không theo trang). Mục tiêu khởi đầu (≤ 30 s cho 20 trang) **không đạt ở tài liệu nhiều bảng** (`nb-qt01`: 8,1 s/trang, 14 trang mất 113 s) và đạt ở EPA (1,0 đến 1,9 s/trang). Chưa chạy lại để đo biến thiên, chưa đo lần đầu ngoài cache model | 2026-10-26 |
| Heading và bảng theo họ tài liệu (V2-19) | Chấm trên nhãn trang chọn (xem §6.1): **text heading recall 96–100%, precision 64–88%; cấp heading không dùng được** (Docling trả gần như toàn cấp 1, chấm cả cấp thì recall 65–69% VI, 57% EN); **bảng recall 40% VI, 0% EN**, precision 25% và 0%; ô gộp 0/2 VI (22 ô dự đoán), 2/6 EN. Mẫu nhỏ (10 file, trang chọn), nhãn do Claude duyệt theo ủy quyền owner, owner chưa tự đọc lại | 2026-10-26 |

### 6.1 Kết quả chấm trên nhãn trang chọn (V2-20, 2026-10-26)

Nguồn: `eval/predict_extraction.py` (cùng code `docproc` của service) và
`python -m sopilot_eval.extraction --selected-pages` trên 10 PDF của V2-19; nd30 (scan) bị loại khỏi điểm
vì `NO_TEXT_LAYER`. Nhãn chỉ phủ các trang đã chọn và do Claude duyệt từ ảnh trang theo ủy quyền của owner
(`reviewer_id=claude-on-behalf-of-owner`); owner chưa tự đọc lại. Khớp chính xác theo chuỗi đã chuẩn hóa.
Kết quả thô nằm ở `eval/results/extraction-docling/` (không commit).

| Nhóm | Heading, chỉ text + trang (P / R) | Heading, thêm cấp (P / R) | Bảng (P / R) | Ô gộp (khớp / nhãn / dự đoán) | Khung lọt vào nội dung |
|---|---|---|---|---|---|
| VI, ISO 9001 (8 file) | 0,64 / 0,96 | 0,44 / 0,65 | 0,25 / 0,40 | 0 / 2 / 22 | 13 / 58 |
| EN, EPA (2 file) | 0,88 / 1,00 | 0,50 / 0,57 | 0,00 / 0,00 | 2 / 6 / 2 | 6 / 15 |

Với luật phụ "mục danh sách có số thứ tự ngắn tính là heading" (`docling+numbering`), recall text VI lên 1,00 và
recall có cấp VI lên 0,69; EN không đổi.

Quan sát (đọc từ so sánh dự đoán và nhãn, không phải thống kê):
- **Cấp heading phẳng:** Docling trả gần như mọi heading ở cấp 1 (ví dụ `5.1.2.1` cấp 1, nhãn cấp 4). Cấp phải suy ra từ số thứ tự ở V2-22.
- **Heading thừa:** khung đầu trang (tên cơ quan, "QUY TRÌNH ...") và dòng đậm đầu gạch ("- Chương trình đánh giá:") bị coi là heading, làm precision VI chỉ 0,64.
- **Bảng phức tạp:** Docling không tách bảng lồng. Trang 4 của nb-qt01 ra một bảng 8 hàng 7 cột kèm 16 ô gộp, trong khi nhãn là hai bảng (4×5 và bảng lồng 4×5). Khung đầu trang kiểu bảng cũng thành bảng riêng. Bảng thông tin của EPA ra 4 hàng, nhãn 6 hàng.
- **Ô gộp không dùng được** để lặp giá trị xuống từng hàng ở V2-22 mà không kiểm: tập ô dự đoán lớn mà chỉ khớp nhãn ở EPA.
- **Khung lọt:** header dạng bảng nằm trong thân nên chưa bị tách; bước tách khung là V2-21, nên số này là mốc trước V2-21.
- **Không đo metadata** (thuộc V2-21).

Hệ quả cho V2-21/V2-22: không dựa vào cấp heading hay `cell_spans` của Docling mà không có lớp suy luận và kiểm riêng;
cần luật cho bảng lồng và khối khung kiểu bảng. Chưa có ngưỡng chấp nhận: owner chốt sau khi xem baseline này.


### 6.2 Thí nghiệm cấu hình và ngưỡng tạm (2026-10-26)

Cùng 10 PDF, cùng nhãn trang chọn, chạy offline (`HF_HUB_OFFLINE=1`). Một lần chạy mỗi cấu hình; thứ tự chạy cố định nên lượt đầu có thể chịu thêm khởi động nguội. Kết quả thô ở `eval/results/extraction-exp/` (không commit).

| Cấu hình | Tổng thời gian, 148 trang | s/trang (trung vị) | RAM đỉnh | Bảng khớp nhãn (gold 12) |
|---|---|---|---|---|
| mặc định, 4 luồng (`TableFormerMode.ACCURATE`, cell matching bật) | 480 s | 3,2 (2,4) | 2191 MB | 4 |
| 4 luồng, `do_cell_matching=False` | 407 s | 2,8 (3,5) | 2178 MB | 5 |
| 8 luồng | 296 s | 2,0 (2,1) | 2201 MB | 4 |
| 12 luồng | 253 s | 1,7 (2,0) | 2159 MB | 4 |
| 12 luồng, TableFormer V2 (`SOPILOT_PDF_TABLE_MODEL=v2`) | 253 s | 1,7 | 2522 MB | 5 |

- **Chế độ bảng:** mặc định của Docling 2.142.1 đã là `ACCURATE`, nên baseline §6.1 đã là chế độ chính xác nhất của TableFormer V1. `FAST` chỉ kém hơn, không thử.
- **Cell matching:** tắt cho 5/12 so với 4/12, mỗi file lệch tối đa một bảng theo cả hai hướng (nhiễu). **Không đổi mặc định.** Log mặc định có cảnh báo `MatchingPostProcessor` "pdf cells ... dropped from the table" ở nb-qt03, nb-qt04, tb-qt05: ô PDF bị bỏ khỏi bảng, đáng điều tra riêng (mất chữ trong bảng).
- **Số luồng:** 4 → 12 giảm thời gian còn 53%, RAM và chất lượng bảng không đổi. Biến `SOPILOT_PDF_THREADS` (mặc định 4) và hai biến mới `SOPILOT_PDF_TABLE_MODE`, `SOPILOT_PDF_CELL_MATCHING` ở `extract/pdf.py`. Trên máy owner nên đặt `SOPILOT_PDF_THREADS=12`.
- **Mục tiêu thời gian:** ở 12 luồng, tài liệu nhiều bảng nhất (`nb-qt01`) 5,0 s/trang, cả corpus 1,7 s/trang trung bình, gần mục tiêu 1,5 s/trang (≤ 30 s cho 20 trang). Chấp nhận ≤ 10 s/trang cho tài liệu nhiều bảng.
- **TableFormer V2** (`docling-project/TableFormerV2`, Apache-2.0, 564 MB, chạy offline từ cache): bảng khớp 5/12 so với 4/12 của V1 cùng 12 luồng (khác nhau ở 3 file, theo cả hai hướng: nb-qt02 và nb-thanhtra06 thêm, nb-qt04 mất), tức là không khác biệt có ý nghĩa. **Không trả ô gộp nào** (0 dự đoán, V1 dự đoán 24 và khớp 2/8), RAM đỉnh 2522 MB (V1 2159 MB), thời gian như nhau. Ngoài trang có nhãn, V2 sinh vài bảng rất lớn (74 đến 83 hàng, 94–99% ô rỗng): đó là các biểu mẫu trắng (bảng "Sửa đổi tài liệu" trang 2 của nb-qt03 có khoảng 38 hàng trống thật, V2 ra 83), tức là chia hàng thừa chứ không phải nội dung bị hợp nhất; V1 không sinh bảng nào như vậy. **Không chuyển sang V2.** Chọn bật bằng `SOPILOT_PDF_TABLE_MODEL=v2`, mặc định `v1`.
- **Có mất chữ không (đo toàn tài liệu, so từ trong lớp chữ PDF với từ Docling trả, tính cả số thứ tự list, 12 luồng, một lần chạy):**

  | Họ | V1 mất | V2 mất | V2 thừa so với PDF |
  |---|---|---|---|
  | `nb-*` (4 file VI) | 0,1–0,8% | 1,6–2,7% | 28–211 từ |
  | `tb-*` (3 file VI) | 2,4–5,9% | 2,4–5,8% | 28–90 từ |
  | `nb-thanhtra06` | 0,2% | 1,1% | 149 từ |
  | `epa-*` (2 file EN) | 0,2–0,3% | 0,3% | 8–37 từ |

  V1 hầu như không mất chữ ở thân văn bản và bảng: các ô bị "dropped" trong cảnh báo `MatchingPostProcessor` gần như không để lại dấu vết (nb-qt03 chỉ thiếu "không nhận chấp"). Phần mất chữ của V1 đến từ hai chỗ khác: (1) **tên cơ quan trong ô logo của khung đầu trang** ("SỞ XÂY DỰNG", "CẢNG VỤ HÀNG HẢI THÁI BÌNH") bị bỏ gần như ở mọi trang, nên V2-21 không thể lấy lại từ đầu ra; (2) **sơ đồ quy trình (flowchart)**: `tb-qt03` trang 5 mất khoảng 128 trên 154 từ (83% trang), vì Docling coi sơ đồ là ảnh và không lấy chữ trong đó khi OCR tắt. Với SOP đây là mất mát thật (các bước quy trình nằm trong sơ đồ). V2 mất nhiều hơn V1 trên mọi họ VI có bảng (tiêu đề cột như "tài liệu", "lần ban hành") và thêm từ thừa. Hạn chế của số này: so đa tập từ (không so thứ tự), một lần chạy, chuỗi lỗi glyph trong PDF nguồn (`aủ`, `nả`) cũng tính là mất.
- **Lấy lại chữ trong vùng ảnh bằng lớp chữ PDF (đã triển khai trong `extract/pdf.py`, 2026-10-26):** với mỗi `picture` Docling trả, lấy chữ pdfium nằm trong khung (`get_text_bounded`), bỏ các dòng Docling đã xuất trên cùng trang (dòng nhiều từ nằm trong chữ đã xuất; dòng một từ chỉ bị bỏ khi trùng đúng một phần tử/ô đã xuất), cần ít nhất 2 từ còn lại. Kết quả là phần tử `paragraph` role `figure_text`, được renderer đưa vào Markdown (`NORMALIZER_VERSION` lên `"2"`). Chữ trong vùng ảnh nằm trọn ở 15% đầu hoặc 10% cuối trang (ô logo) giữ role `header`/`footer`, không vào Markdown; V2-21 vẫn có thể phân loại lại. Chữ mất theo đo toàn tài liệu: `tb-qt01` 60 → 30 từ, `tb-qt03` 171 → 31, `tb-qt05` 46 → 1, `nb-qt03` 19 → 14; heading, bảng, ô gộp không đổi (4/12 bảng, 22/33 heading, 2/8 ô gộp), tốc độ không chậm hơn. Sơ đồ ở `tb-qt03` trang 5 vào Markdown đủ 132 từ. Còn lại: "xây dựng" ở `nb-*` (không có vùng ảnh), chuỗi glyph lỗi, mã chân trang EPA, và vài logo ở trang Docling không tách thành ảnh (còn 5 lần "cảng vụ hàng hải thái bình" ở `tb-qt01`, `tb-qt03`). Giới hạn: (1) thứ tự chữ là thứ tự lớp chữ PDF; pdfium trả sơ đồ `tb-qt03` thành **một dòng liền**, nên dedupe theo dòng không chia nhỏ hơn được, và số trang nằm trong khung (`5`) lọt vào đầu đoạn; (2) không có mũi tên/cạnh nên sơ đồ chỉ là danh sách bước rời, nhánh CÓ/KHÔNG không gắn với bước; (3) mẫu chỉ có 3 họ tài liệu có ảnh chứa chữ.
- **Bảng vẫn kém:** không cấu hình nào nâng bảng khớp nhãn vượt 5/12 (4–5/12 ở mọi cấu hình, mẫu quá nhỏ để phân biệt). Chưa thử `GraniteVisionTableStructureOptions` (VLM, nặng).

**Ngưỡng tạm** (nhãn chưa được owner đọc lại, không dùng để đóng V2-20):

| Chỉ số | Ngưỡng | Đo hiện tại |
|---|---|---|
| Text heading recall | ≥ 0,95 | 0,96–1,00 (đạt) |
| Heading precision, sau lọc khung ở V2-21 | ≥ 0,85 | 0,64–0,88 thô (chưa đo sau lọc) |
| Cấp heading, sau suy từ số thứ tự ở V2-22 | ≥ 0,90 | 0,65–0,69 (chưa đạt) |
| Bảng phát hiện đúng (recall) | ≥ 0,80 | 0,40 VI, 0,00 EN (chưa đạt) |
| Bảng đúng số hàng và cột, trên bảng đã phát hiện | ≥ 0,70 | chưa đo riêng |
| Ô gộp | không đặt ngưỡng | không dùng |
| NFC; scan bị từ chối `NO_TEXT_LAYER` | 100% | đạt |

**Quyết định tạm:** cấp heading suy từ số thứ tự (V2-22); heading thừa lọc ở V2-21; `cell_spans = None` mặc định cho tới khi ô gộp được kiểm; bảng lồng là hạn chế đã biết, giữ `nb-qt01` trang 4 làm test hồi quy. Hai ngưỡng bảng chưa đạt nên quyết định cuối (chấp nhận, thêm model, hoặc xử lý riêng bảng khó) thuộc owner sau khi đọc lại nhãn.

## 7. Tác động & hệ quả

- **Tích cực:** bỏ spike so sánh nên `V2-20` bắt đầu thẳng vào adapter; giấy phép MIT; một nguồn cấu trúc cho PDF.
- **Đánh đổi chấp nhận:** quyết định trước khi có số đo; phụ thuộc nặng hơn (model, `torch`); nếu bước xác nhận của `V2-20` thất bại thì mất công chuyển adapter (nhỏ vì cô lập sau `extract/pdf.py`).
- **Hành động tiếp theo:**
  - `V2-20`: xác nhận Docling theo §5 và điền §6.
  - `V2-19`: gom tập con tối thiểu (≥ 6 PDF tiếng Việt, 2 PDF EPA, 1 PDF scan) để chạy xác nhận.
  - Cập nhật TECH-V2-ai-service §11 Q8, PRD-V2, PLAN-V2 (đã làm cùng ADR này).
