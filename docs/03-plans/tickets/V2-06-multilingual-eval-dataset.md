---
id: V2-06
title: "Corpus và bộ câu hỏi đa ngôn ngữ (VI, EN) có người duyệt"
type: docs
status: todo
created: 2026-10-17
updated: 2026-10-21
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
- [ ] Mỗi câu có `lang`, `cross_lingual` (bool), `answerable`, `expected` ({doc, pages}), `reference_answer`.
- [ ] Câu hỏi đa dạng: tra cứu số liệu, quy trình nhiều bước, câu cần nhiều đoạn, câu diễn đạt khác từ khóa trong tài liệu.
- [ ] Nếu LLM soạn nháp: owner duyệt từng câu; báo cáo ghi số câu sinh, số bị loại.
- [ ] Chia tập: dev (chỉnh ngưỡng) và test (báo cáo cuối), không trộn.

## 3. Hướng dẫn
- **File:** `eval/datasets/<name>/corpus/`, `questions.jsonl`, `SOURCES.md`. Định dạng ở `eval/README.md`.
- Agent có thể gom nguồn công khai và soạn nháp; owner duyệt.

## 4. Kiểm thử
`uv run python -m sopilot_eval.run --dataset datasets/<name> --config configs/smoke.yaml` chạy hết không lỗi định dạng và báo cáo có bảng tách theo `lang`.
