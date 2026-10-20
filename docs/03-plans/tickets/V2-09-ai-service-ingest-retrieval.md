---
id: V2-09
title: "ai-service: worker ingest, embedding, hybrid retrieval, RLS, 4 loại điểm, provider interface"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-21
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-06, V2-08, V2-20, V2-21, V2-22]
blocks: [V2-10, V2-12, V2-14, V2-25]
branch: "feat/ai-qa-v2-ingest-retrieval"
assignee: pair
---

# TICKET V2-09: ai-service (ingest + truy xuất)

## 1. Bối cảnh & Mục tiêu
Service mới `services/ai-service` (FastAPI) thay `ai-qa-service` và `ingestion-service`. Port có chọn lọc embedding và SQL hybrid; sửa các lỗi R1–R5 và AUDIT §4.2. Trích xuất và chunk tách sang V2-20 và V2-22 (owner chốt 2026-10-19 theo [AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md)); ticket này nối chúng vào worker và lưu chunk.

## 2. Tiêu chí Hoàn thành
- [ ] Worker ingest gọi trích xuất (V2-20) và chunk (V2-22); chunk lưu `workspace_id`, `document_id`, `page`, vị trí ký tự, đường dẫn tiêu đề.
- [ ] Lưu `embedding_provider/model/dim/revision` cho mỗi chunk; cache khóa `(model, revision, sha256)`; không cắt bằng `tiktoken`.
- [ ] Migration schema `rag` cho các bảng TECH-V2-ai-service §3.1–§3.4 và `outbox_events`, `processed_requests` (§3.5), hàm `rag.claim_ingestion_job()`; bảng `suggestion_*` để `V2-25`, `message_feedback`/`knowledge_gap_status` để `V2-13`.
- [ ] Interface `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) và `RerankProvider` (`local` | `none`); `models.yaml` là nơi duy nhất khai báo model. `EmbeddingProvider.tokenizer()` trả `docproc.tokens.HFTokenizer` của `V2-22` (TECH-V2-ai-service §1.1), không tạo tokenizer thứ hai.
- [ ] Hybrid dense + BM25 + RRF, **mọi truy vấn lọc `workspace_id`** (tham số hóa, không f-string) và RLS bật.
- [ ] Bảng `rag.document_access` (ADR-007 §4.5) và endpoint nội bộ để core-api cập nhật; dense và BM25 lọc theo `wrole`/`wdept` **trước** `LIMIT k`; tài liệu thiếu dòng quyền không được truy xuất.
- [ ] Lưu tách `dense_score`, `bm25_score`, `fusion_score`, `rerank_score`; rerank chạy trước ngưỡng; ngưỡng riêng từng chế độ.
- [ ] Worker xử lý job bền: quét job tồn khi khởi động; trạng thái `PROCESSING → READY | FAILED`, thử lại được. Phân loại lỗi theo TECH-V2-ai-service §5.1: lỗi tạm thời tự thử lại với backoff `run_after` và không gửi `FAILED` giữa chừng; lỗi tất định `FAILED` ngay với đúng mã; hết lần thử giữ mã của lần cuối (`RETRY_EXHAUSTED` chỉ khi không có mã).
- [ ] Thử lại (owner chốt 2026-10-21, TECH-V2-ai-service §8): `POST /internal/ingestions` cùng `versionId` và `attempt` lớn hơn đưa job `FAILED` về `QUEUED` và chạy lại đúng một lần; gửi lại cùng `attempt` (hoặc job đang chạy/`DONE`) không tạo job. Integration test cả ba nhánh.
- [ ] Ghi `extracted_documents` (Markdown chuẩn, `page_index`, `warnings`, `boilerplate`, `normalizer_version`) chỉ trong transaction kích hoạt (§5.6); callback `READY` gửi `warningCodes` và `attempt`.
- [ ] `GET /ai/v1/documents/{id}/versions/{versionId}/content` theo TECH-V2-ai-service §7.3 (dùng cho FR-14 và FR-31): `404` cho phiên bản chưa kích hoạt, `FAILED`, đã xóa hoặc ngoài quyền (FR-25); trong lúc bản thay thế xử lý trả phiên bản đang hoạt động; offset UTF-16 đúng với chuỗi có ký tự ngoài BMP. Test FR-19/FR-29 phủ endpoint này.
- [ ] Kết quả truy xuất trên corpus của V2-06 khớp harness `eval/` trong sai số đã nêu (TECH-V2-ai-service §6.5: top-10 Jaccard trung bình ≥ 95%), với harness chạy cùng bộ chunk `docproc` và cùng cấu hình; `eval/` chuyển sang import `sopilot_ai.retrieval.lexical` và `fusion` trong cùng thay đổi.

## 3. Hướng dẫn
- **File:** `services/ai-service/` (CREATE), dùng module của V2-20/V2-22, tham khảo `services/ai-qa-service/src/db/repositories/chunk_repo.py`.
- Migration chunk nằm trong `infrastructure/db/migrations/` (V2-08).

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | RRF, provider mock, ngưỡng theo chế độ | `uv run pytest tests/unit` |
| Integration | Postgres thật: ingest → truy xuất, RLS chặn khi thiếu `workspace_id` | `uv run pytest tests/integration` |

```powershell
./scripts/validate-build.ps1 -Scope ai        # scope do V2-20 thêm
./scripts/run-tests.ps1 -Scope ai-service -Type all
```
