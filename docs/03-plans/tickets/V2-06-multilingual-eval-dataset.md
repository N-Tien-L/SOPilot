---
id: V2-06
title: "Corpus và bộ câu hỏi đa ngôn ngữ (VI, EN) có người duyệt"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-04
author: "Owner"
scope: tests
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-07, V2-09]
branch: "docs/tests-eval-dataset"
assignee: owner
---

# TICKET V2-06: Bộ dữ liệu eval đa ngôn ngữ

## 1. Bối cảnh & Mục tiêu
Điểm nghẽn lớn nhất của phần nghiên cứu. Cần corpus công khai bằng tiếng Việt và tiếng Anh, câu hỏi có nhãn tài liệu/trang kỳ vọng, nhãn ngôn ngữ, cờ cross-lingual và câu không trả lời được.

Theo nguyên tắc khả thi của PLAN: kích thước bộ dữ liệu do **khả năng duyệt của owner** quyết định, không đặt số lớn rồi bỏ dở. Chạy được một bộ nhỏ đã duyệt kỹ tốt hơn một bộ lớn chưa duyệt.

## 2. Tiêu chí Hoàn thành
- [x] Chốt kích thước tối thiểu khả thi với owner trước khi làm. *(Owner chốt 2026-11-01: ~100 câu theo đề xuất; canonical lấy từ docproc.)* Đề xuất ban đầu (điều chỉnh được): ~10 tài liệu mỗi ngôn ngữ; ~100 câu hỏi gồm ~35 VI, ~35 EN, ~15 cross-lingual (hỏi một ngôn ngữ, đáp án ở tài liệu ngôn ngữ kia), ~15 không trả lời được.
- [ ] Mỗi tài liệu ghi nguồn và giấy phép trong `datasets/<name>/SOURCES.md`; không đưa tài liệu không được phép tái phân phối vào repo (commit manifest + script tải).
- [ ] Mỗi câu có `lang`, `cross_lingual` (bool), `answerable`, `evidence_sets` (gold theo **span**, schema ở [RESEARCH-02](../../04-reports/RESEARCH-02-dataset-and-labeling.md) §5.1 và §8), `reference_answer`; `expected` ({doc, pages}) là trường suy ra từ `evidence_sets`, không nhập tay hai lần. Sửa 2026-10-21 (audit theo loại query): gold theo span là điều kiện của chỉ số "tỉ lệ gold span nằm trong context" ở `V2-10`.
- [ ] Sửa 2026-10-21 (owner chốt D7/P0-6): thêm `query_types`, danh sách nhãn (một câu có thể nhiều nhãn) trong tập `fact`, `procedure`, `condition_exception`, `number_deadline`, `responsibility`, `comparison`, `multi_passage`. Gán nhãn trên các ý đã có, không thêm câu. Báo cáo `V2-07` và `V2-10` tách số liệu theo nhãn này. **Phải xong trước khi đóng băng tập test** (trước `V2-07`).
- [ ] Câu hỏi đa dạng: tra cứu số liệu, quy trình nhiều bước, câu cần nhiều đoạn, câu diễn đạt khác từ khóa trong tài liệu.
- [ ] Nếu LLM soạn nháp: owner duyệt từng câu; báo cáo ghi số câu sinh, số bị loại.
- [ ] Chia tập: dev (chỉnh ngưỡng) và test (báo cáo cuối), không trộn.

## 3. Hướng dẫn
- **File:** `eval/datasets/<name>/corpus/`, `questions.jsonl`, `SOURCES.md`. Định dạng ở `eval/README.md`.
- Agent có thể gom nguồn công khai và soạn nháp; owner duyệt.

## 4. Kiểm thử
`uv run python -m sopilot_eval.run --dataset datasets/<name> --config configs/smoke.yaml` chạy hết không lỗi định dạng và báo cáo có bảng tách theo `lang`.

### Chuẩn bị 2026-10-24 (chưa nghiệm thu dữ liệu)
Đã có validator `eval/sopilot_eval/dataset.py`, schema/hướng dẫn `eval/datasets/README.md`, 5 câu nháp EN/VI trên corpus synthetic ở `eval/datasets/annotation-example/`. Kiểm offset/quote/hash, AND/OR evidence, nhãn query và rò rỉ dev/test. Đây chỉ là ví dụ công cụ; chưa tải corpus nghiên cứu, chưa chốt kích thước hoặc có nhãn owner duyệt. `--require-reviewed` phải thất bại với ví dụ draft. Không đánh dấu hoàn thành tiêu chí dữ liệu.

### Pilot nguồn thật 2026-10-25 (chờ owner duyệt)
Theo yêu cầu owner tiếp tục đề xuất trong chat: tạo `eval/datasets/sop-pilot/`, 4 tài liệu thật (2 SOP PDF VI từ V2-19, 2 trang GitLab EN cùng commit), 12 ý / 24 câu nháp do Codex soạn, 16 span. Có 20 câu answerable, 4 câu âm, 12 cross-lingual cả hai chiều; phủ 7 `query_types`. Toàn bộ là **dev/draft**, 0 câu người duyệt, 0 câu bị loại lúc tạo pilot; chưa tạo test hoặc freeze. Pilot 24 câu để đo công duyệt, không tự chốt kích thước tối thiểu cuối.

Giữ yêu cầu corpus VI/EN của ticket; handoff GitLab corpus chỉ EN là phương án cũ và không tự thay scope này. GitLab pin commit `4684d72f27f3401d3ae72a26d72ae46eaeaab929`, lưu attribution/CC-BY-SA-4.0. PDF/canonical VI chưa rõ quyền tái phân phối chỉ lưu local và có script tải + khóa hash. Canonical PDF hiện là inventory pypdf 6.21.0; phải rebase span/version theo docproc V2-20/V2-22 trước RQ chính thức. Câu âm cần audit lại khi corpus mở rộng.

Phiếu đọc câu hỏi/đáp án/bằng chứng: [REVIEW pilot](../../../eval/datasets/sop-pilot/REVIEW.md). Hướng dẫn tái lập: [README pilot](../../../eval/datasets/sop-pilot/README.md). `prepare_pilot` và validator pass; `--require-reviewed` vẫn phải thất bại. Giữ `in-progress`, các AC dữ liệu chưa nghiệm thu. Bằng chứng và giới hạn ở [HANDOFF pilot](../../04-reports/RESEARCH-V2-06-V2-19-pilot-review-2026-10-25.md).

### Owner duyệt pilot 2026-11-01 (chưa nghiệm thu ticket)
Owner duyệt cả 24 câu pilot bằng app local `eval/review_ui/server.py` (đối chiếu câu hỏi, đáp án, span với canonical và ảnh trang PDF): **24/24 `reviewed`**, 0 câu bị loại, 0 câu sửa nội dung/`query_types`/span, `reviewer_id=owner:tiên`. `review.jsonl` có 24 bản ghi khớp `label_version`/`corpus_version`; 4 câu âm có `unanswerable_audit` (owner đọc đủ 4 tài liệu pilot). `sopilot_eval.dataset --require-reviewed` chạy **xanh**. Thống kê soạn nháp: 24 câu sinh (Codex), 0 bị loại.

Đây là gate người duyệt của **pilot dev**, không phải nghiệm thu ticket: chưa chốt kích thước tối thiểu, corpus mới 4 tài liệu (2 VI, 2 EN), chưa có tập test/freeze, canonical VI vẫn là inventory pypdf phải rebase theo docproc trước RQ chính thức. Câu âm phải audit lại khi mở rộng corpus. Giữ `in-progress`.

### Bộ chính sop-main 2026-11-01 (chờ owner duyệt tập test)
Owner chốt quy mô ~100 câu và canonical từ docproc ai-service. Tạo [`eval/datasets/sop-main/`](../../../eval/datasets/sop-main/README.md): **23 tài liệu** (13 VI, 10 EN; 21 từ corpus V2-19 gồm ISO 9001 VN, văn bản Chính phủ, EPA, FDA, SOP GMP NCI, Kubernetes; 2 trang GitLab), canonical do `eval/build_canonical.py` chạy `extract → clean_document → render` (Docling 2.142.1, CPU). **105 câu**: dev 24 (pilot) + test 81 (mới), 125 span; 37 câu VI/VI, 38 EN/EN, 15 cross-lingual, 15 câu âm; đủ 7 `query_types`; một câu có hai bộ OR. Dev và test tách tài liệu, nhóm policy, span; validator cấu trúc xanh. Builder `sopilot_eval/prepare_main.py` (5 unit test) đọc `test.seed.json`, tìm offset theo quote, rebase span pilot.

Duyệt: 10 câu dev giữ review owner vì quote trùng từng byte sau rebase (`carried_from` trong `review.jsonl`); 14 câu dev về `draft` (10 câu GitLab đổi định dạng quote, 4 câu âm phải audit lại vì corpus mở rộng). **81 câu test do Claude soạn nháp, 0 câu bị loại ở bước soạn, chưa có người duyệt**; `--require-reviewed` đỏ. Duyệt bằng `eval/review_ui/server.py` (mặc định mở `sop-main`).

Giới hạn: canonical dựng từ docproc có thay đổi chưa commit (`docproc_dirty=true` trong manifest); Docling làm mất bảng phân công biên soạn/soát xét/phê duyệt của tb-qt01 trang 5 (lỗi V2-20, câu hỏi tránh đoạn này). Chưa freeze tập test; freeze sau khi owner duyệt xong, trước `V2-07`. Giữ `in-progress`.

### Duyệt toàn bộ sop-main 2026-11-03 (chờ owner nghiệm thu)
Owner giao Claude Opus 5.5 duyệt toàn bộ phần còn lại vì không đủ thời gian đọc; `review.jsonl` ghi `reviewer_id=owner:tiên` theo chỉ đạo của owner, còn `notes` ghi rõ nội dung do Opus thực hiện, **owner chưa tự đọc lại**. Quy trình: 7 agent Opus duyệt độc lập theo lô tài liệu (EPA, FDA/NCI, GitLab/k8s, ISO Ninh Bình, ISO Thái Bình, văn bản VN, câu âm), mỗi agent chỉ đọc vùng quanh span; 53/80 câu answerable bị yêu cầu sửa (chủ yếu span cắt giữa câu, số liệu và đáp án đúng), 0 câu bị loại; các sửa được chuyển thành patch có cấu trúc, kiểm quote nguyên văn duy nhất, áp bằng `V206Store`. Sau đó 2 agent Opus độc lập kiểm lại 80 mục (53 câu đã vá, 27 câu duyệt thẳng, 6 câu âm tự Grep lại): 6 câu fail (thiếu OR set epa-sw ở 2 câu, span cụt ở 4 câu) được vá và áp lại. Sửa nội dung: `epasoil-low-high-en` (đáp án: lọ 40 mL chỉ áp dụng khi lấy bằng syringe), `qd1308-data-audit` (viết lại thành mục tiêu 2030), `tt06-retention` (thêm ngữ cảnh QT 06/TTr Ninh Bình). `qd1308-proposer`: số hiệu đúng là `319/TTr-BCA-C12` (xem ảnh trang 1), canonical còn lỗi `BCAC12` của Docling (việc của V2-20).
Kết quả: 105 câu `reviewed` (dev 24, test 81; 15 câu âm có `unanswerable_audit`); `sopilot_eval.dataset --require-reviewed` xanh, 58 unit test pass. Giới hạn: tin cậy dựa trên Opus chứ không phải người; chưa freeze test; canonical dựng từ docproc có thay đổi chưa commit (`docproc_dirty=true`). Chuyển `review`; `done` cần owner nghiệm thu và freeze trước V2-07.

### Owner đóng ticket 2026-11-03
Owner chốt `done` dựa trên bằng chứng ở mục trước (gate `--require-reviewed` xanh, 58 unit test pass), chấp nhận duyệt bằng Opus thay vì tự đọc lại. Việc còn lại trước V2-07: freeze tập test (chưa làm) và rebase canonical khi docproc được commit.

### Freeze 2026-11-04
Theo chỉ đạo owner, Opus dựng lại canonical `sop-main` bằng docproc commit sạch `26d1ed1` (`docproc_dirty=false`) vào thư mục tạm, so từng span rồi mới áp. 17/23 tài liệu đổi chữ (docproc mới bỏ header lặp, khối "Nơi nhận"/quốc hiệu, trang chỉ có header; tb-qt01 có lại bảng phân công). Cả 218 span (144 span được dùng: 128 test, 16 dev) còn quote nguyên văn: 94 giữ offset, 124 dịch offset (3 quote lặp giữ đúng lần xuất hiện), **0 đổi/mất**, trang mọi span không đổi. Áp toàn bộ với `corpus_version=sop-main-2026-11-04-v2`; câu hỏi, đáp án, `evidence_sets`, `review_status` không đổi; `review.jsonl` chỉ đổi `corpus_version` và thêm `rebased_from`. Chi tiết: `eval/datasets/sop-main/rebase-report-2026-11-04.json` và mục "Freeze 2026-11-04" của [README](../../../eval/datasets/sop-main/README.md).

Freeze: `manifest.json` `frozen=true`, `frozen_by="owner:tiên (Opus thực hiện theo chỉ đạo)"`, `frozen_docproc_commit=26d1ed1326cd37f8714b44e68929d784dc1659b9`, `test_sha256=f80c2e5d22a9d2f5454953135b61875630d55567ab9ec0f07e2feb8862102aaf` (81 câu test: id, câu hỏi, đáp án, evidence_sets cùng span và `quote_sha`). `sopilot_eval/dataset.py` thêm `fingerprint_test_split`, `check_frozen` (lỗi khi hash, `corpus_version` hoặc commit docproc khác, hay có câu test chưa duyệt) và `--freeze`; 10 unit test trong `eval/tests/test_dataset_freeze.py`. Bằng chứng: `python -m sopilot_eval.dataset --dataset datasets/sop-main --require-reviewed` xanh (`frozen: true`), `pytest` eval 80 pass. Unfreeze chỉ bằng sửa tay manifest có ghi lý do (README). Giới hạn: `eval/datasets/` không nằm trong git, owner cần backup riêng thư mục `sop-main`; `candidate_sections` của câu âm vẫn đếm trên bản cũ.
