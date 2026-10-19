---
id: V2-07
title: "Chạy RQ1–RQ3 và RQ5, viết báo cáo"
type: docs
status: todo
created: 2026-10-17
updated: 2026-10-17
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-05, V2-06]
blocks: [V2-18]
branch: "docs/tests-eval-report"
assignee: pair
---

# TICKET V2-07: Chạy thí nghiệm

## 1. Bối cảnh & Mục tiêu
Cổng quyết định: số liệu truy xuất đa ngôn ngữ cho biết RAG có đáng đầu tư tiếp không. Có thể điều chỉnh mục tiêu NFR (recall@5 ≥ 0.80...) dựa trên baseline.

Theo nguyên tắc khả thi: **thử chạy thật từng cấu hình trên máy owner trước, rồi mới đưa vào ma trận**. Cấu hình không chạy nổi trên CPU trong thời gian hợp lý thì chạy trên tập con hoặc loại, và báo cáo ghi lý do. Không cam kết trước cấu hình nào sẽ vào báo cáo.

## 2. Tiêu chí Hoàn thành
- [ ] Đo thử (smoke) thời gian và RAM của `bge-m3` và `bge-reranker-v2-m3` trên máy owner với ~50 chunk; quyết định cấu hình nào vào ma trận dựa trên số đo.
- [ ] RQ1/RQ1b: dense, bm25, hybrid (cả hai bộ trọng số 1/1 và 0.7/0.3) với `bge-m3` ghim revision, trên tập test, **báo cáo tách theo `lang` và theo cross-lingual**.
- [ ] RQ2: rerank bật/tắt, k ∈ {5, 10}, kèm độ trễ; nếu quá chậm trên CPU thì chạy trên tập con cố định và nêu rõ.
- [ ] RQ3: đường cân bằng false refusal / false answer; ngưỡng chọn trên tập dev rồi đo trên tập test.
- [ ] RQ5: chỉ so các model chạy nổi trên máy (ứng viên: `bge-m3`, `Qwen3-Embedding-0.6B`, `multilingual-e5-large-instruct`; e5 giới hạn 512 token). Ghi thời gian embed corpus của từng model.
- [ ] Ghi phần cứng (CPU, RAM); độ trễ chạy ≥ 3 lần, nêu độ lệch.
- [ ] Nêu giới hạn: quy mô dữ liệu nhỏ, BM25 tách từ đơn giản (không có tokenizer riêng từng ngôn ngữ), chỉ đo truy xuất nếu V2-10 chưa xong.
- [ ] Báo cáo `docs/04-reports/AUDIT-eval-rq1-rq3-<ngày>.md` trỏ tới `eval/results/<run_id>/`.

## 3. Hướng dẫn
`uv sync --extra local` rồi `uv run python -m sopilot_eval.run --dataset ... --config configs/rq1-rq3-bge-m3.yaml`. Thêm cấu hình RQ5 vào `eval/configs/` sau khi đo thử.

## 4. Kiểm thử
Chạy lại cùng cấu hình phải cho cùng thứ hạng truy xuất (PRD NFR tái lập).
