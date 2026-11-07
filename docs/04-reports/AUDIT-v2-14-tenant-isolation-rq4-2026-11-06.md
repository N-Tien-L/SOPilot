---
id: AUDIT-v2-14-tenant-isolation-rq4-2026-11-06
title: "V2-14: cách ly tenant trong CI và RQ4 (độ trễ RLS)"
status: draft
created: 2026-11-06
updated: 2026-11-06
type: audit
scope: tests
verdict: pending-owner-review
milestone: "V2: SOPilot MVP"
---

# V2-14: cách ly tenant (FR-19) và RQ4

## 1. Cách ly tenant

Ba lớp, đều chạy cục bộ trên Postgres thật với role ứng dụng thật (`sopilot_core_app`, `sopilot_ai_app`, `NOBYPASSRLS`):

| Lớp | Nơi | Kết quả |
|---|---|---|
| Database, mọi bảng tenant của `core` và `rag` (tìm từ catalog) | `tests/tenant-isolation/` | 31 test xanh |
| API core-api, 3 workspace có chuỗi bí mật trong tài liệu, phòng ban, thành viên, audit | `TenantIsolationApiIT` | 8 test xanh |
| Truy xuất ai-service (lọc quyền trước `LIMIT`, xóa tài liệu) | `test_retrieval.py` | 12 test xanh (một lần chạy đầu fail ở `test_hybrid_candidates_always_have_dense_score`, ba lần chạy lại đều xanh; test có sẵn, không thuộc thay đổi này, chưa điều tra) |

Phát hiện khi viết test: `rag.processed_requests` là bảng không có `workspace_id` ngoài danh sách bảng toàn cục. Đây là ngoại lệ đã ghi trong TECH-V2-ai-service §3.5 (chỉ chứa UUID idempotency); đã đưa vào `GLOBAL_TABLES` kèm lý do. Từ nay bảng mới không có `workspace_id` làm test đỏ cho tới khi được duyệt.

### Kiểm chứng test có phát hiện rò rỉ

- `ISOLATION_MUTATION=disable-rls` (tắt RLS mọi bảng tenant): 23 test fail, 8 xanh. CI yêu cầu lần chạy này phải đỏ.
- Đột biến thủ công ở API (2026-11-06): bỏ `d.workspace_id = ?` khỏi truy vấn danh sách tài liệu và tắt RLS trên `documents`, `document_versions` -> `TenantIsolationApiIT` fail 2 test với "workspace A leaked a secret of B". Đã khôi phục mã.
- Test `test_detector_*` tạo bảng không RLS: detector báo rò, bật RLS thì im.

### Chưa phủ

- Hỏi đáp, hội thoại, feedback qua API: endpoint chưa tồn tại (V2-10, V2-13). Bảng `rag.conversations`, `messages`, `message_feedback`, `message_citations` đã được phủ ở lớp database.
- Workflow `.github/workflows/tenant-isolation.yml` đã viết nhưng **chưa có run xanh trên GitHub**; các lệnh tương đương đã chạy cục bộ.

## 2. RQ4: chi phí RLS trên đường truy xuất

`eval/rq4_rls_latency.py`. Cùng dữ liệu, cùng truy vấn, hai kết nối xen kẽ (đổi thứ tự mỗi truy vấn), 30 truy vấn khởi động bỏ đi. Đơn vị đo là một transaction truy xuất: `search.dense` rồi `search.bm25` của ai-service (hàm thật), `pool=50`.

- `app-filter`: kết nối superuser (bỏ qua RLS), chỉ có lọc `workspace_id` + quyền đọc của ứng dụng.
- `app+rls`: kết nối `sopilot_ai_app`, cùng SQL, cộng policy RLS trên mọi bảng chạm tới.

Dữ liệu tổng hợp: vector đơn vị ngẫu nhiên 1024 chiều, từ vựng Zipf 3.000 từ, 5 workspace, `pgvector/pgvector:0.8.0-pg16` trong Docker Desktop. Đo đường đi qua database, **không** đo chất lượng truy xuất.

| Quy mô | Giai đoạn | app-filter p50 / p95 (ms) | app+RLS p50 / p95 (ms) | Chênh p50 | Chênh p95 |
|---|---|---:|---:|---:|---:|
| 10.000 chunk (5 x 2.000) | dense | 13,36 / 15,75 | 13,13 / 15,77 | -1,7% | +0,1% |
| | bm25 | 28,17 / 50,66 | 28,86 / 50,63 | +2,5% | -0,1% |
| | tổng | 44,21 / 66,46 | 45,12 / 65,89 | +2,1% | -0,9% |
| 30.000 chunk (5 x 6.000) | dense | 34,90 / 41,54 | 34,30 / 41,78 | -1,7% | +0,6% |
| | bm25 | 129,75 / 271,21 | 132,49 / 265,33 | +2,1% | -2,2% |
| | tổng | 168,13 / 308,08 | 169,00 / 296,20 | +0,5% | -3,9% |

Top-10 của hai chế độ giống hệt nhau ở 300/300 truy vấn mỗi quy mô; một workspace không có dữ liệu nhận 0 dòng.

**Kết luận:** RLS thêm khoảng +0,5% đến +2% ở p50 và không phân biệt được với nhiễu ở p95 (dấu âm xuất hiện ở cả hai chiều), ở hai quy mô. Với dữ liệu này, RLS không phải là lý do để bỏ lớp bảo vệ thứ hai.

**Giới hạn:** dữ liệu tổng hợp; một máy, một lần chạy mỗi quy mô (p95 và p99 của BM25 có đuôi dài, chênh dưới nhiễu); `retrieval` chưa có reranker và chưa có LLM; số tuyệt đối phụ thuộc máy, chỉ so sánh hai chế độ. Không đo ở quy mô lớn hơn 30.000 chunk. Một lần chạy 30.000 chunk đầu tiên bị hủy vì có hai lần chạy chồng nhau làm nhiễu phép đo; số ở trên là lần chạy sau, chạy một mình.

Chạy lại: `cd eval && uv run python rq4_rls_latency.py --workspaces 5 --chunks 6000 --queries 300`. Kết quả máy-đọc nằm ở `eval/results/rq4-*/` (thư mục này bị gitignore).
