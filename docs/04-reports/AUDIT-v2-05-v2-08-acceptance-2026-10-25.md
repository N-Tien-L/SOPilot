---
id: AUDIT-V2-05-V2-08-ACCEPTANCE-2026-10-25
title: "Nghiệm thu V2-05 công cụ eval và V2-08 hạ tầng local"
type: audit
status: final
created: 2026-10-25
updated: 2026-10-25
author: "Owner"
scope: [eval, infra]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/03-plans/tickets/V2-05-eval-harness.md
  - docs/03-plans/tickets/V2-08-flyway-and-compose.md
---

# Phạm vi owner đã chốt

Owner xác nhận trong chat ngày 2026-10-25: "ok chốt", sau khi thống nhất hoàn tất
review kỹ thuật, kiểm cấu hình volume/network và commit riêng.

- **V2-05:** nghiệm thu công cụ benchmark truy xuất. Không nghiệm thu kết quả RQ,
  độ chính xác trả lời hoặc toàn bộ SOPilot. Dataset thật, scorer span-aware,
  chunker docproc và số liệu chính thức vẫn thuộc V2-06/V2-07/V2-22.
- **V2-08:** nghiệm thu nền hạ tầng local. Kiểm tách volume/network ở cấu hình
  Compose gốc; kiểm runtime bằng project riêng dùng tmpfs. Không yêu cầu dùng
  `.env` thật hoặc khởi động trên volume hiện có để hoàn tất phạm vi này.

## Review delta

Codex rà lại diff và call path của splitter, metrics, retriever, embedding cache,
runner, migration và MinIO init; không có blocker còn lại trong phạm vi trên.
Đây là review kỹ thuật của Codex cùng owner nghiệm thu phạm vi; không ghi nhận
một peer reviewer độc lập hoặc CI/PR review chưa diễn ra.

- nDCG chỉ thưởng nguồn mới, không tăng điểm do chunk lặp; threshold có refuse-all.
- Splitter kiểm cửa sổ hợp lệ, cache phân biệt endpoint/revision và reranker không
  tải lại cho mỗi cấu hình. Cấu hình sai không lặng lẽ đổi chế độ.
- Không lưu inline credential vào artifact; báo cáo ghi rõ doc/page proxy.
- V002 additive sửa global PUBLIC EXECUTE; V001 giữ nguyên checksum. Cả hai chain
  dùng transaction advisory lock cho thay đổi default chung.
- MinIO attach lỗi chỉ được chấp nhận nếu xác minh đúng policy đã gắn; kiểm chạy
  init lần hai và AI không có quyền ghi/xóa.

Context được cập nhật: `.agent/context/database/schema.md`; hướng dẫn ở
`infrastructure/db/README.md`. Không thay contract endpoint/event của sản phẩm.

## Bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| `eval/.venv/Scripts/python.exe -m pytest -q eval/tests/test_eval.py eval/tests/test_harness_regressions.py --basetemp=eval/.cache/pytest-acceptance-20261025` | 18 passed; chỉ phụ thuộc file thuộc commit V2-05/V2-08 |
| Toàn bộ `eval/tests` với basetemp mới trong repo | 26 passed; gồm phần chuẩn bị dữ liệu chưa commit |
| `ruff check eval/sopilot_eval eval/tests` | Pass |
| `sopilot_eval.infra_check` từ `eval/` | Pass project `sopilot-v2-readiness-20f4d9cf` |
| Compose gốc render với env file trống/credential ngẫu nhiên | Project `sopilot-v2`; volume `sopilot-v2_postgres_data`, `sopilot-v2_minio_data`, không external; network `sopilot-v2-network`; port chỉ bind loopback |
| Runtime tmpfs | Flyway core/rag, role/schema isolation, RLS đọc/ghi cả hai role, function grants, S3 core ghi/xóa, AI chỉ đọc, anonymous 403, init lặp lại đều pass |

Một lần chạy kiểm chứng trước đó báo minio-init exit 1; log của lần đó chưa đủ để
kết luận nguyên nhân. Runner đã bổ sung chẩn đoán có che credential; lần chạy mới
ở project trên pass. Chưa tuyên bố độ ổn định startup qua nhiều lần hoặc kiểm CI.

## Tách commit và giới hạn

Test regression được tách khỏi test dữ liệu/PLAN để commit chạy độc lập trên
baseline đã tracked. Commit chỉ chứa V2-05/V2-08 và nghiệm thu của hai ticket.
PLAN được stage chọn lọc từ HEAD, chỉ cập nhật hai trạng thái/bộ đếm; bản PLAN
33 ticket và các sửa spec có sẵn vẫn giữ trong working tree, không bị commit kèm.
Vì vậy snapshot commit có 27 ticket/4 done/2 review; working tree hiện có
33 ticket/5 done/1 review. `implemented_tickets` đều là 6.

Không đọc `.env`, không reset/prune/xóa hoặc mount volume cũ, không áp migration
lên DB của owner, không push/merge. Bước tiếp theo là dữ liệu V2-06/V2-19,
sau đó V2-20 khi có corpus phù hợp.
