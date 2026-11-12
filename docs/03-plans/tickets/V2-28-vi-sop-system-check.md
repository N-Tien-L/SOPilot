---
id: V2-28
title: "Bộ kiểm hệ thống SOP tiếng Việt (30–40 câu): ô gộp, ghép context, mã tài liệu, hiệu lực, không dấu"
type: test
status: review
created: 2026-10-21
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-19, V2-21, V2-22]
blocks: [V2-18]
branch: "test/tests-vi-sop-system-check"
assignee: owner
---

# TICKET V2-28: Bộ kiểm hệ thống SOP tiếng Việt

## 1. Bối cảnh & Mục tiêu
Owner chốt 2026-10-21 (audit đầu-cuối ai-service theo loại query, D7; xem [PLAN-V2](../PLAN-V2-sopilot-mvp.md)). Corpus RQ của `V2-06` là Markdown GitLab tiếng Anh; câu tiếng Việt đều là VI→EN. Vì vậy chunk `PROCEDURE_STEP`, văn bản Điều/Khoản, ghép context theo mục (TECH-V2-ai-service §6.4a), mã tài liệu, metadata trong `<source>` và term bỏ dấu **chưa từng được đo trên SOP tiếng Việt thật**; `V2-19` chỉ đo trích xuất, không đo hỏi đáp.

Đây là bộ **kiểm hệ thống** để nghiệm thu các thay đổi của audit, không phải thí nghiệm RQ và không dùng để chọn ngưỡng RQ3 (thuộc `V2-07`).

## 2. Tiêu chí Hoàn thành
- [ ] Chốt kích thước với owner theo khả năng duyệt (đề xuất 30–40 câu tiếng Việt) trên các file `V2-19` đã được owner duyệt: SOP ISO có bảng quy trình và ô gộp, văn bản Điều/Khoản, tài liệu có ngày hiệu lực và mã, PDF 1–2 trang. Cùng schema với `V2-06` (`evidence_sets` theo span, `query_types`, `reference_answer`), tách `dev`/`test`.
- [ ] Phủ các nhóm, mỗi nhóm có câu đạt và câu dễ sai:
  - (a) ô gộp "Trách nhiệm": "bước 3 ai làm" (kiểm `cell_spans` và chunk `PROCEDURE_STEP`);
  - (b) điều kiện hoặc ngoại lệ nằm ở đầu mục (kiểm ghép context §6.4a);
  - (c) tra theo mã tài liệu ("QT-MH-01 bước 2 ai duyệt"; kiểm `doc_code_boost`);
  - (d) lần ban hành, ngày hiệu lực, người phê duyệt (kiểm `<source code rev effective>`);
  - (e) biến thể không dấu **sinh tự động** từ các câu đã có (kiểm term `~`);
  - (f) tài liệu 1–2 trang (kiểm luật header/footer);
  - (g) câu tình huống có dữ kiện cụ thể;
  - (h) câu ngoài chủ đề, vô nghĩa, quá 1000 ký tự và nối tiếp (kiểm `refusal_reason` và việc câu đó có vào danh sách khoảng trống hay không);
  - (i) câu chứa PII (kiểm che trước khi gửi LLM và trong danh sách khoảng trống).
- [ ] Runner chạy pipeline `V2-10` thật trên stack local và DB (LLM cố định, `temperature=0`; phần không cần sinh chạy với LLM giả). Báo cáo theo nhóm (a)–(i) và theo `query_types`: tỉ lệ gold span nằm trong context, citation precision, tỉ lệ từ chối đúng, `refusal_reason` đúng, tỉ lệ câu vào danh sách khoảng trống đúng.
- [ ] Dùng bộ `dev` để chốt giá trị khởi đầu còn để ngỏ: `retrieval.doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS`; số liệu `test` chỉ để báo cáo.
- [ ] Báo cáo `docs/04-reports/AUDIT-vi-sop-system-check-<ngày>.md`: nhóm nào đạt hay không, nguyên nhân, đề xuất tiếp theo (ví dụ chunk `DOC_INFO` hoặc mở §6.4a, theo TECH-V2-ai-service §12a). Ghi rõ đây không phải kết quả RQ và cỡ mẫu nhỏ.

## 2a. Bằng chứng và mục còn mở (2026-11-13)
- Harness: `eval/sopilot_eval/system_check.py`, `eval/configs/vi-sop-check.yaml`, `eval/tests/test_vi_sop_check.py`. Runner gọi `QAService.answer` thật; nhóm e sinh tự động với seed cố định.
- Bộ câu bản nháp `eval/datasets/vi-sop-check/` (gitignored): 33 câu + 4 câu nhóm e = 37, 33 span, 6 tài liệu; `--dry-run` 2026-11-13 hợp lệ. Báo cáo: [AUDIT-vi-sop-system-check-2026-11-13](../../04-reports/AUDIT-vi-sop-system-check-2026-11-13.md) (`draft`, không phải kết quả RQ, cỡ mẫu nhỏ, **chưa chạy pipeline**).
- **Còn mở (owner):** duyệt từng câu và giấy phép 6 tài liệu; chốt cỡ và ngưỡng đạt 0,8; chạy thật trên stack local với Modal (`dev` để chốt `doc_code_boost`, `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_FOLLOWUP_MAX_TOKENS`, rồi `test`). Phần còn thiếu trong harness: `gold_in_context` (asker chưa trả span của context) và tỉ lệ vào danh sách khoảng trống.

## 3. Hướng dẫn
- **File:** `eval/datasets/vi-sop-check/` (câu hỏi, nhãn, `SOURCES.md`), `eval/sopilot_eval/system_check.py`, `eval/configs/vi-sop-check.yaml`. Tài liệu không được phân phối lại thì commit manifest và script tải, không commit file.
- Agent có thể soạn nháp câu hỏi; owner duyệt từng câu (như `V2-06`).
- Gọi pipeline `qa/pipeline.py` trực tiếp, không chép logic sang harness.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Định dạng bộ dữ liệu, sinh biến thể không dấu, tính chỉ số theo nhóm | `uv run pytest` trong `eval/` |
| Thủ công | Chạy trên `test` bằng stack local, đính kèm báo cáo | `python -m sopilot_eval.system_check --config eval/configs/vi-sop-check.yaml` |
