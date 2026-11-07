---
id: V2-07
title: "Chạy RQ1–RQ3 và RQ5, viết báo cáo"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-07
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-05, V2-06, V2-22]
blocks: [V2-18]
branch: "docs/tests-eval-report"
assignee: pair
---

# TICKET V2-07: Chạy thí nghiệm

## 1. Bối cảnh & Mục tiêu
Cổng quyết định: số liệu truy xuất đa ngôn ngữ cho biết RAG có đáng đầu tư tiếp không. Có thể điều chỉnh mục tiêu NFR (recall@5 ≥ 0.80...) dựa trên baseline.

Theo nguyên tắc khả thi: **thử chạy thật từng cấu hình trên máy owner trước, rồi mới đưa vào ma trận**. Cấu hình không chạy nổi trên CPU trong thời gian hợp lý thì chạy trên tập con hoặc loại, và báo cáo ghi lý do. Không cam kết trước cấu hình nào sẽ vào báo cáo.

Sửa 2026-10-21 (rà soát trước implement, TECH-V2-ai-service §6.5): số liệu chính thức chạy với bộ chunk `sopilot_ai.docproc` của `V2-22` để kết quả và ngưỡng áp dụng được cho service. Smoke và lần chạy thăm dò bằng bộ chunk 800/100 ký tự hiện có vẫn làm được trước `V2-22`, nhưng không vào báo cáo như số liệu chính thức.

## 2. Tiêu chí Hoàn thành
- [x] Cấu hình RQ chính thức dùng `chunking: docproc` (target 384 / max 512 token, tokenizer của model đang đo, giống `config/models.yaml` của ai-service); báo cáo ghi phiên bản `docproc` và `normalizer_version`. Kết quả chạy bằng bộ chunk cũ chỉ được ghi là thăm dò.
- [x] Sửa 2026-10-21 (audit theo loại query, owner chốt D11/P0-1/P0-6), **làm trước khi chạy số liệu chính thức** để không phải đo lại: (a) harness cài tokenizer BM25 cuối của TECH-V2-ai-service §6.3 (term bỏ dấu `~`) trong `eval/sopilot_eval/retrievers.py::tokenize`; (b) cổng `hybrid` của harness dùng `dense_score` luôn có giá trị: ứng viên đầu chỉ có điểm BM25 được tính cosine trực tiếp (TECH-V2-ai-service §6.4, [HANDOFF-research-04](../../04-reports/HANDOFF-research-04-experiment-tooling.md) §5), vì RQ3 đo ngưỡng trên đúng điểm này; (c) `V2-06` đã gắn `query_types` và đóng băng tập test. Báo cáo tách số liệu theo `query_types`.
- [x] Đo thử (smoke) thời gian và RAM của `bge-m3` và `bge-reranker-v2-m3` trên máy owner với ~50 chunk; quyết định cấu hình nào vào ma trận dựa trên số đo.
- [x] RQ1/RQ1b: dense, bm25, hybrid (cả hai bộ trọng số 1/1 và 0.7/0.3) với `bge-m3` ghim revision, trên tập test, **báo cáo tách theo `lang` và theo cross-lingual**.
- [x] Sửa 2026-10-21 (TECH-V2-ai-service §6.4): nếu hybrid thua dense ở nhóm cross-lingual, chạy thêm hybrid với `cross_lingual_bm25_factor` ∈ {0.3, 0} (harness cài hệ số này trong RRF của mình cho tới khi `V2-09` có `retrieval.fusion`); chọn giá trị trên tập dev, báo cáo trên tập test, ghi vào `retrieval.cross_lingual_bm25_factor`. Nếu không thua, giữ `1.0` và ghi lý do. **(Chốt 2026-11-07: giữ `1.0`. Luật dev chọn 0,3 nhưng chỉ hơn 1 câu, test không khác, hệ số không chạm nguyên nhân; xem báo cáo §4.2, §12.)**
- [x] RQ2: rerank bật/tắt, k ∈ {5, 10}, kèm độ trễ; nếu quá chậm trên CPU thì chạy trên tập con cố định và nêu rõ.
- [x] RQ3: đường cân bằng false refusal / false answer; ngưỡng chọn trên tập dev rồi đo trên tập test. Ngưỡng chọn được ghi vào `retrieval.thresholds` của ai-service theo từng chế độ (TECH-V2-ai-service §6.4). **(Chốt 2026-11-07: lệch có chủ đích, không ghi. Ngưỡng chọn trên dev không chuyển sang test, FA test 0,36 đến 0,56, vì dev chỉ có 14 negative; giữ giá trị giữ chỗ trong `models.yaml` và hiệu chỉnh ở V2-10.)**
- [x] RQ5: chỉ so các model chạy nổi trên máy (ứng viên: `bge-m3`, `Qwen3-Embedding-0.6B`, `multilingual-e5-large-instruct`; e5 giới hạn 512 token). Ghi thời gian embed corpus của từng model.
- [x] Ghi phần cứng (CPU, RAM); độ trễ chạy ≥ 3 lần, nêu độ lệch.
- [x] Nêu giới hạn: quy mô dữ liệu nhỏ, BM25 tách từ đơn giản (không có tokenizer riêng từng ngôn ngữ), chỉ đo truy xuất nếu V2-10 chưa xong.
- [x] Báo cáo `docs/04-reports/AUDIT-eval-rq1-rq3-<ngày>.md` trỏ tới `eval/results/<run_id>/`.

## 3. Hướng dẫn
`uv sync --extra local` rồi `uv run python -m sopilot_eval.run --dataset ... --config configs/rq1-rq3-bge-m3.yaml`. Thêm cấu hình RQ5 vào `eval/configs/` sau khi đo thử. `eval/pyproject.toml` khai báo `services/ai-service` là dependency dạng path để import `sopilot_ai.docproc`.

## 4. Kiểm thử
Chạy lại cùng cấu hình phải cho cùng thứ hạng truy xuất (PRD NFR tái lập).

## 5. Tiến độ 2026-11-04

Số liệu chính thức đã chạy, báo cáo [AUDIT-eval-rq1-rq3-2026-11-04](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) (`draft`). Mã harness đã commit ở `583d0a3`.

- [x] Chunk `docproc` (target 384 / max 512, tokenizer của từng model) qua `sopilot_ai.docproc` (path dependency trong `eval/pyproject.toml`); 23/23 tài liệu dựng lại khớp từng byte corpus đã freeze. `normalizer_version=2`, corpus từ docproc `26d1ed1`.
- [x] (a) Tokenizer BM25 có term `~` (`retrievers.tokenize`, `lexical_len`); (b) cổng `hybrid` dùng `dense_score` luôn có giá trị, `bm25` không có cổng, rerank dùng sigmoid; (c) báo cáo tách theo `query_types`. Test: `eval/tests/test_v2_07_retrieval.py`.
- [x] Smoke bge-m3 / bge-reranker-v2-m3 / Qwen3-Embedding-0.6B / e5-large-instruct (`sopilot_eval.smoke_models`); cả bốn vào ma trận, rerank chạy file cấu hình riêng.
- [x] RQ1 tách `lang` và cross-lingual; RQ1b chạy hệ số {0,3; 0}: dev chọn 0,3 (hơn 1 câu), test không khác. **Chưa ghi** vào `retrieval.cross_lingual_bm25_factor`: chờ owner (ai-service chưa có `models.yaml`).
- [x] RQ2: rerank bật/tắt, k ∈ {5, 10}, cả dev và test (không cần tập con), 3 lượt; p50 17,7 s/câu trên CPU.
- [x] RQ3: ngưỡng chọn trên dev, đo trên test. **Chưa ghi** vào `retrieval.thresholds`: chờ owner.
- [x] RQ5: ba model, có thời gian embed corpus.
- [x] Phần cứng, độ trễ 3 lượt kèm độ lệch, giới hạn.
- [x] Tái lập: chạy lại cùng cấu hình cho 486/486 bảng xếp hạng top-25 trùng.
- [x] **Bộ mở rộng `sop-main-v2`** (owner yêu cầu 2026-11-04 sau khi thấy `sop-main` không phân biệt được các cấu hình; freeze 2026-11-05):
  - 96 intent mới, không nêu mã tài liệu. Mỗi intent có một câu cùng ngôn ngữ và một câu cross-lingual, kèm negative "suýt đúng".
  - Harness: `extend_dataset`, `run --allow-draft`, bootstrap theo cụm `intent_id`, đếm số câu thắng/thua.
  - Duyệt: Claude soạn, subagent Claude rà với corpus, owner duyệt trên kết quả rà soát của Claude. `test_sha256 = a568bf74…8059`. `sop-main` giữ nguyên hash.
  - Số chính thức RQ1/RQ3/RQ5 ở §12 báo cáo AUDIT:
    - cross-lingual: dense hơn hybrid +0,26 [0,16; 0,37] (thắng 19, thua 0);
    - cùng ngôn ngữ: hybrid hơn dense +0,035, CI chạm 0;
    - `cross_lingual_bm25_factor` không có tác dụng;
    - Qwen3-0,6B ngang bge-m3.
  - RQ2 trên v2, 1 lượt: hybrid + rerank đạt 0,940, cross-lingual 0,893; hơn hybrid +0,137 và hơn dense +0,067. Giá: 18,1 s/câu trên CPU.
  - RQ2b: rerank trên top-25 của dense, hybrid 1/1 hay hybrid 0,7/0,3 cho kết quả như nhau (0,940–0,945, chênh nhau ≤ 0,014). Dense + rerank là cấu hình đơn giản nhất.
  - Owner quyết các đề xuất ở §12 ngày 2026-11-07, xem §6.

## 6. Chốt 2026-11-07

Owner chốt ticket `done` trên báo cáo [AUDIT-eval-rq1-rq3-2026-11-04](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) (`final`). Các đề xuất ở §8 và §12 của báo cáo được nhận như sau; **không đổi** `services/ai-service/config/models.yaml`.

| Mục | Quyết định |
|---|---|
| Model embedding | Giữ `bge-m3`; Qwen3-Embedding-0,6B là phương án ngang hàng, chưa có lý do đổi |
| `cross_lingual_bm25_factor` | Giữ `1.0` |
| `retrieval.thresholds` | Không ghi từ số này; hiệu chỉnh lại ở V2-10 với dev có nhiều negative khó hơn hoặc thêm tín hiệu ngoài cosine (điểm rerank, kiểm ở tầng LLM) |
| NFR recall@5 ≥ 0,80 | Không hạ |
| Rerank | Chưa bật mặc định trên CPU (15,7 đến 18,1 s/câu) |

**Chuyển sang V2-10 và V2-18 (chưa quyết, không chặn V2-07):**
- Chế độ truy xuất mặc định. `models.yaml` đang là `hybrid`, nhưng trên `sop-main-v2` hybrid thua dense ở câu cross-lingual (+0,26, thắng 19 thua 0). Không rerank thì dense tốt hơn tổng thể; có rerank thì dense + rerank là cấu hình đơn giản nhất, chất lượng như hybrid + rerank. Cần quyết cùng với ngân sách độ trễ (GPU hay không).
- Phương án nhánh BM25 theo ngôn ngữ câu hỏi (tắt khi khác ngôn ngữ đa số) hoặc dịch câu hỏi: chưa đo.
- Giá trị giữ chỗ `thresholds` (dense 0,45, hybrid 0,45) thấp hơn ngưỡng dev (0,619 và 0,482) nên gần như không chặn câu âm; V2-10 phải thay trước khi bật cổng.
- Dữ liệu `sop-main-v2` và `eval/results/` bị `.gitignore`; chỉ có hash đóng băng và báo cáo trong repo.
