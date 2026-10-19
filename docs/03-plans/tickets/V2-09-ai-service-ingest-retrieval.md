---
id: V2-09
title: "ai-service: worker ingest, embedding, hybrid retrieval, RLS, 4 loại điểm, provider interface"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-03, V2-08, V2-20, V2-22]
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
- [ ] Interface `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) và `RerankProvider` (`local` | `none`); `models.yaml` là nơi duy nhất khai báo model.
- [ ] Hybrid dense + BM25 + RRF, **mọi truy vấn lọc `workspace_id`** (tham số hóa, không f-string) và RLS bật.
- [ ] Bảng `rag.document_access` (ADR-007 §4.5) và endpoint nội bộ để core-api cập nhật; dense và BM25 lọc theo `wrole`/`wdept` **trước** `LIMIT k`; tài liệu thiếu dòng quyền không được truy xuất.
- [ ] Lưu tách `dense_score`, `bm25_score`, `fusion_score`, `rerank_score`; rerank chạy trước ngưỡng; ngưỡng riêng từng chế độ.
- [ ] Worker xử lý job bền: quét job tồn khi khởi động; trạng thái `PROCESSING → READY | FAILED`, thử lại được.
- [ ] Kết quả truy xuất trên corpus của V2-06 khớp harness `eval/` trong sai số đã nêu (kiểm tra cùng dữ liệu).

## 3. Hướng dẫn
- **File:** `services/ai-service/` (CREATE), dùng module của V2-20/V2-22, tham khảo `services/ai-qa-service/src/db/repositories/chunk_repo.py`.
- Migration chunk nằm trong `infrastructure/db/migrations/` (V2-08).

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | RRF, provider mock, ngưỡng theo chế độ | `uv run pytest tests/unit` |
| Integration | Postgres thật: ingest → truy xuất, RLS chặn khi thiếu `workspace_id` | `uv run pytest tests/integration` |

```powershell
./scripts/validate-build.ps1 -Scope ai-qa   # cập nhật script cho service mới trong V2-17
```
