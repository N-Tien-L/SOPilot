---
id: V2-22
title: "ai-service: nhận diện loại tài liệu, bảng quy trình và chunk theo cấu trúc"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-04
author: "Owner"
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-07, V2-09, V2-28]
branch: "feat/ai-qa-structure-chunking"
assignee: pair
---

# TICKET V2-22: Chunk theo cấu trúc

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 5, 6 và 7, PRD-V2 FR-08. Standardizer cũ chỉ nhận Chương/Điều/Khoản, làm mất tiêu đề, cộng dồn sai `section_path`, tách nhầm câu bị ngắt dòng, và chunker đếm token bằng `cl100k`.

## 2. Tiêu chí Hoàn thành
- [x] Nhận diện họ tài liệu (quy trình ISO, Chương/Điều/Khoản, Markdown/wiki, văn xuôi không chuẩn) từ cấu trúc của V2-20; ưu tiên heading Markdown (`#`), sau đó mẫu đánh số (`1.`, `5.1`, `I.`, `Điều n`), cuối cùng mới tới heuristic (dòng in hoa, chữ đậm). *Xong 2026-10-26: `chunk/family.py`, `chunk/headings.py`.*
- [x] Tiêu đề section giữ đầy đủ chữ (không chỉ số); `section_path` là chuỗi tổ tiên, không phải các section anh em. *Xong 2026-10-26.*
- [x] Bảng quy trình (Trách nhiệm / Bước / Mô tả / Biểu mẫu): mỗi hàng là một đơn vị nội dung kèm tiêu đề cột; bảng dài lặp tiêu đề cột khi bị cắt. Sửa 2026-10-21 (audit theo loại query, owner chốt P0-3, TECH-V2-ai-service §5.2, §5.4): ô gộp dọc (`DocElement.cell_spans`) được **lặp xuống từng hàng** mà nó phủ khi dựng `content` của chunk `PROCEDURE_STEP`, để bước 3–4 dưới một ô "Trách nhiệm" gộp vẫn có người phụ trách; offset và `row_spans` không đổi. Không có `cell_spans` thì không đoán. Test: fixture bảng có ô gộp (V2-19) cho `content` đúng ở từng hàng. *Xong 2026-10-26: `chunk/procedure_table.py`; test ô gộp dọc lặp xuống từng hàng và không đoán khi `cell_spans = None`.*
- [x] Chunk mang đường dẫn tiêu đề (tên tài liệu › mục › bước) trong nội dung được embed và index BM25. Sửa 2026-10-21 (TECH-V2-ai-service §5.4): chunker nhận `title` và `doc_code` (tùy chọn) làm tham số; `index_text` = `"{title} [{doc_code}] › …"` khi có mã, `"{title} › …"` khi không; không đưa lần ban hành hay ngày hiệu lực vào `index_text`. Test cả hai dạng. *Xong 2026-10-26: `index_prefix`, test cả hai dạng.*
- [x] Đếm token bằng tokenizer của model embedding qua `docproc.tokens.Tokenizer` truyền vào chunker; triển khai `HFTokenizer` (nạp `AutoTokenizer` theo `model`/`revision` của embedding đang hoạt động, không nạp model embedding) để `V2-09` và `eval/` dùng lại (TECH-V2-ai-service §1.1). Chunker không import `providers`. Chunk không vượt giới hạn của model; gộp section quá nhỏ cùng cha; không cắt giữa ký tự. *Xong 2026-11-01: `docproc/tokens.py` có `Tokenizer`, `HFTokenizer` (tham số `local_files_only`); extra riêng `tokenizer = ["transformers>=4.40"]` trong `pyproject.toml`. Test `test_real_embedding_tokenizer_keeps_chunks_within_limit` chạy với tokenizer thật `BAAI/bge-m3` (revision `5617a9f6…`, cache HF cục bộ, chạy offline, transformers 5.20.2): mọi `index_text` ≤ `max_tokens` và `token_count` khớp số đếm của tokenizer; test tự bỏ qua nếu máy không có cache.*
- [x] Văn xuôi không chuẩn: chia theo đoạn/câu, không cắt cứng theo số token. *Xong 2026-10-26.*
- [x] Chunk làm việc trên `StructuredDocument` đã làm sạch và mang `char_start/char_end` trên Markdown chuẩn của V2-20 (owner chốt 2026-10-21): chunk thường là chuỗi con đúng của `markdown` tại offset đó; chunk `PROCEDURE_STEP` lấy offset từ `row_spans[i]` và trang từ `row_pages[i]` của hàng nguồn; chunk bảng cắt theo hàng lấy offset từ hàng đầu tới hàng cuối của phần đó; `page_start ≤ page_end` và khớp trang của các phần tử nguồn; chunk phủ bảng nhiều trang có `page_end > page_start`. Kiểm bằng property test trên fixture và corpus V2-19. *Xong một phần 2026-10-26: property test trên fixture synthetic và PDF thật. Đo trên corpus V2-19 2026-11-03 (mục bên dưới): 591 chunk / 21 file, 0 vi phạm mọi bất biến; nhưng bất biến "bảng nhiều trang có `page_end > page_start`" không kiểm được trên corpus vì extractor không nối bảng nào qua trang (0 bảng nhiều trang, lỗi V2-20 đã ghi). Giữ mở chờ owner: chấp nhận kiểm bảng nhiều trang chỉ bằng fixture, hoặc chờ sửa nối bảng rồi đo lại. Đo lại sau sửa nối bảng 2026-11-04 (mục "Nối bảng nhiều trang và đo lại 2026-11-04"): 7 bảng nhiều trang, bất biến `multi_page_table` kiểm 3 chunk, 0 vi phạm mọi bất biến trên 564 chunk.*

## 3. Hướng dẫn
- Thay `services/ingestion-service/src/services/{standardizer,chunker}.py`; không port nguyên trạng.
- Kích thước chunk khớp cấu hình eval V2-07 để kết quả RQ áp dụng được.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Các ca trong AUDIT §2.3 (tiêu đề chỉ là số, path cộng dồn, "Điều 5" giữa câu, `1. MỤC ĐÍCH`, `5.1`); bảng quy trình; ký tự tiếng Việt ở mép chunk | `uv run pytest tests/unit` |
| Eval | Heading và bảng trên corpus V2-19 | theo V2-19 |

### Ghi chú triển khai 2026-10-26
Code: `services/ai-service/src/sopilot_ai/docproc/chunk/` (`chunk_document(rendered, tokenizer, title=, doc_code=)`; 0 chunk thì `EMPTY_CONTENT`). Mặc định `ChunkConfig` 384/512/64 theo `models.yaml`. Heading phẳng của Docling (cấp 1 cho mọi heading) được dựng lại từ đánh số khi tài liệu không báo phân cấp; mục `2. Procedure` mà Docling trả như list item được coi là heading khi không có list item kề bên. Tiền tố tiêu đề dài hơn nửa `max_tokens` bị rút gọn trong `index_text` (bỏ tổ tiên trước), `section_path` vẫn đầy đủ. Chưa đo heading/bảng trên corpus V2-19 (xem V2-19), chưa chạy với tokenizer của model embedding thật. Giữ `review`.

### Đo trên corpus V2-19 2026-11-03
Chạy (từ gốc repo, ai-service venv): `HF_HUB_OFFLINE=1 services/ai-service/.venv/Scripts/python.exe eval/check_chunks_corpus.py --structured eval/results/extraction-clean/structured --out eval/results/chunk-invariants/report.json`. Tái dùng `StructuredDocument` đã trích ở lượt đo V2-21 (`predict_extraction.py --clean`), không chạy Docling lại. Quy trình: `clean_document` → `render` → `chunk_document` với tokenizer thật `BAAI/bge-m3@5617a9f6…` (cache HF cục bộ), `ChunkConfig` mặc định 384/512/64, `title` = `doc_id`, `doc_code` = metadata đã trích. Bất biến cài thuần trong `eval/sopilot_eval/chunk_invariants.py` (test `eval/tests/test_chunk_invariants.py`), không thêm test Docling nặng vào `tests/unit` của ai-service.

**Bất biến** (định nghĩa đầy đủ trong docstring): `offsets` (0 ≤ start < end ≤ len); `substring` (`TEXT` = đúng lát cắt Markdown; `TABLE` = lát cắt, hoặc phần cắt theo hàng: offset từ đầu hàng đầu tới cuối hàng cuối của một bảng, nội dung = tiêu đề cột lặp + đúng lát cắt đó, hoặc mảnh của một hàng quá dài); `procedure_row` (`PROCEDURE_STEP` có offset = `row_spans[i]` và `page_start = page_end = row_pages[i]`); `page_order`; `page_source` (trang chunk = min/max trang của các hàng bảng hoặc phần tử nguồn mà chunk phủ); `multi_page_table` (chunk phủ hàng bảng trên nhiều trang có `page_end > page_start`); `token_budget` (≤ 512).

| | Kết quả |
|---|---|
| File / chunk | 21 file (19 PDF, 2 MD) / 591 chunk: 543 `TEXT`, 42 `PROCEDURE_STEP`, 6 `TABLE` |
| Số lần kiểm | offsets 591, substring 549, procedure_row 42, page_order 591, page_source 549, token_budget 591, multi_page_table **0** |
| Vi phạm | **0** ở mọi bất biến (không có ví dụ vi phạm); không file nào `EMPTY_CONTENT` |
| Bảng đã render | 122, trong đó **0** bảng nhiều trang (`row_pages` > 1 trang) |

**Lỗi lộ ra (V2-20, chỉ báo cáo):** nhãn gold có 34 mảnh bảng `page_fragment` (bảng kéo qua trang), nhưng `extract/pdf.py` `_merge_tables` không nối cặp nào. Trên 64 cặp "bảng cuối trang p / bảng đầu trang p+1" (`table_continuation_blockers` trong report): 24 vì trang p kết thúc bằng phần tử không phải bảng, 19 vì khác số cột, 15 vì có phần tử nội dung trước bảng ở trang p+1, 6 vì hàng tiêu đề không lặp, 0 đủ điều kiện. Nguyên nhân chính ở ISO VI: header trang là một **bảng nội dung** ở đầu mỗi trang (ví dụ `nb-qt01` tr. 5→6: bảng quy trình 5 cột kéo trang, trang 6 mở đầu bằng bảng header 4 cột "SỞ | QUY TRÌNH | Mã hiệu: | QT-01"), mà việc nối chạy lúc trích xuất, trước làm sạch; ngoài ra mảnh nối tiếp thường không lặp hàng tiêu đề (quy ước nhãn 3). Đề xuất: nối bảng sau bước đánh khung (bỏ qua phần tử `header/footer/boilerplate` giữa hai mảnh) và cho phép nối khi cùng số cột mà không lặp tiêu đề; sau đó đo lại bất biến `multi_page_table` trên corpus.

**Giới hạn:** bất biến là điều kiện cần về offset/trang, không đo chất lượng ranh giới chunk; `page_source` so với trang mà extractor gán, không so với nhãn gold; corpus chỉ có 6 chunk `TABLE` và 42 `PROCEDURE_STEP`; nhãn do agent duyệt theo ủy quyền. Ngưỡng (nếu có) chờ owner.

### Nối bảng nhiều trang và đo lại 2026-11-04
Sửa lỗi nối bảng ở mục trên. `extract/pdf.py` `_merge_tables` giữ nguyên điều kiện (bảng kế tiếp ngay sau, cùng số cột, lặp hàng tiêu đề), chỉ gọi hàm chung trong mới `docproc/tables.py`; nên `structured/*.json` cũ vẫn đúng và không chạy lại Docling. Bước mới `join_continued_tables` chạy trong `clean_document` **sau** `mark_repeated_header_footer` (header dạng bảng đã là khung) và trước `mark_frame_blocks`: hai bảng thân được nối khi giữa chúng chỉ có phần tử `header/footer/boilerplate`/`page_break`, bảng sau ở trang `page_end + 1`, cùng số cột, và hoặc lặp hàng tiêu đề (bỏ hàng lặp) hoặc không có hàng tiêu đề (`header_rows = 0`, mảnh nối không lặp tiêu đề); bảng trang sau có tiêu đề khác là bảng mới. `row_pages`, `cell_spans`, `page_end` được cập nhật như ở extractor. Logic chunk/`PROCEDURE_STEP` không đổi. Test: `test_table_split_by_a_header_table_is_joined_after_cleaning_and_chunks_span_pages` (bảng quy trình 4 trang bị chia bởi bảng header, mỗi `PROCEDURE_STEP` đúng trang của hàng; bảng thường 2 trang có chunk `page_end > page_start`) và `test_next_page_table_with_its_own_header_is_not_joined` trong `tests/unit/test_clean_corpus_fixes.py`.

Chạy như mục trên (tokenizer thật `BAAI/bge-m3`, `eval/results/chunk-invariants/report.json` đã ghi đè), sau các sửa V2-21 cùng ngày:

| | Trước (2026-11-03) | Sau (2026-11-04) |
|---|---|---|
| Chunk | 591 (543 `TEXT`, 42 `PROCEDURE_STEP`, 6 `TABLE`) | 564 (500 `TEXT`, 54 `PROCEDURE_STEP`, 10 `TABLE`) |
| Bảng đã render / nhiều trang | 122 / **0** | 88 / **7** (`nb-qt01` 1, `nb-qt03` 2, `nb-qt04` 1, `tb-qt05` 3); 11 lần nối |
| Số lần kiểm `multi_page_table` | 0 | **3** |
| Số lần kiểm khác | offsets 591, substring 549, procedure_row 42, page_order 591, page_source 549, token_budget 591 | offsets 564, substring 510, procedure_row 54, page_order 564, page_source 510, token_budget 564 |
| Vi phạm | 0 | **0** ở mọi bất biến |

Bảng giảm vì bảng header ISO nay là khung, chunk `TEXT` giảm vì header lặp không còn vào thân. Cặp "bảng cuối trang p / bảng đầu trang p+1" còn lại **sau** làm sạch: 32 (14 có phần tử thân trước bảng trang sau, 9 có phần tử thân sau bảng trang trước, 9 khác số cột; 0 vì tiêu đề không lặp). Phần lớn là bảng khác nhau thật (danh mục biểu mẫu sau bảng quy trình, biểu mẫu phụ lục); số còn lại do header trang không được nhận là khung (`nb-qt01` tr. 4→5, `tb-qt05` tr. 4→5, `nb-thanhtra06` tr. 3→4) hoặc Docling suy số cột khác nhau giữa hai mảnh (`nb-thanhtra06` 4 ↔ 5 cột): chưa sửa, cần căn cột theo vị trí thay vì số cột. Trường `table_continuation_blockers` của report vẫn tính trên phần tử **trước** làm sạch (điều kiện của extractor, 64 cặp, không đổi). Gold có 34 mảnh `page_fragment`; chưa chấm khớp từng cặp nối với nhãn. Ngưỡng (nếu có) chờ owner.

### Owner chốt ngưỡng và đóng ticket 2026-11-04
Owner chấp nhận khuyến nghị: `header_footer_ratio` = 0,4 (TECH §5.3 đã sửa cùng ngày). Ngưỡng nghiệm thu V2-21: **khung lọt ≤ 10%** và **xóa nhầm ≤ 2%** trên corpus V2-19. Số đo hậu sửa: khung lọt **8,1%** (đạt), xóa nhầm **1,6%** (đạt; toàn bộ là bất đồng nhãn với bảng lịch sử sửa đổi, 0 lỗi thật). Giới hạn đã biết: tiếng Việt khung lọt **13,8%** (vượt 10%), do Docling cắt header khác nhau giữa các trang; theo dõi ở V2-07. Kiểm mẫu 176 khối bị xóa mà nhãn không xác nhận: các loại header chạy, số trang, footer, danh sách "Nơi nhận", chữ ký, số hiệu văn bản, bảng lịch sử sửa đổi; mẫu ngẫu nhiên không thấy nội dung thật. Ngưỡng 10%/2% là đề xuất của trợ lý, chưa suy ra từ tác động lên retrieval. Bằng chứng: `validate-build.ps1 -Scope ai` xanh, 104 test ai-service và 70 test eval pass (2026-11-04). Đóng `done`.
