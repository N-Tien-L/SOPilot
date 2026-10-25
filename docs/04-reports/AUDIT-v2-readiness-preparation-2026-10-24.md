---
id: AUDIT-V2-READINESS-PREPARATION-2026-10-24
title: "Chuẩn bị triển khai V2: review nền, tách XL và công cụ dữ liệu"
type: quality-audit
status: final
created: 2026-10-24
updated: 2026-10-24
author: "Codex"
milestone: "V2: SOPilot MVP"
scope: [docs, eval, infra]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/03-plans/PLAN-V2-sopilot-mvp.md
  - docs/03-plans/tickets/V2-04-close-legacy-backlog.md
  - docs/03-plans/tickets/V2-05-eval-harness.md
  - docs/03-plans/tickets/V2-06-multilingual-eval-dataset.md
  - docs/03-plans/tickets/V2-08-flyway-and-compose.md
  - docs/03-plans/tickets/V2-19-sop-extraction-corpus.md
---

# Kết quả chuẩn bị V2 ngày 2026-10-24

Hoàn tất nhóm việc owner giao trong chat: review backlog/harness/hạ tầng, chia ticket XL và chuẩn bị công cụ nhãn dữ liệu. Đây không phải nghiệm thu MVP, corpus nghiên cứu hay kết quả RQ. Nhánh `chore/tests-v2-readiness`, bắt đầu từ HEAD `36e2cbb`; không commit/push. Những thay đổi PRD/TECH/ticket/config đã có từ đầu phiên được giữ nguyên và bổ sung tại chỗ.

## 1. Tiến độ và phạm vi

| Phần | Đã làm | Trạng thái |
|---|---|---|
| V2-04 | Review trạng thái/ánh xạ 12 ticket M1/NEXT, bộ đếm PLAN lịch sử, thư mục cũ và ancestry commit; sửa chỉ dẫn V1 lỗi thời trong docs hub | `done` sau review tài liệu |
| PLAN | Tách V2-11 thành identity/JIT (11), workspace/session (29), lời mời/OWNER (30); V2-15 thành khung/chat (15), upload (31), viewer (32), quản trị (33); giữ các AC | 33 ticket, không thêm tính năng |
| V2-05 | Review baseline, sửa lỗi, test hồi quy và smoke offline | Giữ `review`: delta mới chưa commit/peer review |
| V2-08 | Sửa default function grants, MinIO init; kiểm chứng Docker cô lập | Giữ `review`: delta mới chưa commit/peer review; DB bền của owner chưa kiểm |
| V2-06 | Contract/validator và 5 câu draft EN/VI trên một tài liệu synthetic | `in-progress`; chưa chốt quy mô/corpus thật hoặc duyệt nhãn |
| V2-19 | Contract/validator/scorer, hai MD synthetic VI/EN, predictions ví dụ | `in-progress`; chưa có corpus/PDF thật hoặc nhãn duyệt |

PLAN hiện có **3 done, 3 review, 2 in-progress, 25 todo**; `implemented_tickets=6`. DAG có **75 cạnh**, không chu trình; `depends_on`, `blocks`, bảng và bộ đếm khớp. V2-18 chờ mọi ticket qua dependency closure, gồm V2-27/V2-28 và các phần frontend mới. Không chuyển ticket code mới sang `done` chỉ vì test xanh.

## 2. Phát hiện và sửa lỗi

### Eval harness

- nDCG trước đây cộng điểm cho nhiều chunk trúng cùng một expected target, có thể vượt 1. Sửa chỉ thưởng target mới; recall bao phủ mọi target khớp.
- Splitter thiếu kiểm `size/overlap`, có thể không tiến khi overlap không hợp lệ; một đoạn dài có thể vượt size. Thêm kiểm tham số và giới hạn cửa sổ.
- Reranker dùng `dict.setdefault` với constructor khiến model bị tải lại dù key tồn tại. Chuyển sang kiểm cache trước constructor, có regression test bằng model giả.
- Cache embedding OpenAI-compatible thiếu endpoint trong identity; bổ sung endpoint. Local cache namespace ghi revision/query prefix/cap; không tái dùng cache cũ khác provenance.
- Refusal sweep thiếu điểm refuse-all khi score trùng; thêm threshold lớn hơn max, không làm tròn threshold trước áp dụng.
- Retriever sai chính tả và thiếu reranker không còn lặng lẽ chạy cấu hình khác. `k` và corpus/questions rỗng được kiểm; run ID thêm suffix chống ghi đè cùng giây.
- Inline `api_key` có thể lọt vào config lưu trong run artifact; đổi sang `api_key_env`, không đọc `.env` hay ghi credential vào artifact.
- Nhóm báo cáo thêm `query_types`. Kết quả CLI ghi rõ `document_page_proxy` và character chunking thăm dò; yêu cầu `docproc` sẽ lỗi rõ ràng thay vì chạy splitter cũ.

**Giới hạn:** chưa có scorer span-aware, mapping sau truncation hay `docproc`. BM25 term bỏ dấu, RQ chính thức và hiệu chỉnh ngưỡng còn thuộc V2-07/V2-22. Không chạy lại BGE/reranker nặng, gọi LLM hay kết luận chất lượng nghiên cứu trong đợt này.

### Hạ tầng

- `ALTER DEFAULT PRIVILEGES ... IN SCHEMA ... REVOKE EXECUTE` trong V001 không bỏ global PUBLIC EXECUTE mặc định. Thêm **V002 cho core và rag**, revoke global default và sửa helper hiện có; giữ explicit grants cho app roles, giữ nguyên V001. Hai chain serialize thay đổi global bằng transaction advisory lock `24082026`.
- Bỏ `|| true` vô điều kiện sau MinIO policy attach. Client đã ghim trả nonzero nếu policy đã được gắn; script chỉ chấp nhận khi `mc admin user info --json` xác minh đúng policy hiện hành, còn lỗi thật làm init thất bại. Không cần grep/jq ngoài image. Kiểm cả lần init thứ hai.
- Runner `eval/sopilot_eval/infra_check.py` dùng source Compose/images/migrations/scripts thật nhưng thay storage/network/ports bằng cấu hình kiểm thử riêng. Credential ngẫu nhiên chỉ trong environment con, không đọc `.env`, không hiện credential trong lỗi.

Context cập nhật cùng thay đổi: **`.agent/context/database/schema.md`**; hướng dẫn migration/verification ở **`infrastructure/db/README.md`**. Không đổi endpoint, event hoặc RBAC sản phẩm. V002 chưa áp lên DB của owner.

## 3. Bằng chứng kiểm tra

Lệnh từ repo root trừ khi ghi `eval/`:

| Kiểm tra | Kết quả |
|---|---|
| `eval/.venv/Scripts/python.exe -m pytest -q eval/tests --basetemp=eval/.cache/pytest-readiness-final` | 26 passed; gồm 5 test cũ và 21 ca mới/parameterized |
| `ruff check eval/sopilot_eval eval/tests` | Pass |
| `eval/.venv/Scripts/python.exe -m compileall -q eval/sopilot_eval eval/tests` | Pass |
| Trong `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml` | Xuất đủ 4 artifact; smoke run `20261024-102051-10f78912`, không phải số liệu nghiên cứu |
| Trong `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.plan_check` | 33 ticket/75 cạnh, counters/table/reverse deps/DAG/closure khớp |
| Trong `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset wadatasets/annotation-example` | 1 tài liệu, 2 span, 5 câu; dev 2/test 3; hợp lệ cấu trúc |
| Trong `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.extraction --dataset ../datasets/extraction/example --predictions ../datasets/extraction/example/predictions.example.jsonl --out .cache/extraction-example.json` | Chấm riêng 2 nhóm family/language; thời gian/RAM chưa đo là null |
| Hai validator với `--require-reviewed` | Exit 1 đúng kỳ vọng vì labels draft |
| Trong `eval/`: `./.venv/Scripts/python.exe -m sopilot_eval.infra_check` | Pass project `sopilot-v2-readiness-697d367c`: Flyway hai chain, roles/schema, RLS đọc/ghi cả hai app, function grants, core S3 ghi/xóa, AI chỉ đọc, anonymous 403, init lặp lại |
| `./scripts/pre-commit-check.ps1` | Pass với auto-load `.env` tắt, env file trống và biến bắt buộc được gán giá trị giả ngẫu nhiên cho Compose config; không gọi stack V1 |
| `git diff --check` | Pass |
| `./scripts/check-conventions.ps1 -Scope infra` | Exit 1 chỉ do nhánh `chore/tests-v2-readiness` khác prefix scope infra; thay đổi nhiều scope là có chủ đích |

Pre-commit hiện không chạy test cho `eval/` và bỏ qua untracked files. Vì vậy đã chạy pytest/ruff trực tiếp, đồng thời quét bổ sung code/data mới và thay đổi để kiểm debug statement/TODO không ticket/environment file. Không gọi `validate-build` với scope không được hỗ trợ; không chạy full stack hoặc test các service V1.

Lỗi tmpdir pytest trong sandbox được xử lý bằng basetemp mới nằm trong `eval/.cache/`; không sửa temp directory ngoài repo. Các lần thử runner đầu đã phát sinh anonymous volume `/data` từ image minio-init; runner cuối dùng tmpfs cả ở đó. Không prune hoặc xóa volume Docker, kể cả volume phát sinh từ các lần thử. Project kiểm chứng cuối đã được dừng bằng `down` không `-v`; không mount volume V1/V2 của owner.

## 4. Dữ liệu và bước kế tiếp

- V2-06: xem `eval/datasets/README.md`, mẫu `annotation-example/`. Validator kiểm quote/hash/offset code-point, AND/OR evidence, nhãn query, provenance và leakage dev/test; không thể thay người duyệt nội dung hoặc nhận ra mọi trùng nghĩa.
- `.gitattributes` giữ Markdown corpus ở LF trên Windows để checksum/offset không đổi sau checkout; không áp text normalization lên PDF.
- V2-19: xem `datasets/extraction/README.md`, mẫu `example/`. LCS heading và exact table/span matching là kiểm cấu trúc; đếm regex tham chiếu chỉ là candidates. Peak RAM toàn file không chia cho số trang; RAM từng trang cần adapter đo thật.
- Chưa thu corpus GitLab/SOP thật hoặc tạo nhãn gold. Owner còn chốt quy mô, nguồn/giấy phép và duyệt nhãn; tập con PDF cho V2-20 chưa sẵn sàng.
- Những sửa đổi code/hạ tầng mới vẫn cần commit và review trước nghiệm thu. Khi có dữ liệu và gate nền đã qua, tiếp tục V2-20; không coi synthetic fixtures là bằng chứng Docling đã chạy.
