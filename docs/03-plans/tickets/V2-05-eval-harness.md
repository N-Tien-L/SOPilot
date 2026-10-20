---
id: V2-05
title: "Eval harness truy xuất (FR-18)"
type: feat
status: review
created: 2026-10-17
updated: 2026-10-20
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-07, V2-27]
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
- [x] Chạy thật với `bge-m3` và `bge-reranker-v2-m3` trên máy owner, xác nhận cấu hình `rq1-rq3-bge-m3.yaml` chạy được (CPU). Bằng chứng ở §4.
- [x] Ghim `revision` HF commit hash trong cấu hình: `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`, `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` (bản `main` trên HF ngày 2026-10-20); `run.json` ghi lại revision.
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

Chạy thật 2026-10-20 (máy owner: AMD Ryzen, 16 luồng, CPU, torch 2.14.1+cpu, sentence-transformers 6.1.0):
```powershell
cd eval; uv sync --extra local --extra dev; uv run pytest -q   # 5 passed
uv run python -m sopilot_eval.run --dataset datasets/smoke --config configs/rq1-rq3-bge-m3.yaml
```
- Run `20261020-140634`: đủ 5 cấu hình (dense, bm25, hybrid, hybrid-legacy-w, hybrid-rerank), xuất đủ 4 file. Tổng 35 phút, phần lớn là tải `bge-reranker-v2-m3` (~2 GB, HF chưa đăng nhập); `bge-m3` đã có sẵn trong cache. Số liệu trên smoke (3 chunk, 9 câu) chỉ xác nhận chạy được, **không báo cáo**.
- Đo riêng tốc độ CPU (đoạn ~800 ký tự): embed `bge-m3` khoảng 0,41 s/chunk (64 chunk, batch 16; có cache nên chỉ tốn một lần); rerank 25 ứng viên mất khoảng 10,5–11 s/câu hỏi.
- Hệ quả cho V2-07: 200 câu × rerank pool 25 ≈ 35–40 phút mỗi lần chạy cấu hình rerank, chấp nhận được cho eval. Với demo tương tác thì quá chậm: giữ `RERANK_ENABLED=false` mặc định hoặc giảm pool (TECH-V2-ai-service §11 Q3).
- Còn lại: review code bởi người khác.
