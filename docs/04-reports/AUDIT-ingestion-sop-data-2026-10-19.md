---
id: AUDIT-ingestion-sop-data-2026-10-19
title: "Phân tích pipeline nạp SOP: định dạng, cấu trúc tài liệu thật và lỗ hổng"
status: final
type: audit
scope: ingestion
verdict: conditional-recommendation
author: "Owner"
created: 2026-10-19
updated: 2026-10-20
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/03-plans/tickets/V2-09-ai-service-ingest-retrieval.md
  - docs/04-reports/RESEARCH-02-dataset-and-labeling.md
---

> **Owner chốt 2026-10-20:** hoãn DOCX sau MVP V2 để giảm độ phức tạp trích xuất và kiểm thử. Phạm vi hiện hành là PDF có lớp chữ, MD, TXT (PRD-V2 FR-06); DOCX trả `415` ở upload, không tạo job, hướng dẫn xuất PDF có lớp chữ. Các nhận xét DOCX trong audit là lịch sử, không phải yêu cầu nghiệm thu MVP. Không đổi trạng thái hoặc bộ đếm ticket.


# Phân tích pipeline nạp SOP

Phạm vi: `services/ingestion-service` (luồng chính `pipeline.py`), `preview_extractor.py`, và phần trích xuất Tika/PDFBox trong knowledge-service. Chỉ đọc code và chạy một probe nhỏ; không sửa code.

## 1. Kết luận chính

Pipeline được viết cho **bộ dữ liệu mẫu là handbook tiếng Anh dạng Markdown** (`ingest_base_dataset.py`: `BASE_DATASET_PATH = "/app/base_dataset/handbook"`, chỉ quét `*.md`; standardizer có regex xóa shortcode Hugo). Nó chưa được thiết kế cho SOP doanh nghiệp Việt Nam dạng DOCX/PDF. Phần hỗ trợ nhiều định dạng (ảnh, OCR, XLSX) là ghép thêm, còn phần hiểu cấu trúc tài liệu thì chưa làm.

Ba nghi ngờ ban đầu đều đúng:
1. Ôm đồm định dạng (ảnh, OCR) trong khi DOCX/PDF/MD xử lý chưa sạch.
2. Chưa tách phần "khung" (quốc hiệu, tiêu ngữ, chữ ký, header/footer, bảng phê duyệt) khỏi nội dung.
3. Giả định cấu trúc kiểu văn bản luật (Chương/Điều/Khoản); SOP kiểu ISO và văn bản không chuẩn bị chia sai.

## 2. Hiện trạng (đã kiểm trong code và probe)

### 2.1. Định dạng
- Có 3 bộ trích xuất: `extractors/*` (luồng chính), `preview_extractor.py` (gợi ý metadata bằng LLM), Tika/PDFBox ở knowledge-service (`DocumentParsingService`). `services/extractor.py` là code chết.
- knowledge-service `FileType` cho `XLSX/DOC/XLS`, nhưng ingestion không có extractor cho các đuôi này: upload thành công, pipeline `FAILED` với `No extractor for extension`.
- PDF: OCR tesseract 300 dpi cho mọi trang có dưới `ocr_fallback_min_text_length=50` ký tự (gồm trang bìa, trang chữ ký). Chạy đồng bộ trong hàm `async`, chặn event loop. Ảnh bị OCR hai lần (`image_to_data` rồi `image_to_string`). Mặc định code `ocr_language="eng"`; `.env.example` đặt `eng+vie` (chưa kiểm compose có truyền biến này).

### 2.2. Trích xuất
- Extractor tạo `chunks` có heading style và số trang, nhưng `pipeline.py` chỉ dùng `extracted.text`: mất số trang (không trích dẫn theo trang được) và mất heading style DOCX.
- DOCX (`extractors/docx.py`): bảng bị dồn xuống cuối văn bản; ô gộp lặp lại; số thứ tự tự động của Word ("1.", "5.1", "a)") không có trong `para.text`; `page_count` là số section Word.
- PDF (`extractors/pdf.py`): `get_text("text")` thô; header/footer lặp mỗi trang ("Mã số · Lần ban hành · Trang x/y") lẫn vào nội dung; bảng dàn phẳng; dòng ngắt giữa câu.

### 2.3. Standardizer (`standardizer.py`)
Probe với một mẫu SOP tiếng Việt cho kết quả:

| Đầu vào | Kết quả |
|---|---|
| `Điều 1. Mục đích` | `title='1'`, dòng heading bị xóa khỏi nội dung chunk |
| Section thứ 3 | `path=['', '1', '2', '5']` (cộng dồn anh em, không phải cha) |
| `...căn cứ ⏎ Điều 5 Luật Doanh nghiệp.` | Tách nhầm thành heading mới |
| `1. MỤC ĐÍCH`, `5.1 Lập đề nghị...` | Không nhận là heading |
| Quốc hiệu, tiêu ngữ, mã số | Thành một section/chunk riêng được embed |

### 2.4. Chunk và embedding (`chunker.py`, `embedding_service.py`)
- Đếm token bằng `cl100k_base`, không khớp model embedding; tiếng Việt khoảng 2,3 token/từ (probe: 32 token cho 14 từ).
- Cắt theo token có thể cắt giữa ký tự UTF-8, sinh "�" ở mép chunk (probe: 1/31 điểm cắt lỗi).
- Chunk cha không giới hạn kích thước, nhưng `embed_batch` cắt còn 512 token: section dài chỉ embed phần đầu.
- Chunk con không mang tiêu đề/ngữ cảnh.
- `_build_token_char_index` là O(n²).

### 2.5. Dedup (`deduplicator.py`)
Fingerprint ngữ nghĩa lấy 3 cửa sổ (đầu 3000, giữa 4000, cuối 2000 ký tự), mỗi cửa sổ cắt 512 token, so ngưỡng chặn 0,98 với mọi version. Rủi ro (chưa đo trên dữ liệu thật): bản sửa đổi của cùng SOP đổi vài bước ngoài 3 cửa sổ bị đánh `DUPLICATE` và bỏ qua; hai SOP khác nhau chung template có thể bị coi là trùng.

### 2.6. Lỗi khác
- `ALLOWED_BUCKETS` thiếu `sopilot-documents`; `embedding_model="BGE_M3"` hard-code (đã có trong drift của `CLAUDE.md`).
- Trích xuất rỗng vẫn thành `READY` với 0 chunk.
- `mark_not_latest` gọi trước `bulk_insert`; nếu insert lỗi thì phụ thuộc rollback.

## 3. SOP ngoài thực tế

> Chưa mở được file SOP thật (các PDF THADS trả 404). Phần này tổng hợp từ kết quả tìm kiếm và chuẩn đã biết, chưa phải phân tích trên corpus thật.

| Họ tài liệu | Dấu hiệu | Phần mang thông tin |
|---|---|---|
| Quy trình ISO 9001 (phổ biến nhất ở VN) | Bảng header mỗi trang (mã hiệu, lần ban hành, ngày hiệu lực, trang x/y); bảng Soạn thảo/Soát xét/Phê duyệt; bảng theo dõi sửa đổi; mục đánh số Mục đích, Phạm vi, Tài liệu viện dẫn, Định nghĩa, Nội dung, Biểu mẫu, Hồ sơ | "Nội dung" thường là bảng hoặc lưu đồ: Trách nhiệm / Các bước / Mô tả / Biểu mẫu |
| Văn bản hành chính (NĐ 30/2020) | Quốc hiệu, tiêu ngữ, số/ký hiệu, trích yếu, nơi nhận, chữ ký, dấu; quy chế dùng Chương/Điều/Khoản | Thân Điều/Khoản |
| SOP GMP/FDA, EPA QA/G-6 | Purpose, Scope, Responsibilities, Procedure (bước đánh số nhiều cấp), References, Revision history | Procedure |
| Wiki/handbook (Markdown, Confluence) | Heading `#` rõ, ít khung | Toàn bộ |
| Không chuẩn | Heading bằng chữ đậm, số gõ tay, văn liền | Phải đoán cấu trúc |

Phần khung nên **bỏ khỏi index nhưng giữ làm metadata**: mã số, lần ban hành, ngày hiệu lực, người phê duyệt.

## 4. Hệ thống tương tự

| Hệ thống | Điều đáng học |
|---|---|
| Docling | Cây tài liệu có kiểu phần tử; HybridChunker chia theo cấu trúc, gộp mảnh nhỏ, lặp tiêu đề bảng, tokenizer khớp model embedding |
| Unstructured | Phần tử có kiểu (Title, NarrativeText, ListItem, Table, Header, Footer); `chunk_by_title` |
| RAGFlow | Template chunk theo loại tài liệu (General, Laws, Manual, Table...) và nhận dạng bố cục bằng model thị giác |
| MarkItDown / Mammoth | DOCX → Markdown giữ Heading 1–6 và bảng; không nhận heading giả bằng chữ đậm |
| Anthropic Contextual Retrieval | Gắn 50–100 token ngữ cảnh vào đầu chunk trước khi embed và index BM25 |

## 5. Hướng giải quyết

1. **Corpus SOP thật (20–50 file)** nhiều họ tài liệu, có nhãn loại, làm thước đo chất lượng trích xuất.
2. **Thu hẹp định dạng** còn DOCX, PDF có lớp chữ, MD, TXT; từ chối ảnh/PDF scan với thông báo rõ; OCR sau cờ cấu hình.
3. **Một bộ trích xuất duy nhất xuất Markdown có cấu trúc** (DOCX theo thứ tự body, có numbering, heading, bảng đúng chỗ; PDF layout-aware). Bỏ các bộ trùng.
4. **Tách khung, giữ ruột**: header/footer lặp, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt và sửa đổi đưa vào metadata.
5. **Nhận diện loại tài liệu, rẽ nhánh chia chunk** (ISO, Điều/Khoản, Markdown, văn xuôi).
6. **Bảng quy trình**: mỗi hàng (bước) thành một đơn vị nội dung kèm tiêu đề cột.
7. **Sửa chunker**: tokenizer khớp model, chunk mang đường dẫn tiêu đề, giới hạn chunk cha, gộp section nhỏ.
8. **Trích metadata từ nội dung**: mã số, lần ban hành, ngày hiệu lực, bộ phận.
9. **Dedup theo vòng đời phiên bản**: không tự bỏ version mới của cùng tài liệu; chỉ cảnh báo trùng giữa tài liệu khác nhau.
10. **(Tùy chọn) Contextual retrieval** sau khi các mục 3–7 xong.

## 6. Quan hệ với V2

PRD-V2 và V2-09 đã chốt một phần: định dạng PDF/DOCX/MD/TXT, OCR ảnh ngoài phạm vi, trùng chỉ theo SHA-256 trong workspace, giữ số trang và tiêu đề mục, không cắt bằng `tiktoken`. `ingestion-service` sẽ được thay bằng `services/ai-service` (V2-09) và gỡ ở V2-17. Vì vậy các mục 3–9 nên đi vào TECH-V2 (V2-03) và V2-09, không sửa trên `ingestion-service` cũ.

Corpus eval của V2-06 (RESEARCH-02) là GitLab Handbook tiếng Anh dạng Markdown: không đo được chất lượng trích xuất DOCX/PDF tiếng Việt. Mục 1 cần một corpus trích xuất riêng.

## 7. Chưa xác minh
- Chưa chạy pipeline trên file DOCX/PDF thật; các lỗi DOCX numbering, bảng, header/footer PDF suy ra từ code và hành vi đã biết của thư viện.
- Rủi ro dedup chặn nhầm version chưa đo.
- Chưa kiểm `OCR_LANGUAGE` thực tế trong compose.

## Nguồn
- [QT.ISO.01 THADS Trà Vinh](https://thads.moj.gov.vn:443/travinh/noidung/thongbao/Lists/ThongBao/Attachments/185/QT%2001%20%20%20KSTT%20d%E1%BA%A1ng%20v%C4%83n%20b%E1%BA%A3n.pdf)
- [Thể thức văn bản theo NĐ 30 (luatvietnam)](https://luatvietnam.vn/hanh-chinh/the-thuc-van-ban-570-94255-article.html)
- [Sơ đồ thể thức VB hành chính](https://thuviennhadat.vn/phap-luat/so-do-bo-tri-cac-thanh-phan-the-thuc-van-ban-hc-ap-dung-tu-0532020-640632.html)
- [Lưu đồ quy trình ISO (MISA)](https://amis.misa.vn/133441/cach-ve-luu-do-quy-trinh-theo-iso/)
- [EPA QA/G-6](https://www.epa.gov/sites/default/files/2015-06/documents/g6-final.pdf)
- [GMP QMS-005](https://www.gmpsop.com/gmp_documents/qms-005/)
- [Docling + OpenSearch](https://opensearch.org/blog/building-powerful-rag-pipelines-with-docling-and-opensearch/)
- [Unstructured chunking](https://docs.unstructured.io/open-source/core-functionality/chunking)
- [RAGFlow (DataCamp)](https://www.datacamp.com/tutorial/ragflow)
- [Anthropic Contextual Retrieval](https://anthropic.com/news/contextual-retrieval)
- [MarkItDown office docs](https://www.mintlify.com/microsoft/markitdown/formats/office-documents)
