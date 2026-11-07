---
id: V2-21
title: "ai-service: tách phần khung, trích metadata SOP và cảnh báo trích xuất"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-04
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-09, V2-16, V2-25, V2-28]
branch: "feat/ai-qa-boilerplate-metadata"
assignee: pair
---

# TICKET V2-21: Tách khung, giữ ruột

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 4 và 8, PRD-V2 FR-08. Phần khung (header/footer lặp, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt, bảng sửa đổi) đang bị embed như nội dung. Bỏ chúng khỏi index nhưng giữ thông tin hữu ích làm metadata.

## 2. Tiêu chí Hoàn thành
- [x] Phát hiện header/footer lặp qua các trang PDF (DOCX hoãn sau MVP theo FR-06); loại khỏi nội dung. Sửa 2026-10-21 (audit theo loại query, owner chốt P0-4, TECH-V2-ai-service §5.3): luật "≥ 60% số trang" chỉ áp dụng khi PDF có ít nhất `SOPILOT_HEADER_FOOTER_MIN_PAGES` trang (mặc định 3, chốt trên corpus V2-19) và phần tử `heading` đầu tiên không bao giờ bị đánh `header`; thêm fixture PDF 1 trang và 2 trang, chỉ số "nội dung bị xóa nhầm" phải bằng 0 trên chúng. *Xong 2026-10-26: `docproc/clean/boilerplate.py`, test `test_clean.py` (kể cả PDF 1–2 trang không mất nội dung, heading đầu không bị đánh `header`) và PDF thật `framed_procedure` trong `test_pdf.py`.*
- [x] Nhận diện khối quốc hiệu/tiêu ngữ, số/ký hiệu, nơi nhận, khối chữ ký, bảng Soạn thảo/Soát xét/Phê duyệt, bảng theo dõi sửa đổi; loại khỏi nội dung được chunk. *Xong 2026-10-26 (luật VI/EN, test synthetic).*
- [x] Trích metadata khi có: mã số, lần ban hành, ngày ban hành/hiệu lực, người phê duyệt. *Xong 2026-10-26: `clean/metadata.py` trả `docCode`, `revisionLabel`, `issueDate`, `effectiveDate`, `approvedBy`. Sửa phạm vi 2026-11-01 (owner): phần "lưu theo version tài liệu" (`extracted_meta`) chuyển sang `V2-09` vì bảng `rag` thuộc ticket đó; xem tiêu chí `extracted_documents` của V2-09.*
- [x] Khối đã loại có dạng `{kind, page, text}`; không xuất hiện trong Markdown chuẩn, chunk hay index (test trên fixture có header/footer lặp và bảng phê duyệt). *Xong 2026-10-26: `CleanResult.boilerplate` và test khối khung không vào Markdown. Sửa phạm vi 2026-11-01 (owner): cột `extracted_documents.boilerplate` do `V2-09` ghi (đã có trong tiêu chí của V2-09); màn FR-31 liệt kê khối đã loại thuộc phần giao diện (`V2-15`/`V2-31`), không thuộc ticket này.*
- [x] Cảnh báo theo TECH-V2-ai-service §5.3a (`PAGES_WITHOUT_TEXT`, `UNMAPPED_GLYPHS`, `NO_HEADINGS_DETECTED`, `BOILERPLATE_REMOVED`, `CONVERTER_WARNING` nếu thư viện có): mỗi mã có fixture sinh ra nó và fixture sạch không sinh ra nó; không có điểm tin cậy tổng hợp; cảnh báo không làm `FAILED`. *Xong 2026-10-26: `clean/warnings.py`; mỗi mã có fixture sinh ra và fixture sạch không sinh mã nào.*
- [x] Không xóa nội dung thật: trên corpus V2-19, tỷ lệ khung lọt vào nội dung và tỷ lệ nội dung bị xóa nhầm đều được báo cáo; owner chốt ngưỡng. *Phần báo cáo xong 2026-11-03 (mục "Đo trên corpus V2-19 2026-11-03" bên dưới): khung lọt 29,9 %, xóa nhầm 4,7 %. **Ngưỡng chờ owner**; với số hiện tại cả hai tỷ lệ còn cao ở họ ISO VI, xem các lỗi đã ghi. Sau sửa lỗi 2026-11-04 (mục "Sửa lỗi và đo lại 2026-11-04"): khung lọt 8,1 % (VI 13,8 %, EN 2,2 %), xóa nhầm 1,6 % (11/706, toàn bộ là bảng lịch sử sửa đổi EN mà nhãn ghi là nội dung; theo quy ước owner thì 0). **Ngưỡng vẫn chờ owner.***

## 3. Hướng dẫn
- Bước xử lý trên cấu trúc của V2-20, trước bước chunk của V2-22.
- Schema metadata theo TECH-V2; nếu thêm cột thì migration trong `infrastructure/db/migrations/` và cập nhật `.agent/context/database/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Header/footer lặp; khối quốc hiệu; bảng phê duyệt; trích mã số và lần ban hành | `uv run pytest tests/unit` |
| Eval | Chấm trên corpus V2-19 | theo V2-19 |

### Ghi chú triển khai 2026-10-26
Code: `services/ai-service/src/sopilot_ai/docproc/clean/` (`clean_document` đánh `role`, không xóa phần tử; `render` bỏ phần tử không phải nội dung). Cấu hình qua `CleanConfig` (`SOPILOT_HEADER_FOOTER_MIN_PAGES`=3, `SOPILOT_PAGE_MIN_CHARS`=20 là giá trị khởi đầu, chưa hiệu chỉnh trên corpus thật). Luật khung viết cho văn bản VI/EN và chỉ kiểm bằng fixture tự tạo; chưa chạy trên tài liệu thật. Giữ `review` vì còn ba tiêu chí chưa có bằng chứng ở trên.

### Đo trên corpus V2-19 2026-11-03
Chạy: `predict_extraction.py --clean` (một lần Docling cho mỗi file, ai-service venv, CPU, `HF_HUB_OFFLINE=1`) ghi `eval/results/extraction-clean/predictions.{raw,clean}.jsonl` và `structured/*.json`; chấm bằng `python -m sopilot_eval.cleaning` (từ `eval/`) ra `eval/results/extraction-clean/score.cleaning.json` (gitignored: chứa chữ tài liệu). Phạm vi: 21 file có chữ (19 PDF + 2 Markdown); 4 fixture từ chối (`nd30`, 3 bản scan) không chấm. Test đơn vị: `eval/tests/test_cleaning.py`.

**Định nghĩa** (chi tiết trong docstring `eval/sopilot_eval/cleaning.py`). "Có mặt" = chữ của nhãn, sau chuẩn hóa (NFC, casefold, gộp khoảng trắng, bỏ `|`, dấu `#` và dòng `---` của Markdown), xuất hiện trong Markdown **của đúng trang** mà nhãn ghi (Markdown: cả file), không dính chữ/số liền trước/sau.
- Khung lọt = số khối `furniture` gold còn có mặt sau làm sạch / tổng khối `furniture` gold.
- Xóa nhầm = số đơn vị nội dung gold (heading gold, tiêu đề cột không rỗng của bảng gold) có mặt trước làm sạch nhưng mất sau làm sạch / số đơn vị có mặt trước làm sạch. Đơn vị không có mặt ngay từ trước (lỗi trích xuất V2-20) không tính vào mẫu số.
- Kiểm khối đã loại: mỗi khối `boilerplate` đã loại là "xác nhận" khi nó và một khối `furniture` gold cùng trang chứa nhau; còn lại "chưa xác nhận", liệt kê để xem tay.

| Nhóm | Khung gold | Có mặt trước làm sạch | **Khung lọt** | Đơn vị nội dung có mặt | **Xóa nhầm** |
|---|---:|---:|---:|---:|---:|
| Tổng (21 file) | 827 | 343 (41,5 %) | **247 (29,9 %)** | 706 | **33 (4,7 %)** |
| lang=vi | 419 | 248 | 201 (48,0 %) | 437 | 22 (5,0 %) |
| lang=en | 408 | 95 | 46 (11,3 %) | 269 | 11 (4,1 %) |
| iso_9001 / vi (8) | 391 | 227 | 188 (48,1 %) | 404 | 22 (5,4 %) |
| administrative / vi (2) | 12 | 9 | 6 (50,0 %) | 31 | 0 |
| non_standard / vi (3) | 16 | 12 | 7 (43,8 %) | 2 | 0 |
| epa_sop / en (3) | 276 | 0 | 0 (0 %) | 155 | 7 (4,5 %) |
| fda_sop / en (1) | 36 | 27 | 3 (8,3 %) | 32 | 4 (12,5 %) |
| gmp_sop / en (2) | 88 | 64 | 39 (44,3 %) | 53 | 0 |
| wiki_markdown / en (2) | 8 | 4 | 4 (50,0 %) | 29 | 0 |

Ghi chú số: "trước làm sạch" đã là sau lớp furniture của Docling (`page_header`/`page_footer` không render), nên EPA lọt 0 % là nhờ Docling, không nhờ `clean_document`. Chỉ số cũ của scorer (khớp chính xác trên cả tài liệu, `score_document`) cho khung lọt 31,7 %. Loại 508 khối: 438 xác nhận, 70 chưa xác nhận (6 271 ký tự, trong đó 4 896 là ba bảng lịch sử sửa đổi EPA).

**Xóa nhầm, từng trường hợp (33 đơn vị, 7 bảng):**
- Thật sự xóa nhầm (VI, 22 đơn vị, 3 bảng nội dung): `nb-qt01` tr. 11 bảng danh mục tài liệu (STT, Tên tài liệu, Mã số, Lần ban hành, Ngày ban hành, 1–6, Nơi nhận, Ngày nhận, Người nhận) và tr. 13 bảng tài liệu bên ngoài (STT, Tên tài liệu, Mã số/ký hiệu, Nơi ban hành, Ngày tháng năm ban hành, Nơi lưu) bị đánh `revision_table`; `tb-qt01` tr. 5 bảng phân công theo loại tài liệu (TT, Loại tài liệu, Biên soạn, Soát xét, Phê duyệt) bị đánh `approval_table`.
- Xung đột nhãn và quy ước (EN, 11 đơn vị, 4 bảng): bảng "Revision History" (`epa-qc` tr. 23, `epa-sw` tr. 18, kèm heading "Revision History"; `epa-soil` tr. 28) và bảng lịch sử phiên bản `fda-qms-sop` tr. 9. Code loại chúng theo quy ước "bảng sửa đổi là khung" (README pilot, quy ước 2), còn nhãn gold ghi chúng là bảng/heading nội dung. **Owner quyết định** nhãn hay quy ước đúng; nếu quy ước đúng thì xóa nhầm EN = 0 và nhãn cần sửa (không sửa trong lượt đo này).

**Khung lọt, nguyên nhân chính** (danh sách đầy đủ `cases.leaked` trong file kết quả):
- ISO VI (188/247): header trang ("SỞ XÂY DỰNG", "Mã hiệu: QT-01", "Lần ban hành 01", "Ngày ban hành: …", tên quy trình) được Docling trả là **bảng** nội dung ở đầu trang; ví dụ `nb-qt01` tr. 3 `[["Mã hiệu:", "QT-01"], ["Lần ban hành", "01"], ["Ngày ban hành:", "05/11/2020"]]`. Nhiều nhất: `tb-qt05` 31, `nb-qt01` 28, `nb-thanhtra06` 28, `tb-qt03` 26.
- GMP EN: `nci-bdp-deviations` "SOP Number: 21301" (17 trang), "Revision: 07" (16); `nci-bdp-labeling` "SOP 12188 Rev. 05" (4).
- VI hành chính / không chuẩn: quốc hiệu–tiêu ngữ (`vn-qd1308`, `vn-cv10065`, `vn-tb425` tr. 1), "Nơi nhận:" (5 file), "KT. BỘ TRƯỞNG…" (`vn-tb425`).
- Markdown: chú thích HTML `<!-- overview -->`, `<!-- steps -->`, `<!-- body -->` (k8s).

**Khối loại chưa xác nhận** (70; không phải nội dung gold): số trang trần ("2", "3"… ở `vn-vbhn109`, `vn-qd1308`, `tb-qt03`, `vn-cv10065`, `vn-qd82`, `vn-tb425`), mã biểu mẫu chân trang `BM.QT.03.0x` (`tb-qt03` tr. 9–13), "SOP Title:" (`nci-bdp-deviations`, 17 trang), "Số: …" (`vn-qd1308`, `vn-cv10065`, `vn-qd82`; không có trong nhãn `furniture`), tên người ký (`vn-qd1308`, `vn-cv10065`), tiêu đề bảng sửa đổi (6), "Phê duyệt" chân trang `nb-qt02` tr. 10 (cần xem tay), cùng các bảng đã kể ở phần xóa nhầm.

**Lỗi docproc lộ ra (chỉ báo cáo, chưa sửa):**
1. `clean/boilerplate.py` `mark_repeated_header_footer` chỉ xét `paragraph/heading/list_item`, nên header trang dạng bảng (ISO VI) không bao giờ bị đánh `header`. Đề xuất: đưa bảng ở mép trang vào luật lặp (khóa lặp trên chữ bảng, che số), hoặc đánh khung bảng mà mọi hàng khớp `_DOC_NUMBER`/`_DOC_META_LINE`.
2. Cùng hàm: `_EDGE_ELEMENTS = 2`, mà header NCI dài 7 phần tử mỗi trang (tiêu đề, "SOP Title:", giá trị, "SOP Number:", "21301", "Revision:", "07"), nên chỉ "SOP Title:" bị loại. Đề xuất: cửa sổ mép theo vị trí (bbox) hoặc theo nhóm nhãn–giá trị, không theo số phần tử cố định.
3. `mark_frame_blocks`: Docling trả quốc hiệu–tiêu ngữ là `heading` (thường là heading đầu tiên), và luật bảo vệ `first_heading` chặn việc đánh khung; quốc hiệu nằm trong bảng (`vn-tb425`) bị bỏ qua vì luật bỏ qua bảng. `_mark_recipients` chỉ nhận `paragraph/list_item`, mà "Nơi nhận:" ra dạng `heading`. Đề xuất: heading đầu tiên khớp `_MOTTO` không được bảo vệ; luật nơi nhận nhận cả `heading`; xét ô bảng ở đầu trang 1.
4. `is_revision_table` khớp tiêu đề có "ban hành" + "ngày" và `is_approval_table` khớp "Biên soạn/Soát xét/Phê duyệt" ở **bất kỳ** trang nào, nên bảng nội dung có các cột đó bị loại (3 bảng VI ở trên). Đề xuất: yêu cầu thêm tín hiệu vị trí (trang đầu/cuối, ngay sau tiêu đề "theo dõi sửa đổi") hoặc cột đặc trưng ("nội dung sửa đổi", "lần sửa").
5. Markdown: chưa có luật cho chú thích HTML; đề xuất bỏ `<!-- … -->` khi trích MD.

**Giới hạn:** khớp chuỗi con nên heading lặp trong mục lục cùng trang che việc bị xóa; nhãn rất ngắn ("2/9") có thể khớp nhầm; đoạn văn không có nhãn gold nên xóa nhầm chỉ đo trên heading và tiêu đề cột; 81 đơn vị gold ISO không có mặt ngay từ trước làm sạch (lỗi trích xuất V2-20) nên không đo được; nhãn do agent duyệt theo ủy quyền, chưa được owner đọc lại hết. **Ngưỡng chờ owner.**

### Sửa lỗi và đo lại 2026-11-04
Sửa các lỗi 1–4 của mục trên (lỗi 5, chú thích HTML trong Markdown, chưa làm). Code: `docproc/clean/boilerplate.py`, `docproc/clean/metadata.py`, `docproc/clean/model.py`, `docproc/clean/__init__.py`, mới `docproc/tables.py` (nối bảng, xem V2-22). Luật theo cấu trúc, không theo tên file hay chuỗi riêng của corpus:
- Header/footer lặp: khóa lặp tính trên phần tử ở 10 phần tử đầu/cuối trang (che số, **giữ số mục đầu dòng** để "1.1 General" và "2.1 General" không thành một dòng lặp; dòng "Nhãn: giá trị" có thêm khóa theo nhãn). Khung của trang là **dải phần tử lặp liên tiếp từ mép trang vào**, dài bao nhiêu cũng được (header NCI 7 phần tử), dừng ở phần tử đầu tiên không lặp (dòng lặp giữa thân giữ nguyên). Bảng ≤ 6 hàng, ô ngắn là khung khi ≥ 60 % ô có chữ lặp (khóa theo ô và theo cặp ô kề nhau trong hàng, vì Docling cắt cùng header khác nhau giữa các trang), mọi hàng có chữ đều có ô lặp, ô không lặp ≤ 60 ký tự (bảng thân có tiêu đề cột lặp mỗi trang không đạt vì hàng dữ liệu).
- Ngưỡng lặp: `max(SOPILOT_HEADER_FOOTER_MIN_PAGES, header_footer_ratio × số trang)`, **`header_footer_ratio` đổi 0,6 → 0,4** (giá trị khởi đầu, chờ owner; TECH-V2-ai-service §5.3 còn ghi 60 %, chưa sửa). Lý do: SOP ISO có phụ lục biểu mẫu với khung riêng, nên header chính chỉ phủ 41–57 % số trang (`nb-thanhtra06` 7/17, `nb-qt01` 8/14); khóa nội dung lặp nhiều nhất ở mép trang trên corpus chiếm ≤ 20 % số trang. Với 0,6 và mọi sửa khác: khung lọt 19,8 % (ISO 39,1 %).
- Quốc hiệu–tiêu ngữ là heading đầu tiên vẫn bị đánh khung (luật bảo vệ heading đầu chỉ giữ tiêu đề); bảng ở đầu trang 1 chứa quốc hiệu (ô ngắn, ≤ 6 hàng) là khung; tiêu đề bảng sửa đổi ngay trước bảng sửa đổi cũng không được bảo vệ.
- "Nơi nhận:" dạng heading (phải có dấu hai chấm, để heading "Distribution" ở thân giữ nguyên); dòng mở chữ ký "KT./TM./TL./TUQ." dạng heading.
- Bảng phê duyệt cần thêm nhãn hàng/cột ký duyệt (Họ tên, Chữ ký, Chức vụ, Ngày, Name, Signature, Date…) hoặc là lưới ≤ 3 hàng không đánh số thứ tự; bảng sửa đổi cần **cột đầu** nêu lần sửa ("sửa đổi", "revision", "history", "change", "rev") cùng một cột ngày/nội dung; "ban hành" một mình không còn đủ (đó là sổ đăng ký tài liệu).
- Metadata đọc thêm các hàng của bảng header đã đánh khung ("Mã hiệu: QT-02").

Test mới (synthetic, không Docling): `services/ai-service/tests/unit/test_clean_corpus_fixes.py`, 8 test (mỗi lỗi ít nhất một). `run-tests.ps1 -Scope ai-service -Type unit`: 104 passed (96 cũ + 8); `validate-build.ps1 -Scope ai`: pass; `eval` `pytest tests`: 70 passed.

Đo lại: tái dùng `structured/*.json` (không chạy Docling: `extract/pdf.py` chỉ đổi cách gọi hàm nối bảng, hành vi trích xuất giữ nguyên), `predict_extraction.py --clean --reuse-structured` rồi `python -m sopilot_eval.cleaning`; kết quả ghi đè `eval/results/extraction-clean/{predictions.*.jsonl,score.cleaning.json}`.

| Nhóm | Khung lọt trước | **Khung lọt sau** | Xóa nhầm trước | **Xóa nhầm sau** |
|---|---:|---:|---:|---:|
| Tổng (21 file) | 247/827 (29,9 %) | **67 (8,1 %)** | 33/706 (4,7 %) | **11 (1,6 %)** |
| lang=vi | 201/419 (48,0 %) | 58 (13,8 %) | 22/437 | 0 |
| lang=en | 46/408 (11,3 %) | 9 (2,2 %) | 11/269 | 11 |
| iso_9001 / vi | 188/391 (48,1 %) | 56 (14,3 %) | 22/404 | 0 |
| administrative / vi | 6/12 | 2 | 0 | 0 |
| non_standard / vi | 7/16 | 0 | 0 | 0 |
| epa_sop / en | 0/276 | 0 | 7/155 | 7 |
| fda_sop / en | 3/36 | 3 | 4/32 | 4 |
| gmp_sop / en | 39/88 (44,3 %) | 2 (2,3 %) | 0 | 0 |
| wiki_markdown / en | 4/8 | 4 | 0 | 0 |

Chỉ số cũ khớp cả tài liệu: 31,7 % → 15,8 %. Khối đã loại 508 → 824 (xác nhận 438 → 648, chưa xác nhận 70 → 176, 8 239 ký tự). Đã xem tay các khối chưa xác nhận mới: đều là khung mà chuỗi khác nhãn gold (dòng header "Lần ban hành QT.01" do Docling đổi thứ tự chữ, tiêu đề SOP NCI lặp trong header mỗi trang, mục danh sách dưới "Nơi nhận:" mà nhãn chỉ ghi dòng nhãn, số trang, mã biểu mẫu `BM-xx` chân trang, "Title:" FDA); không thấy đoạn thân nào. Metadata cải thiện: `nb-qt01..04` có `docCode`/`revisionLabel`/`issueDate`, `nb-thanhtra06` và `tb-qt*` có `issueDate`, `fda-qms-sop` có `docCode`.

**Xóa nhầm còn lại (11, EN) đều là bất đồng nhãn, không phải lỗi code:** bảng "Revision History"/"History | Effective Date" `epa-qc` tr. 23 (heading + 2 tiêu đề cột), `epa-sw` tr. 18 (3), `epa-soil` tr. 28 (1), bảng lịch sử phiên bản `fda-qms-sop` tr. 9 (4). Theo quy ước owner, bảng theo dõi sửa đổi là khung; nhãn gold cần sửa (không sửa trong lượt này). Nếu tính theo quy ước: xóa nhầm thật = 0/706.

**Khung lọt còn lại (67):** chữ header bị Docling cắt khác nhau nên khóa lặp xuất hiện ở ít trang hơn ngưỡng (`nb-qt01` tr. 2/3/5 "SỞ XÂY DỰNG…", `tb-qt05` bảng header tr. 5/7/8/9 chỉ 2/6 ô lặp, `fda-qms-sop` tr. 4 header ra dạng dòng thay vì bảng); heading đầu tài liệu được giữ làm tiêu đề (`nb-thanhtra06`, `tb-qt01` tr. 1); quốc hiệu của biểu mẫu phụ lục ở trang ≠ 1 (`tb-qt03` tr. 9–12); "VĂN BẢN HỢP NHẤT" (`vn-vbhn109`); chú thích HTML Markdown (lỗi 5, chưa làm); một phần là khớp chuỗi con nhầm của scorer ("CẢNG VỤ HÀNG HẢI" có trong câu thân bài `tb-qt01`, `tb-qt03`). **Ngưỡng chờ owner.**

### Owner chốt ngưỡng và đóng ticket 2026-11-04
Owner chấp nhận khuyến nghị: `header_footer_ratio` = 0,4 (TECH §5.3 đã sửa cùng ngày). Ngưỡng nghiệm thu V2-21: **khung lọt ≤ 10%** và **xóa nhầm ≤ 2%** trên corpus V2-19. Số đo hậu sửa: khung lọt **8,1%** (đạt), xóa nhầm **1,6%** (đạt; toàn bộ là bất đồng nhãn với bảng lịch sử sửa đổi, 0 lỗi thật). Giới hạn đã biết: tiếng Việt khung lọt **13,8%** (vượt 10%), do Docling cắt header khác nhau giữa các trang; theo dõi ở V2-07. Kiểm mẫu 176 khối bị xóa mà nhãn không xác nhận: các loại header chạy, số trang, footer, danh sách "Nơi nhận", chữ ký, số hiệu văn bản, bảng lịch sử sửa đổi; mẫu ngẫu nhiên không thấy nội dung thật. Ngưỡng 10%/2% là đề xuất của trợ lý, chưa suy ra từ tác động lên retrieval. Bằng chứng: `validate-build.ps1 -Scope ai` xanh, 104 test ai-service và 70 test eval pass (2026-11-04). Đóng `done`.
