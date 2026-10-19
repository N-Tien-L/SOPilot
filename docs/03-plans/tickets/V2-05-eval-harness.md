---
id: V2-05
title: "Eval harness truy xuất (FR-18)"
type: feat
status: review
created: 2026-10-17
updated: 2026-10-17
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-07]
branch: "feat/tests-eval-harness"
assignee: pair
---

# TICKET V2-05: Eval harness truy xuất

## 1. Bối cảnh & Mục tiêu
Harness độc lập trong `eval/`, chạy dense, BM25, hybrid (RRF) và rerank, không cần LLM hay stack. Phục vụ RQ1–RQ3, RQ5.

## 2. Tiêu chí Hoàn thành
- [x] Chạy được `python -m sopilot_eval.run` với dataset + config, xuất `run.json`, `metrics.json`, `per_question.jsonl`, `report.md`.
- [x] Metrics: recall@k, hit@k, MRR, nDCG@10, độ trễ p50/p95, quét ngưỡng từ chối.
- [x] Cache embedding theo `(model, sha256(text))`.
- [x] 5 test pass (`uv run pytest` trong `eval/`).
- [ ] Chạy thật với `bge-m3` và `bge-reranker-v2-m3` trên máy owner, xác nhận cấu hình `rq1-rq3-bge-m3.yaml` chạy được (CPU, chưa kiểm chứng).
- [ ] Ghim `revision` HF commit hash trong cấu hình.
- [ ] Review code bởi người khác trước khi `done`.

## 3. Hướng dẫn
Đã triển khai: `eval/sopilot_eval/{corpus,embedders,retrievers,metrics,run}.py`, `eval/configs/`, `eval/datasets/smoke/`, `eval/tests/test_eval.py`, `eval/README.md`.

Chưa có (ghi nhận, không chặn ticket này): RQ4 (lọc tenant) thuộc V2-14; đo ở mức câu trả lời (citation precision, faithfulness) cần LLM, thuộc V2-10/V2-07.

## 4. Kiểm thử
```powershell
cd eval; uv sync --extra dev; uv run pytest -q
uv run python -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml
```
Kết quả 2026-10-17: 5 passed; lần chạy smoke xuất đủ 4 file. Số liệu smoke (hash embedder, 2 tài liệu) **không có giá trị nghiên cứu**.
