---
id: AUDIT-vi-sop-system-check-2026-11-13
title: "Bộ kiểm hệ thống SOP tiếng Việt (V2-28): kiểm dữ liệu, chưa chạy pipeline"
type: audit
status: draft
created: 2026-11-13
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [tests, ai-qa]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/03-plans/tickets/V2-28-vi-sop-system-check.md
  - eval/README.md
---

# Bộ kiểm hệ thống SOP tiếng Việt (V2-28)

> **Đây không phải kết quả RQ** và không dùng để chọn ngưỡng RQ3 (thuộc `V2-07`). Cỡ mẫu nhỏ (33 câu viết tay + 4 câu không dấu sinh tự động = 37 câu), không đủ để kết luận thống kê.
>
> **Kết luận:** `PASSED_WITH_WARNINGS` **chỉ cho phần kiểm dữ liệu và harness**. Pipeline chưa chạy trên bộ này, nên **chưa biết nhóm nào đạt**; các mục (a)–(i) ở §3 đều "chưa đo".

## 1. Phạm vi đã làm

| Phần | Trạng thái |
|---|---|
| Bộ câu `eval/datasets/vi-sop-check/` (gitignored): 33 câu, 33 span gold, 6 tài liệu (`SOURCES.md`, `manifest.json` có sha256) | Bản nháp, `review_status: draft`, **chưa owner duyệt**; giấy phép tài liệu chờ owner |
| Nhóm e sinh tự động (`generate_group_e`, seed `vi-sop-check-group-e-v1`) | Có, có unit test |
| Runner `eval/sopilot_eval/system_check.py`, config `eval/configs/vi-sop-check.yaml` | Có. Chạy thật gọi `QAService.answer` (đường đi thật, `qa/pipeline.py`); test dùng asker giả |
| Chỉ số theo nhóm và `query_types` (citation precision, span gold được trích dẫn, từ chối đúng, `refusal_reason` đúng, che PII) | Có |
| `gold_in_context`, tỉ lệ vào danh sách khoảng trống đúng | **Chưa**: `ServiceAsker` chưa trả `context_spans`; danh sách khoảng trống (V2-13) chưa được nối vào runner |
| Chốt `doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS` trên `dev` | **Chưa**: runner chỉ ghi giá trị vào báo cáo, không áp dụng |

## 2. Lệnh đã chạy (2026-11-13)

| Lệnh | Kết quả |
|---|---|
| `cd eval; uv run python -m sopilot_eval.system_check --config configs/vi-sop-check.yaml --dry-run` | Dữ liệu hợp lệ (schema, offset và sha256 của span so với corpus, tách `dev`/`test`, cỡ nhóm). 33 câu + 4 câu nhóm e; mỗi nhóm 2 `dev` + 2 `test`, riêng nhóm h có 3 `test`. Không gọi dịch vụ nào |
| `cd eval; uv run pytest -q` | xem kết quả kiểm chạy của đợt đóng Wave 1 (ticket V2-28 §2a) |

## 3. Kết quả theo nhóm

| Nhóm | Kiểm | Kết quả |
|---|---|---|
| (a) ô gộp "Trách nhiệm" | `cell_spans`, chunk `PROCEDURE_STEP` | chưa đo |
| (b) điều kiện/ngoại lệ đầu mục | ghép context §6.4a | chưa đo |
| (c) tra theo mã tài liệu | `doc_code_boost` | chưa đo |
| (d) lần ban hành, ngày hiệu lực, người duyệt | `<source code rev effective>` | chưa đo |
| (e) biến thể không dấu | term `~` | chưa đo |
| (f) tài liệu 1–2 trang | luật header/footer | chưa đo |
| (g) câu tình huống | | chưa đo |
| (h) ngoài chủ đề, vô nghĩa, quá dài, nối tiếp | `refusal_reason` | chưa đo |
| (i) câu có PII | che trước LLM | chưa đo |

## 4. Việc owner cần làm để có kết quả

1. Duyệt từng câu, đáp án, span và nhãn (đặc biệt h04 kỳ vọng `INPUT_INVALID`, i01–i04 chỉ kiểm che PII), xác nhận cỡ 37 câu và ngưỡng đạt đề xuất 0.8 mỗi nhóm.
2. Xác nhận giấy phép 6 tài liệu trong `SOURCES.md` (tài liệu không được phân phối lại thì chỉ commit manifest và script tải).
3. Chạy thật trên stack local với endpoint Modal đã làm nóng: nạp 6 tài liệu vào một workspace, điền `principal` và `document_ids` vào bản config riêng (không commit id), chạy `--split dev` để chốt ba tham số, rồi `--split test`, và cập nhật báo cáo này với số liệu, phần cứng và commit.

## 5. Chưa xác minh

Toàn bộ chỉ số hỏi đáp ở §3; `gold_in_context`; danh sách khoảng trống; hiệu chỉnh ba tham số trên `dev`.
