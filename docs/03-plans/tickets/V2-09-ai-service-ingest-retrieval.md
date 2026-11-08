---
id: V2-09
title: "ai-service: worker ingest, embedding, hybrid retrieval, RLS, 4 loại điểm, provider interface"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-05
author: "Owner"
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
- [x] Worker ingest gọi trích xuất (V2-20) và chunk (V2-22); chunk lưu `workspace_id`, `document_id`, `page`, vị trí ký tự, đường dẫn tiêu đề.
- [x] Lưu `embedding_provider/model/dim/revision` cho mỗi chunk; cache khóa `(model, revision, sha256)`; không cắt bằng `tiktoken`.
- [x] Migration schema `rag` cho các bảng TECH-V2-ai-service §3.1–§3.4 và `outbox_events`, `processed_requests` (§3.5), hàm `rag.claim_ingestion_job()`; bảng `suggestion_*` để `V2-25`, `message_feedback`/`knowledge_gap_status` để `V2-13`.
- [x] Interface `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) và `RerankProvider` (`local` | `none`); `models.yaml` là nơi duy nhất khai báo model. `EmbeddingProvider.tokenizer()` trả `docproc.tokens.HFTokenizer` của `V2-22` (TECH-V2-ai-service §1.1), không tạo tokenizer thứ hai.
- [x] Hybrid dense + BM25 + RRF, **mọi truy vấn lọc `workspace_id`** (tham số hóa, không f-string) và RLS bật.
- [x] Bảng `rag.document_access` (ADR-007 §4.5) và endpoint nội bộ để core-api cập nhật; dense và BM25 lọc theo `wrole`/`wdept` **trước** `LIMIT k`; tài liệu thiếu dòng quyền không được truy xuất.
- [x] Lưu tách `dense_score`, `bm25_score`, `fusion_score`, `rerank_score`; rerank chạy trước ngưỡng; ngưỡng riêng từng chế độ.
- [x] Sửa 2026-10-21 (TECH-V2-ai-service §5.4, §6.4, §3.3, §3.4): worker truyền `title` và `extracted_meta.docCode` (V2-21) vào chunker; ghi `chunks.lang` từ bước phát hiện ngôn ngữ; `fusion` có `cross_lingual_bm25_factor` (mặc định `1.0`, test `1.0` cho kết quả như RRF thường); migration có `chunks.lang` và `messages.context_sources` (cột dùng ở `V2-10`).
- [x] Sửa 2026-10-21 (audit đầu-cuối theo loại query, owner chốt D2/D11; TECH-V2-ai-service §3.4, §6.3, §6.4): (a) migration `rag.messages` có ngay `refusal_reason`, `route jsonb`, `rewrite_status`, `checks jsonb` và CHECK `refusal_reason` (gộp vào migration của ticket này, **không** viết migration thứ hai); (b) tokenizer BM25 sinh thêm term bỏ dấu `~` cho từ có dấu, `lexical_len` chỉ đếm term gốc, truy vấn không dấu dùng cả term gốc lẫn `~`; (c) `qa/doc_code.py` nhận diện mã tài liệu trong câu hỏi và `retrieval.doc_code_boost` cộng vào `fusion_score` của chunk có `extracted_meta.docCode` khớp; (d) cổng `hybrid` luôn có `dense_score`: ứng viên chỉ có điểm BM25 được tính cosine trực tiếp (`fusion.gate_score`, dùng chung với `eval/`), `retrieval_results.dense_score` đủ cho 25 ứng viên; (e) lệnh quản trị `python -m sopilot_ai.admin reindex` (theo `normalizer_version`, model embedding hoặc tokenizer đổi) và kiểm lúc khởi động: chunk của phiên bản đang hoạt động lệch `(embedding_model, embedding_revision)` đang bật → log `ERROR`, `/health` trả `degraded`. Test: ứng viên chỉ có BM25 vào cổng cho cùng điểm ở harness và service; "quy trinh mua hang" khớp "quy trình mua hàng", câu tiếng Anh không đổi kết quả; `QT-MH-01` được boost; `reindex` đưa phiên bản lệch về khớp.
- [x] Worker xử lý job bền: quét job tồn khi khởi động; trạng thái `PROCESSING → READY | FAILED`, thử lại được. Phân loại lỗi theo TECH-V2-ai-service §5.1: lỗi tạm thời tự thử lại với backoff `run_after` và không gửi `FAILED` giữa chừng; lỗi tất định `FAILED` ngay với đúng mã; hết lần thử giữ mã của lần cuối (`RETRY_EXHAUSTED` chỉ khi không có mã).
- [x] Thử lại (owner chốt 2026-10-21, TECH-V2-ai-service §8): `POST /internal/ingestions` cùng `versionId` và `attempt` lớn hơn đưa job `FAILED` về `QUEUED` và chạy lại đúng một lần; gửi lại cùng `attempt` (hoặc job đang chạy/`DONE`) không tạo job. Integration test cả ba nhánh.
- [x] Ghi `extracted_documents` (Markdown chuẩn, `page_index`, `warnings`, `boilerplate`, `extracted_meta` = metadata SOP của `clean/metadata.py` theo version tài liệu, `normalizer_version`) chỉ trong transaction kích hoạt (§5.6); callback `READY` gửi `warningCodes` và `attempt`.
- [x] `GET /ai/v1/documents/{id}/versions/{versionId}/content` theo TECH-V2-ai-service §7.3 (dùng cho FR-14 và FR-31): `404` cho phiên bản chưa kích hoạt, `FAILED`, đã xóa hoặc ngoài quyền (FR-25); trong lúc bản thay thế xử lý trả phiên bản đang hoạt động; offset UTF-16 đúng với chuỗi có ký tự ngoài BMP. Test FR-19/FR-29 phủ endpoint này.
- [x] Kết quả truy xuất trên corpus của V2-06 khớp harness `eval/` trong sai số đã nêu (TECH-V2-ai-service §6.5: top-10 Jaccard trung bình ≥ 95%), với harness chạy cùng bộ chunk `docproc` và cùng cấu hình; `eval/` chuyển sang import `sopilot_ai.retrieval.lexical` và `fusion` trong cùng thay đổi. Tokenizer (term `~`) và cổng `dense_score` đã được cài vào harness từ `V2-07`, nên đây chỉ là chuyển import, không đổi số liệu RQ.

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

## 5. Tiến độ

**Bước 1/2 (2026-11-04, owner chấp nhận):** owner chốt các quyết định ngoài TECH: policy `definer_*` chỉ cho `sopilot_migrator` để hàm SECURITY DEFINER chạy được dưới `FORCE ROW LEVEL SECURITY`; `TEXT` của docproc → `PROSE` (họ PROSE) hoặc `SECTION`; phiên bản cũ xong sau phiên bản mới `DONE` thì job `CANCELLED`; env mới `SOPILOT_PROFILE`, `SOPILOT_S3_SECURE`, `SOPILOT_INGEST_LEASE_SECONDS`, `SOPILOT_INGEST_BACKOFF_SECONDS`, `SOPILOT_WORKER_POLL_SECONDS`, `SOPILOT_OUTBOX_*`; chưa tạo `suggestion_jobs` (V2-25). Nội dung: migration `rag/V003__rag_tables.sql` (mọi bảng §3.1–§3.5, §7.6, RLS, `claim_ingestion_job`, `claim_outbox_batch`, `stale_active_versions`); `EmbeddingProvider` (`local` | `cloudflare` | `openai_compatible`) đọc `config/models.yaml`, `tokenizer()` trả `docproc.tokens.HFTokenizer`; `retrieval/lexical.py` (term `~`, `lexical_len`); worker ingest nối `docproc` (extract → clean → render → family → chunk, truyền `title` và `docCode`), phát hiện ngôn ngữ, embed có cache `(model, revision, sha256)`, transaction kích hoạt §5.6, phân loại lỗi §5.1, outbox + dispatcher; `POST /internal/ingestions` (token nội bộ, `Idempotency-Key`, thử lại theo `attempt`). Test: 23 unit + 15 integration (Postgres pgvector thật, role `sopilot_ai_app`).

**Bước 2/2 (2026-11-04, owner nghiệm thu 2026-11-05):** `retrieval/access_filter.py` (`allowed_cte()` duy nhất, tham số hóa, `workspace_id` tường minh cạnh RLS); `retrieval/search.py` (dense có `hnsw.iterative_scan`, BM25 trong SQL với `N`/`df`/`avgdl` trên tập được đọc, cosine trực tiếp cho ứng viên chỉ có BM25, docCode, text cho rerank, tất cả lọc trước `LIMIT`); `retrieval/fusion.py` (RRF, `cross_lingual_bm25_factor`, `doc_code_boost`, `gate_score`, ngưỡng theo chế độ); `retrieval/retriever.py` (4 điểm tách riêng, rerank trước cổng, `hybrid` luôn có `dense_score`); `qa/doc_code.py`; `RerankProvider` (`local` | `none`); `retrieval_results.save`; `PUT /internal/document-access/{id}`, `DELETE /internal/documents/{id}`; `GET /ai/v1/documents/{id}/versions/{versionId}/content` (JWT RS256 qua JWKS core-api, `404` chung, offset UTF-16); `/health` `degraded` và log `ERROR` khi lệch model/normalizer; `python -m sopilot_ai.admin reindex [--all] [--dry-run]` (job `reindex` không gửi callback). `eval/` import tokenizer, `BM25` và fusion từ `sopilot_ai.retrieval` (hành vi harness không đổi, đã so từng hàm). Test: 24 unit + 12 integration mới (tổng 178). Đối chiếu §6.5 (`sopilot_eval.service_parity`, sop-main 105 câu, 575 chunk docproc, bge-m3): Jaccard top-10 trung bình dense 1,000, bm25 0,993, hybrid 0,995, hybrid-xl0.3 0,997; mọi khác biệt ở hạng 10 do phá hòa điểm (chunk trùng nội dung giữa hai tài liệu) hoặc ứng viên BM25 điểm 0 mà harness vẫn xếp hạng.

**Nghiệm thu 2026-11-05:** owner chấp nhận bước 2/2, chuyển `done`. Code ai-service (`services/ai-service/`, migration `rag/V003__rag_tables.sql`) và thay đổi import ở `eval/` **chưa commit** tại thời điểm nghiệm thu; commit trên nhánh `feat/ai-qa-v2-ingest-retrieval`.
