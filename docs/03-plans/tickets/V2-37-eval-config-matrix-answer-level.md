---
id: V2-37
title: "Ma trận cấu hình truy xuất và eval mức câu trả lời với giám khảo độc lập"
type: test
status: todo
created: 2026-11-11
updated: 2026-11-11
author: "Owner"
scope: tests
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-07, V2-10, V2-13, V2-27, V2-35]
blocks: [V2-18]
branch: "test/eval-config-matrix"
assignee: pair
---

# TICKET V2-37: Ma trận cấu hình truy xuất và eval mức câu trả lời

> **Phạm vi:** `tests` | **Độ phức tạp:** `L` | **Ưu tiên:** `P0`
> **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP` | **Nhánh:** `test/eval-config-matrix`

## 1. Bối cảnh & Mục tiêu

Owner chốt 2026-11-11 (ghi chú trong [PLAN-V2](../PLAN-V2-sopilot-mvp.md)). Số liệu truy xuất RQ1–RQ5 đã có ([AUDIT-eval-rq1-rq3](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) §12, [V2-35](V2-35-infra-modal-rerank-shared-gpu.md) mục kết quả). Báo cáo nghiên cứu còn thiếu:

- số liệu **mức câu trả lời** trên `sop-main-v2`. Lượt `answers` của V2-10 chỉ chạy trên `sop-main`, và model sinh tự chấm chính nó (`judge_is_the_answer_model: true`);
- thước đo **độ đúng so với `reference_answer`**. `answers.py` hiện chỉ đo faithfulness so với context;
- một lập luận có kiểm soát cho cấu hình đề xuất. Trên `sop-main-v2` test, dense + rerank và hybrid + rerank không phân biệt được (0,953 / 0,953 / 0,958; CI chứa 0);
- đối chiếu harness với API thật ở mức câu trả lời. Harness không đi qua guard, router, PII, rewrite, lọc quyền, output guard.

**Cấu hình đề xuất:** `hybrid`, RRF `k = 60`, trọng số 1/1, rerank `bge-reranker-v2-m3` (Modal), pool 25. Đây là mặc định hiện có trong `services/ai-service/config/models.yaml` khi bật rerank. Không sửa code retriever.

**Hypothesis và luật quyết định (ghi trước khi chạy, không đổi sau khi thấy số test):**
- H1 (non-inferiority): `span_recall@5` của hybrid + rerank không kém cấu hình tốt nhất trong ma trận quá δ = 0,02. Cận dưới CI 95% của hiệu ghép cặp phải > −0,02.
- H2 (superiority so với không rerank): hybrid + rerank hơn dense và hơn hybrid ở mức truy xuất, và hơn dense ở độ đúng câu trả lời. CI 95% của hiệu ghép cặp phải > 0.
- H3 (vai trò BM25): ở nhóm câu có mã tài liệu, câu không dấu, và câu có số hiệu/thuật ngữ chính xác, hybrid + rerank ≥ dense + rerank. Nếu H3 không đạt, báo cáo ghi rằng dense + rerank đơn giản hơn mà điểm ngang.
- So nhiều cặp thì hiệu chỉnh Holm. Kết quả âm được báo đầy đủ.

## 2. Tiêu chí Hoàn thành

### A. Chuẩn bị
- [ ] Sao lưu `eval/datasets/` và `eval/results/` ra ngoài repo (hai thư mục bị gitignore). Ghi nơi lưu và SHA-256 của file nén vào ticket.
- [ ] Đối chiếu hybrid `sop-main-v2` test: AUDIT ghi `span_recall@5` 0,803, V2-35 ghi "recall@5 0,835". Ghi rõ đó là hai thước đo khác nhau hay một lỗi.
- [ ] Parity harness và service qua Postgres trên `sop-main-v2` (`service_parity --split all`). Jaccard top-10 trung bình ≥ 0,95.

### B. Ma trận truy xuất (harness, `sop-main-v2`, dev + test)
- [ ] Sáu cấu hình: BM25, dense, hybrid 1/1, hybrid 0,7/0,3, dense + rerank, hybrid 1/1 + rerank. Cùng bge-m3 (revision đã ghim), chunk `docproc`, k = 5.
- [ ] Độ nhạy của hybrid + rerank: `rrf_k` ∈ {20, 60, 100} × pool ∈ {10, 25, 50}.
- [ ] Bộ dẫn xuất `datasets/sop-main-v2-probe`, không sửa bộ đã freeze. Gồm: (i) biến thể không dấu **sinh tự động** từ câu test; (ii) nhóm câu nêu mã tài liệu, gắn tag từ câu v1; (iii) nhóm câu có số hiệu/thuật ngữ chính xác, gắn tag theo luật. Báo cáo là phân tích phụ.
- [ ] Thước đo: `span_recall@5`, `full@5`, `mrr_span`, p50/p95. Tách theo cùng ngôn ngữ / cross-lingual / nhóm probe. Bootstrap theo cụm `intent_id`. Hiệu ghép cặp kèm số câu thắng/thua.

### C. Ngưỡng từ chối
- [ ] Chọn `thresholds.hybrid_rerank` (và `dense_rerank` nếu dùng) trên **dev** bằng luật định trước của `analyze_v2_07` (cực tiểu FR + FA). Áp nguyên lên test. Không ghi vào `models.yaml` nếu owner chưa duyệt.

### D. Giám khảo
- [ ] App Modal giám khảo trên **L40S** (tài khoản Modal thứ hai), một file có tham số model: Gemma 4 26B A4B và Gemma 4 31B, checkpoint FP8, `--max-model-len 8192`, KV cache FP8, `max_containers=1`, idle 60 s. Ghi revision HF.
- [ ] Owner chấm 30 câu trả lời trước (độ đúng: đúng / một phần / sai; faithfulness: có / một phần / không căn cứ), không xem điểm của judge.
- [ ] Hai model Gemma và Qwen tự chấm (mốc) chấm cùng 30 câu đó. Ghi κ Cohen (kèm CI), thời gian, chi phí thật từ `modal billing report`.
- [ ] Chọn model có κ cao hơn; nếu bằng nhau thì chọn 26B A4B. Nếu mọi model có κ < 0,6 thì số chính lấy từ người chấm, judge chỉ là tham khảo.

### E. Mức câu trả lời (harness `answers.py`, commit QA đã ghim)
- [ ] Ghim commit sau khi `V2-13` và `V2-27` xong. Mọi run ghi `dirty: false`.
- [ ] `answers.py` có thêm: reranker GPU, thước đo độ đúng so với `reference_answer`, citation recall, judge độc lập. Có unit test với LLM và judge giả.
- [ ] Chạy thử 20 câu trước. Nếu judge không parse được trên 5% thì dừng, sửa prompt.
- [ ] Ba cấu hình (dense, dense + rerank, hybrid + rerank) × 239 câu test, `temperature = 0`, `expand` bật. Thước đo: độ đúng, faithfulness, citation precision (mức trúng) và recall, trả lời không có trích dẫn, từ chối nhầm (tách cổng truy xuất và LLM), trả lời sai khi nên từ chối, đường risk–coverage, p50/p95.
- [ ] Lượt "đóng sách" (không có context) trên câu trả lời được. Câu trả lời đúng khi không có tài liệu thì gắn cờ, và báo faithfulness tách theo cờ.
- [ ] Ba lượt lặp ở `temperature = 0,2` trên 60 câu cố định theo hash. Báo tỉ lệ câu trả lời đổi giữa các lượt.
- [ ] Owner chấm thêm 30 câu (tổng 60). Báo κ cuối cùng giữa judge đã chọn và owner.

### F. Đối chiếu với API thật
- [ ] Runner gọi `POST /ai/v1/conversations/.../messages` (JWT của core-api, đọc SSE) với core-api, ai-service, worker chạy local. Tài liệu upload qua core-api. Span vàng ánh xạ lại theo `quote`.
- [ ] Khoảng 30 câu test chạy qua cả harness và API, cùng cấu hình. Báo độ chênh của outcome, citation và độ đúng. Nếu chênh vượt CI của harness thì điều tra trước khi báo cáo.

### G. Ngân sách và báo cáo
- [ ] Modal tài khoản sinh câu trả lời ≤ $15; tài khoản giám khảo ≤ $8. Ghi chi phí thật sau mỗi bước. Vượt trần thì dừng và hỏi owner.
- [ ] Kết quả thô lưu ở `eval/results/<run_id>/`. Báo cáo `docs/04-reports/AUDIT-eval-config-matrix-answers-<ngày>.md`: hypothesis, luật quyết định, bảng kèm CI, kết quả bất lợi, giới hạn (nhãn do LLM soạn, 23 tài liệu, judge nhỏ, tiếng Việt chưa có trên model card Gemma 4).
- [ ] `eval` pytest xanh; `./scripts/check-docs.ps1` xanh.

## 3. Hướng dẫn

- **Không gửi tài liệu sang API ngoài.** Giám khảo chỉ chạy trên Modal của owner. Gemini không dùng cho phần chấm chính: chỉ 104/200 câu test có bằng chứng thuộc tài liệu được phép gửi đi, và context có thể chứa chunk của tài liệu bị hạn chế (`manifest.json`, `redistribution`).
- **Nhãn:** giữ nguyên `review.jsonl`. Báo cáo ghi đúng quy trình: câu do LLM soạn (`drafted_by`), 105 câu v1 owner duyệt trực tiếp, 188 câu v2 owner duyệt dựa trên bản rà của Claude (`review_basis=claude_review`).
- Tái dùng `sopilot_eval.run`, `analyze_v2_07`, `answers`, `service_parity`. Không chép logic pipeline sang harness.
- Không thêm dependency. `httpx` đã có qua path dependency `services/ai-service`.
- Thứ tự: A → B (chạy nền) → C → D → E → F → G.

## 4. Kiểm thử

| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Thước đo độ đúng, citation recall, parse verdict, sinh biến thể không dấu, luật chọn ngưỡng, κ | `cd eval; uv run pytest -q` |
| Thủ công | Ma trận truy xuất, `answers`, giám khảo, đối chiếu API | Lệnh và run id ghi vào mục 6 |

## 5. Tóm tắt các file thay đổi

| File | Hành động |
|---|:---:|
| `eval/sopilot_eval/answers.py` | MODIFY |
| `eval/sopilot_eval/system_api.py` (runner gọi API thật) | CREATE |
| `eval/sopilot_eval/probe.py` (bộ dẫn xuất) | CREATE |
| `eval/configs/v2-37-matrix.yaml`, `v2-37-sensitivity.yaml`, `v2-37-answers.yaml` | CREATE |
| `infrastructure/modal/serve_judge.py` | CREATE |
| `eval/tests/test_v2_37_*.py` | CREATE |
| `docs/04-reports/AUDIT-eval-config-matrix-answers-<ngày>.md` | CREATE |

## 6. Kết quả

*(Điền khi chạy: run id, commit, chi phí thật.)*
