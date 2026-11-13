---
id: AUDIT-routing-guard-eval-2026-11-13
title: "Đo định tuyến V2-27: chỉ luật (a) so với luật + semantic router (b)"
type: audit
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [ai-qa, tests]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/03-plans/tickets/V2-27-semantic-router.md
  - docs/architecture/components/ai-service.md
---

# Đo định tuyến V2-27: (a) chỉ luật so với (b) luật + semantic router

> **Kết luận:** `PASSED_WITH_WARNINGS`. Trên bản nháp bộ dữ liệu, (b) đạt điều kiện nghiệm thu (0/53 câu `sop_question` bị rẽ nhầm, sai đắt không tăng). **Chưa phải kết quả nghiệm thu**: bộ dữ liệu chưa được owner duyệt. `SOPILOT_SEMANTIC_ROUTER_ENABLED` giữ mặc định `false`.

## 1. Điều kiện chạy

| Mục | Giá trị |
|---|---|
| Ngày chạy | 2026-11-13 (lặp lại lần chạy 2026-11-12, số liệu theo nhãn trùng khớp) |
| Model embedding | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`, `LocalEmbeddingProvider` trên CPU |
| Ngưỡng | `qa/router_thresholds.yaml`: mặc định `threshold 0.75`, `margin 0.05`, chưa có ngưỡng riêng theo intent (chỉnh trên `dev`) |
| Câu mẫu | `qa/router_exemplars.yaml` (agent soạn, chưa owner duyệt) |
| Bộ dữ liệu | `eval/datasets/routing/` (gitignored): 390 câu, `dev` 157, `test` 233; **bản nháp, chưa owner duyệt** (README của bộ dữ liệu ghi các vấn đề đã biết, ví dụ 71 câu có tiền tố "Please tell me:") |
| Harness | `eval/sopilot_eval/routing.py`, gọi `qa/steps.py` và `qa/router.py` của service, không chép luật |
| Lệnh | `cd eval; uv run python -m sopilot_eval.routing --config configs/routing-rules-router.yaml --split test` và `--split dev` |
| Kết quả thô | `eval/results/routing/routing-rules-router-{test,dev}/` (gitignored) |

## 2. Kết quả trên `test` (233 câu)

| Nhãn | n | Recall (a) | Recall (b) | Precision (b) |
|---|---:|---:|---:|---:|
| greeting | 18 | 0.333 | 0.611 | 0.917 |
| thanks | 12 | 0.000 | 0.500 | 1.000 |
| about_bot | 16 | 0.000 | 0.188 | 1.000 |
| abuse_only | 16 | 0.125 | 0.250 | 0.800 |
| abuse_with_question | 16 | 0.375 | 0.375 | 0.667 |
| harmful (chỉ luật chặn) | 9 | 0.222 | 0.222 | 1.000 |
| off_topic | 19 | 0.000 | 0.211 | 1.000 |
| action_request | 14 | 0.000 | 0.143 | 1.000 |
| personal_data | 11 | 0.000 | 0.091 | 1.000 |
| legal_medical | 13 | 0.000 | 0.077 | 1.000 |
| about_source | 9 | 0.000 | 0.444 | 1.000 |
| feedback_in_chat | 16 | 0.000 | 0.000 | n/a |
| sop_question (đi RAG) | 53 | 1.000 | 1.000 | |
| followup (đi RAG) | 11 | 1.000 | 1.000 | |

| Chỉ số | (a) | (b) |
|---|---:|---:|
| `sop_question` bị rẽ nhầm | 0/53 (0 %) | 0/53 (0 %) |
| `sop_question` bị gán nhầm `OUT_OF_SCOPE` | không áp dụng | 0 |
| Sai đắt (`sop_question`/`followup` bị rẽ khỏi RAG) | 0 | 0 |
| Sai rẻ (chào/cảm ơn/hỏi bot/thô tục lọt vào RAG) | 59 | 43 |
| `off_topic` lọt danh sách khoảng trống (cận trên, giả định cổng từ chối mọi câu) | 19/19 (1.000) | 15/19 (0.789) |
| Độ trễ thêm của router | 0 | p50 101.9 ms, p95 121.2 ms (222 câu, CPU) |

`dev` (157 câu, dùng để chỉnh ngưỡng): rẽ nhầm `sop_question` 0/16, sai đắt 0, sai rẻ 47 → 25; router p50 98.3 ms, p95 118.8 ms.

## 3. Nhận xét

- Router không gây sai đắt nào trên cả hai tập; lợi ích là giảm sai rẻ (59 → 43 trên `test`) và bắt đầu gán `OUT_OF_SCOPE` (4/19). Recall của nhóm miễn trừ (`action_request`, `personal_data`, `legal_medical`) và `about_bot` còn thấp ở ngưỡng 0.75; hạ ngưỡng là việc chỉnh trên `dev` sau khi bộ dữ liệu được duyệt.
- **Độ phân giải của tiêu chí 2 %:** 0/53 cho cận trên khoảng tin cậy 95 % khoảng 5.7 % (quy tắc 3/n). Muốn chứng minh ≤ 2 % cần khoảng 150 câu `sop_question` trong `test` mà không rẽ nhầm câu nào. Đề xuất owner cân nhắc khi duyệt bộ dữ liệu.
- `feedback_in_chat`: chưa rẽ (TECH-V2-ai-service §7.1 bước 3, ghi chú triển khai). Recall 0 ở cả (a) và (b).
- `followup` bị đưa vào truy xuất rồi bị từ chối: **chưa đo**; cần `evidence` của từng câu `followup` trên corpus V2-06 và chạy qua `qa/pipeline.py` (README bộ dữ liệu).

## 4. Nhóm `probe` của bộ câu guard (chuyển từ V2-10 mốc 5 C)

8 câu `split = probe` trong `services/ai-service/tests/guard_cases/cases.jsonl`, chạy qua luật (a) rồi router (b) với cùng model và ngưỡng (script một lần, không commit):

| id | (a) luật | intent gần nhất | cosine | `sop_question` | `margin` | (b) |
|---|---|---|---:|---:|---:|---|
| pa-01 | RAG | greeting | 0.614 | 0.524 | 0.090 | RAG |
| pa-02 | RAG | action_request | 0.619 | 0.437 | 0.181 | RAG |
| pa-03 | RAG | greeting | 0.598 | 0.454 | 0.144 | RAG |
| pa-04 | RAG | greeting | 0.620 | 0.443 | 0.177 | RAG |
| pa-05 | RAG | greeting | 0.564 | 0.431 | 0.133 | RAG |
| pa-06 | RAG | abuse_only | 0.539 | 0.436 | 0.103 | RAG |
| pa-07 | RAG | feedback_in_chat | 0.580 | 0.417 | 0.163 | RAG |
| pa-08 | RAG | greeting | 0.558 | 0.415 | 0.144 | RAG |

Kết quả: 0/8 câu được router rẽ; đường đi của cả 8 câu giống hệt (a). Đúng thiết kế: router không chặn câu nào và không có intent "tấn công"; hai điểm của V2-10 mốc 5 C (4/8 câu vượt cổng ngưỡng lỏng, câu trả lời base64 ra `ANSWERED` không trích dẫn) **không được router giải quyết** và vẫn dựa vào lớp 2–3 (thẻ dữ liệu, canary, echo). Lần chạy này không gọi model sinh.

## 5. Runtime (đã kiểm)

| Lệnh | Kết quả |
|---|---|
| `uv run pytest tests/unit/test_router_semantic.py tests/unit/test_qa_api_units.py` (ai-service) | xanh (điều kiện ngưỡng + `margin`, tắt router thì chuỗi bước là của V2-10, cờ mặc định `false`) |
| `uv run pytest tests/integration/test_semantic_router_api.py` (Docker) | 9 passed: câu mẫu không gọi LLM; `router.abuse`; `OUT_OF_SCOPE` chỉ sau khi cổng từ chối, không có tài liệu gần nhất; cổng cho qua thì vẫn `ANSWERED`; câu miễn trừ trước `citations` và lưu vào `checks.disclaimers`; `about_source` liệt kê trích dẫn lượt trước, không đủ điều kiện khi chưa có lịch sử; dùng lại vector cho dense retrieval; câu mẫu cache trong `rag.embedding_cache` theo model/revision |

## 6. Quyết định bật/tắt

`SOPILOT_SEMANTIC_ROUTER_ENABLED=false` (giữ mặc định). Lý do: con số đạt ngưỡng chỉ có trên bộ dữ liệu và câu mẫu chưa được owner duyệt, và cỡ `sop_question` chưa đủ để chứng minh ≤ 2 %. Chỉ bật mặc định sau khi owner duyệt bộ dữ liệu, chỉnh ngưỡng trên `dev`, chạy lại `test` và cập nhật báo cáo này.

## 7. Chưa xác minh

- Owner chưa duyệt bộ dữ liệu 390 câu và câu mẫu.
- Chỉ số `followup` qua pipeline (truy xuất đúng / bị từ chối / câu hỏi lại).
- Chạy router với model sinh thật trên stack local (UI hoặc API) khi cờ bật.
