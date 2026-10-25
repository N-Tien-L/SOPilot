---
id: V2-06
title: "Corpus và bộ câu hỏi đa ngôn ngữ (VI, EN) có người duyệt"
type: docs
status: in-progress
created: 2026-10-17
updated: 2026-10-25
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
- [ ] Chốt kích thước tối thiểu khả thi với owner trước khi làm. Đề xuất ban đầu (điều chỉnh được): ~10 tài liệu mỗi ngôn ngữ; ~100 câu hỏi gồm ~35 VI, ~35 EN, ~15 cross-lingual (hỏi một ngôn ngữ, đáp án ở tài liệu ngôn ngữ kia), ~15 không trả lời được.
- [ ] Mỗi tài liệu ghi nguồn và giấy phép trong `datasets/<name>/SOURCES.md`; không đưa tài liệu không được phép tái phân phối vào repo (commit manifest + script tải).
- [ ] Mỗi câu có `lang`, `cross_lingual` (bool), `answerable`, `evidence_sets` (gold theo **span**, schema ở [HANDOFF-research-02](../../04-reports/HANDOFF-research-02-dataset-and-labeling.md) §5.1 và §8), `reference_answer`; `expected` ({doc, pages}) là trường suy ra từ `evidence_sets`, không nhập tay hai lần. Sửa 2026-10-21 (audit theo loại query): gold theo span là điều kiện của chỉ số "tỉ lệ gold span nằm trong context" ở `V2-10`.
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

Phiếu đọc câu hỏi/đáp án/bằng chứng: [REVIEW pilot](../../../eval/datasets/sop-pilot/REVIEW.md). Hướng dẫn tái lập: [README pilot](../../../eval/datasets/sop-pilot/README.md). `prepare_pilot` và validator pass; `--require-reviewed` vẫn phải thất bại. Giữ `in-progress`, các AC dữ liệu chưa nghiệm thu. Bằng chứng và giới hạn ở [HANDOFF pilot](../../04-reports/HANDOFF-V2-06-V2-19-pilot-review-2026-10-25.md).
