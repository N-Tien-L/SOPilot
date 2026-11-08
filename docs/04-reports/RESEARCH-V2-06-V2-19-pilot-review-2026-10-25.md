---
id: RESEARCH-V2-06-V2-19-PILOT-REVIEW-2026-10-25
title: "Pilot dữ liệu thật V2-06/V2-19 và gói nhãn chờ owner duyệt"
status: final
created: 2026-10-25
updated: 2026-10-25
type: research
scope: tests
author: "Owner"
refs:
  - docs/03-plans/tickets/V2-06-multilingual-eval-dataset.md
  - docs/03-plans/tickets/V2-19-sop-extraction-corpus.md
  - docs/04-reports/AUDIT-v2-readiness-preparation-2026-10-24.md
---

# Kết quả đợt pilot

Owner yêu cầu thực hiện đề xuất: ưu tiên tập PDF nhỏ V2-19, đồng thời chuẩn bị pilot V2-06. Đợt này đã có dữ liệu thật và phiếu nhãn cụ thể để duyệt. `final` là hoàn tất bản bàn giao đợt pilot, **không phải nghiệm thu hai ticket/corpus hoặc kết quả nghiên cứu**. Giữ cả hai ticket `in-progress` và giữ nguyên counters/DAG PLAN.

Tiếp tục checkout `chore/tests-v2-readiness` đang có thay đổi chuẩn bị từ trước; không stash/reset, chuyển branch, commit hoặc push. Không sửa service V1/V2, DB, API, event hoặc RBAC. Các thay đổi PRD/TECH/harness/hạ tầng đã có được giữ nguyên. Scope build tập trung `eval/`; không có scope `validate-build.ps1` cho eval nên dùng pytest, ruff và compileall trực tiếp.

## 1. V2-19: PDF gốc đã lấy được

| Nhóm | File | Trang | Kết quả pypdf không OCR |
|---|---:|---:|---|
| ISO VI: Sở Xây dựng Ninh Bình QT-01/02/03/04 | 4 | 44 | Có chữ; mỗi PDF có trang đầu không có chữ |
| ISO VI: Cảng vụ Thái Bình QT.01/03/05 | 3 | 34 | Mọi trang có chữ |
| ISO VI: Thanh tra Ninh Bình QT 06/TTr | 1 | 17 | Mọi trang có chữ |
| SOP EPA EN: Soil Sampling / Field Sampling QC | 2 | 53 | Mọi trang có chữ |
| NĐ 30 ký số | 1 | 76 | Không trích được ký tự ở cả 76 trang; ảnh trang 1 là scan |
| **Tổng** | **11** | **224** | Chưa có số đo Docling |

Sources và hash ở [SOURCES](../../datasets/extraction/SOURCES.md), [acquisition lock](../../datasets/extraction/pilot/acquisition.lock.json). Byte PDF giữ nguyên; URL/URL cuối, MIME, thời điểm UTC, SHA-256 và probe từng trang được ghi lại. File PDF và ảnh trang ở vùng `local/` bị gitignore vì chưa xác minh quyền tái phân phối từng tài liệu; không mặc định tài liệu government là CC/public domain. Không có OCR hoặc PDF tạo từ HTML.

Đã render các trang chọn bằng Poppler và đọc ảnh để soạn nhãn nháp: heading, vị trí bảng/fragment, ô gộp ngang và bảng lồng QT-01, metadata, khung và một số tham chiếu. **10 record là nhãn một phần (`selected_pages`), 1 record chỉ là kỳ vọng từ chối `NO_TEXT_LAYER`.** Header table chưa xác nhận được ghi `pending_fields`, không điền tên cột suy đoán. Ngày ban hành SOP VI không bị gán thành ngày hiệu lực; revision EPA QC lấy từ nội dung R7, không từ filename r5.

Tập ứng viên tối thiểu: nb-qt01/02/03/04, tb-qt01/03, epa-soil/qc, nd30. Đủ file để bắt đầu chuẩn bị nhưng chưa đủ nhãn owner duyệt theo gate V2-19. Không coi nhãn fragment là gold toàn tài liệu. Scorer đã chặn việc chấm toàn tài liệu bằng nhãn một phần và không cho ca từ chối bị cộng vào điểm heading/table.

Mở [phiếu duyệt PDF](../../datasets/extraction/pilot/REVIEW.md). Phần tiếp theo sau pilot: hoàn thiện nhãn các trang còn lại/biểu diễn bảng kéo trang, giải quyết quyền dùng, mở rộng 20–50 file/5 họ, PDF 1–2 trang và thêm scan/MD. Chưa đo thời gian/RAM hoặc chất lượng Docling; không thay `V2-20` bằng phép đo pypdf.

## 2. V2-06: pilot song ngữ trên nguồn thật

- 4 tài liệu: 2 SOP PDF VI (`nb-qt02`, `nb-qt03`) và 2 trang GitLab EN (Buddies, Meetings).
- GitLab pin chung commit `4684d72f27f3401d3ae72a26d72ae46eaeaab929`; đã tải raw và trang bằng chứng license ở cùng commit. Text/chuyển thể GitLab giữ attribution và CC-BY-SA-4.0; không thay giấy phép code repo.
- 12 ý / 24 câu do Codex soạn: 12 VI, 12 EN; 20 answerable, 4 câu âm; 12 cross-lingual cả VI→EN và EN→VI; 16 span với AND evidence; phủ 7 `query_types`.
- 24 câu giữ lại ở giai đoạn tạo pilot, 0 câu bị loại, **0 câu người duyệt**. Mọi câu `draft`, toàn bộ **dev**, không có test hoặc freeze. Không đếm bản dịch là một ý độc lập khác.
- `expected` được suy ra từ `evidence_sets`, không duy trì song song thủ công. Quotes/offset/hash trỏ đúng canonical; page-map dùng số trang vật lý.
- Câu âm có audit nháp agent theo toàn bộ bốn tài liệu và từ khóa ứng viên; owner vẫn phải đọc nội dung để xác nhận. `review.jsonl` trống, không có reviewer giả. Khi mở rộng corpus phải audit lại câu âm.

Mở [phiếu duyệt 12 ý/24 câu](../../eval/datasets/sop-pilot/REVIEW.md): từng ý có VI/EN, hai đáp án nháp, bằng chứng, offset và nguồn/trang. [README](../../eval/datasets/sop-pilot/README.md) ghi cách tái lập; [SOURCES](../../eval/datasets/sop-pilot/SOURCES.md) ghi attribution và giới hạn phân phối.

Giữ phạm vi VI/EN của ticket hiện hành; thiết kế GitLab corpus EN trong handoff cũ không tự ghi đè yêu cầu đó. Pilot là bước xác định công review, chưa chốt quy mô tối thiểu cuối (~100 theo ticket hay quy mô khác được owner duyệt). Canonical VI hiện chỉ là inventory pypdf 6.21.0 chuẩn hóa NFC/whitespace, chưa phải Markdown cấu trúc Docling. Trước RQ chính thức cần rebase corpus/spans bằng docproc V2-20/V2-22, duyệt/version lại; scorer span-aware/truncation vẫn thuộc các việc còn lại của chuỗi eval.

## 3. Công cụ và kiểm tra

Hai module mới: `eval/sopilot_eval/acquire.py` (download có pin/hash, chặn path thoát dataset/HTML giả PDF, probe không OCR, offline verification) và `prepare_pilot.py` (section allowlist, canonical/page map, span và câu hỏi từ seed, không ghi đè artifact đã sửa). Thêm 11 test hồi quy ở `test_corpus_acquisition.py`; sửa guard trong extraction scorer.

| Kiểm tra | Bằng chứng |
|---|---|
| `eval/.venv/Scripts/python.exe -m pytest -q eval/tests --basetemp=eval/.cache/pytest-corpus-final` | **37 passed** (11 test mới + 26 có sẵn) |
| Từ `eval/`: ruff trên acquire/prepare_pilot/extraction và test_corpus_acquisition | Pass |
| compileall trên 4 file code/test đợt này | Pass |
| acquire cả hai `sources.json` với `--offline` | 11 PDF + 3 raw GitLab khớp SHA-256, không gọi mạng |
| prepare_pilot chạy lại trên cùng lock/seed | Pass; 4 documents, 16 spans, 24 questions; dev 24/test 0; không thay artifact |
| Validator retrieval / extraction | Pass cấu trúc: 24 câu / 11 annotation record |
| Hai validator `--require-reviewed` | Exit 1 đúng kỳ vọng: retrieval draft; extraction labels một phần |
| `sopilot_eval.plan_check` | 33 ticket, 75 cạnh, counters/DAG/closure khớp |
| `git diff --check` | Pass; `git check-ignore` xác nhận PDF, raw cache và canonical VI không được đưa vào git |
| `scripts/pre-commit-check.ps1` | Pass; tắt auto-load env file, env file rỗng trong repo, giá trị giả sinh ngẫu nhiên cho các biến Compose bắt buộc; không đọc `.env`, không chạy stack |

Ruff khi chạy toàn bộ `eval/tests` từ thư mục `eval/` còn báo import order ở hai file có sẵn `test_harness_regressions.py` và `test_review_regressions.py`; không sửa phần ngoài đợt này. Lint các file thay đổi đợt này pass. Pre-commit không tự chạy tests cho eval và bỏ qua untracked; vì vậy đã chạy pytest/lint trực tiếp. Không chạy full stack, LLM/embedding API, Docling hoặc RQ.

## 4. Điểm cần owner duyệt và việc tiếp tục

1. Đọc 12 ý trong phiếu V2-06; xác nhận/sửa/loại từng ý và bản dịch, đặc biệt câu âm và các điều kiện thời gian. Đây là cơ sở chốt quy mô mở rộng và nhóm split, không phải ký nhận test cuối.
2. Đối chiếu trang được chọn trong phiếu V2-19, xác nhận cách biểu diễn heading/bảng lồng/ô gộp và metadata. Phần duyệt chỉ áp dụng cho trang đã xem; nhãn toàn tài liệu còn phải hoàn thiện trước nghiệm thu corpus.
3. Sau phản hồi, ghi người/ngày/phiên bản review thật; hoàn thiện nhãn PDF, mở rộng corpus và chuẩn bị baseline Docling V2-20. Không đổi `review_status` hoặc `done` chỉ để công cụ chạy xanh.

Tài liệu tiến độ đã cập nhật: V2-06, V2-19 và PLAN-V2; hướng dẫn dataset/eval đã thêm đường dẫn pilot. Không có thay đổi contract sản phẩm nên không đổi `.agent/context/`.
