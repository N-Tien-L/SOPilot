---
id: V2-19
title: "Corpus SOP thật (VI, EN; PDF/MD) và bộ đo chất lượng trích xuất"
type: test
status: in-progress
created: 2026-10-19
updated: 2026-10-25
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-20, V2-28]
branch: "test/tests-extraction-corpus"
assignee: pair
---

# TICKET V2-19: Corpus và bộ đo trích xuất SOP

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 1. Corpus eval của V2-06 chỉ có Markdown tiếng Anh nên không đo được trích xuất PDF có lớp chữ tiếng Việt. Cần một bộ nhỏ tài liệu thật, có nhãn cấu trúc, làm thước đo cho V2-20 đến V2-22.

Bộ này đo **trích xuất và cấu trúc**, không đo truy xuất; không trộn vào RQ1–RQ5.

Sửa 2026-10-21 ([AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md)): TXT bỏ khỏi MVP nên không thuộc corpus đo chất lượng; một **tập con tối thiểu** cần sẵn sàng trước, vì bước xác nhận Docling ở `V2-20` (ADR-008, timebox 2 ngày) dùng nó.

## 2. Tiêu chí Hoàn thành
- [ ] 20–50 file, phủ ít nhất 5 họ: quy trình ISO 9001, văn bản hành chính (NĐ 30/2020, Chương/Điều/Khoản), SOP GMP/EPA, wiki/Markdown, tài liệu không theo chuẩn. Có PDF có lớp chữ và MD; thêm 2–3 PDF scan để kiểm tra từ chối và ít nhất 1 PDF có lớp chữ nhưng một số trang chỉ là ảnh (cảnh báo `PAGES_WITHOUT_TEXT`). DOCX (hoãn) và TXT (bỏ 2026-10-21) không thuộc corpus đo chất lượng; chỉ cần fixture kiểm tra từ chối upload trong V2-12. Tài liệu nguồn TXT trong HANDOFF-V2-19 (ví dụ curl RELEASE-NOTES) không cần thu thập.
- [ ] Tập con tối thiểu cho bước xác nhận Docling của `V2-20`, có nhãn heading/bảng đã được owner duyệt: ≥ 6 PDF tiếng Việt (ưu tiên 4 PDF ISO nhóm A của HANDOFF-V2-19 có bảng quy trình), 2 PDF tiếng Anh (EPA), 1 PDF scan. Chưa đủ thì V2-20 dùng fixture synthetic theo quy tắc của AUDIT-markdown-normalization §6.3.
- [ ] Mỗi file ghi nguồn, giấy phép và nhãn họ tài liệu trong `datasets/extraction/SOURCES.md`. File không được tái phân phối thì commit manifest + script tải, không commit file. Tài liệu nội bộ phải được xóa thông tin nhạy cảm trước khi đưa vào.
- [ ] Nhãn vàng cho mỗi file: danh sách heading theo thứ tự (kèm cấp), các bảng (vị trí, tiêu đề cột), các khối khung cần bỏ (header/footer, quốc hiệu, chữ ký, bảng phê duyệt, bảng sửa đổi), metadata kỳ vọng (mã số, lần ban hành, ngày hiệu lực) nếu có.
- [ ] Script chấm điểm một bộ trích xuất bất kỳ: độ khớp heading (precision/recall theo thứ tự và cấp), bảng đúng vị trí và số hàng/cột, tỷ lệ khung lọt vào nội dung, metadata đúng, ký tự lỗi (`U+FFFD`, `(cid:`), thời gian xử lý và RAM đỉnh mỗi trang. Báo cáo tách theo họ tài liệu và ngôn ngữ, không chỉ trung bình toàn corpus.
- [ ] Sửa 2026-10-21 (audit đầu-cuối theo loại query, owner chốt D6/P0-3/P0-4): nhãn vàng thêm (a) các bảng có **ô gộp** (vị trí ô, rowspan/colspan) để chấm `cell_spans` của `V2-20` và chunk `PROCEDURE_STEP` của `V2-22`; (b) ít nhất 2 PDF **1–2 trang** (kiểm luật header/footer không xóa nhầm tiêu đề và đoạn cuối); (c) vị trí các tham chiếu chéo trong cùng tài liệu ("theo mục 5.3", "Điều 12") và giữa tài liệu ("theo QT-05").
- [ ] Sửa 2026-10-21 (D6): script đếm tần suất tham chiếu chéo (trong cùng tài liệu và giữa tài liệu) trên cả corpus, số liệu vào báo cáo của `V2-19`. Đây là căn cứ để xét lại "Không làm" của TECH-V2-ai-service §6.4a; không quyết định ngưỡng trước khi có số.
- [ ] Owner duyệt nhãn của từng file.

## 3. Hướng dẫn
- **File:** `datasets/extraction/` (CREATE), script chấm trong `eval/` cạnh harness V2-05.
- Owner cung cấp hoặc chọn tài liệu; agent chuẩn bị định dạng nhãn và script.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Script chấm trên 2 file mẫu có nhãn tay | `uv run pytest` trong `eval/` |

### Chuẩn bị 2026-10-24 (chưa nghiệm thu dữ liệu)
Đã có manifest/nhãn draft và hai fixture MD synthetic ở `datasets/extraction/example/`; validator/scorer `eval/sopilot_eval/extraction.py`, contract ở `datasets/extraction/README.md`. Chấm heading có thứ tự/cấp/trang, bảng, ô gộp, khung, metadata, lỗi ký tự và đếm tham chiếu; báo riêng theo họ/ngôn ngữ. Predictions là ví dụ viết tay, thời gian/RAM chưa đo. Chưa có 20–50 tài liệu thật, tập con PDF cho Docling hoặc nhãn owner duyệt; các tiêu chí corpus vẫn chưa hoàn thành.

### Acquisition pilot 2026-10-25 (chưa nghiệm thu corpus)
Đã tải và khóa SHA-256 **11 PDF thật / 224 trang** tại `datasets/extraction/pilot/`: 8 SOP VI có lớp chữ, 2 SOP EPA EN, 1 PDF VI không có text theo pypdf. Bốn SOP Ninh Bình có trang đầu không chữ (`mixed`); NĐ 30 có 76/76 trang không trích được chữ và ảnh trang 1 xác nhận trang scan. Không OCR. Có đủ file ứng viên cho tập con 6 VI + 2 EN + 1 scan, nhưng **chưa đủ gate nhãn owner duyệt** để nghiệm thu.

Nhãn nháp heading/bảng/ô gộp/khung/metadata/tham chiếu mới phủ **các trang được chọn**, không phủ toàn bộ tài liệu. QT-01 trang 4 có bảng lồng/ô gộp ngang; cần duyệt cách biểu diễn bảng và phần kéo qua trang. Scorer chặn tính điểm toàn tài liệu với nhãn một phần hoặc gộp fixture từ chối vào heading/table. Chưa chạy Docling hoặc đo latency/RAM. Chưa đủ 20–50 file/5 họ, PDF ngắn và số scan yêu cầu; không đánh dấu AC corpus hoàn thành.

File PDF/ảnh chỉ local (gitignore), nguồn/quyền đang chờ xác minh từng file; commit manifest + script tải thay binary. Xem [SOURCES](../../../datasets/extraction/SOURCES.md), [README](../../../datasets/extraction/pilot/README.md), [phiếu duyệt](../../../datasets/extraction/pilot/REVIEW.md) và [HANDOFF pilot](../../04-reports/HANDOFF-V2-06-V2-19-pilot-review-2026-10-25.md). Giữ `in-progress`; owner chưa duyệt file/nhãn nào.
