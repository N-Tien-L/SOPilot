---
id: HANDOFF-WAVE1-2026-11-11
title: "Bàn giao Wave 1 (V2-13, V2-25): triển khai, kiểm thử và điểm cần duyệt"
status: draft
created: 2026-11-11
updated: 2026-11-11
type: handoff
scope: [ai-qa, user, infra, tests]
milestone: V2
author: "Owner"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-13-feedback-and-knowledge-gaps.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-25-async-metadata-suggestion.md
  - docs/architecture/components/ai-service.md
  - docs/architecture/components/core-api.md
---

# Bàn giao Wave 1: V2-13 và V2-25

Báo cáo này để agent khác (hoặc chủ dự án) rà soát mà không cần lịch sử hội thoại. Trạng thái
ticket **không** đổi: cả hai vẫn `todo` cho đến khi chủ dự án duyệt bằng chứng. Thay đổi nằm trong
working tree, chưa commit.

## 1. Tóm tắt

| Ticket | Trạng thái sau phiên | Ghi chú |
|---|---|---|
| V2-13 phản hồi và khoảng trống tri thức | Code xong, IT xanh. Đã thêm vào `tenant-isolation.yml`. | Chưa đánh dấu done. |
| V2-25 gợi ý metadata chạy nền | Code hai phía (ai-service + core-api), IT xanh. | Chưa chạy thật với khóa Groq; chưa đo p50/p95. |
| V2-27 semantic router | Chưa làm. | Cần bộ nhãn 300–500 câu do chủ dự án duyệt. |
| V2-16 demo + compose một lệnh | Chưa làm. | Cần Dockerfile và thay đổi compose (rule 8, hỏi trước). |
| V2-28 bộ kiểm SOP tiếng Việt | Bị chặn. | Người được giao là `owner`. |

## 2. Kết quả kiểm chạy

| Phạm vi | Lệnh | Kết quả |
|---|---|---|
| ai-service lint | `uv run ruff check src tests` | All checks passed |
| ai-service unit | `uv run pytest tests/unit` | 559 passed, 3 skipped, 15 xfailed |
| ai-service integration (Docker pgvector) | `uv run pytest tests/integration` | 134 passed |
| ai-service migration | `./scripts/check-migrations.ps1` | passed (rag V004, core V010 gồm trong kiểm) |
| ai-service IT mới | `test_feedback_isolation.py` (9), `test_suggestions.py` (10) | 19 passed |
| core-api unit | `./mvnw test` | 126 passed, gồm `ArchitectureTest` |
| core-api IT mới | `DocumentSuggestionIT` | 7 passed |
| core-api IT đã có | `DocumentLifecycleIT` | 18 passed (sau khi đổi `suggest.enabled` thành `true`) |
| core-api tenant | `TenantIsolationApiIT`, `TenantIsolationIT` | 17 passed (đã thêm ca cho `PUT .../suggestions`) |
| docs | `./scripts/check-docs.ps1` | passed |

Chưa chạy: `./mvnw verify` đầy đủ (mọi IT của core-api). Chưa mở trình duyệt (không có UI trong wave này).

## 3. V2-13: thay đổi

Bảng và cột đã có trong migration `rag/V003`, nên không có migration mới.

- `services/ai-service/src/sopilot_ai/feedback/gaps.py`: tiêu chí khoảng trống dưới dạng hằng số. SQL được sinh từ đây.
- `feedback/repository.py`: SQL phản hồi, danh sách và giải quyết.
- `api/feedback.py`: ba endpoint. Đăng ký trong `api/app.py`.
- `tests/integration/test_feedback_isolation.py`: 9 test.
- `.github/workflows/tenant-isolation.yml`: thêm `tests/integration/test_feedback_isolation.py` vào bước ai-service (theo yêu cầu chủ dự án).

Endpoint:
- `PUT /ai/v1/messages/{id}/feedback` `{vote: -1|1, comment?}`: 204. Chỉ chủ hội thoại, chỉ tin ASSISTANT. Một phiếu mỗi người mỗi câu.
- `GET /ai/v1/knowledge-gaps?status=open|resolved`: OWNER/ADMIN; MEMBER nhận 403. Câu hỏi đã che PII bằng `qa/pii.py`. Không trả user id và không trả nội dung câu trả lời.
- `POST /ai/v1/knowledge-gaps/{id}/resolve`: OWNER/ADMIN; idempotent; 404 nếu không phải khoảng trống.

Tiêu chí khoảng trống: `refusal_reason` thuộc `NO_EVIDENCE`/`GENERATOR_NOT_FOUND`, hoặc `ANSWERED` với `citationCount = 0`, hoặc có phiếu -1. Loại `TEMPLATE`, `REFUSED_GUARD`, `QUOTA_EXCEEDED`, `OUT_OF_SCOPE`, `INPUT_INVALID`.

## 4. V2-25: thay đổi

### 4.1 Luồng

1. Ingest xong, `ingest/handler.py` đưa job gợi ý vào hàng đợi trong cùng transaction làm phiên bản thành READY (chỉ khi payload có `suggest.enabled`).
2. Worker (`worker.py`) chạy `suggest/runner.py.drain` sau mỗi lượt ingest, rồi đẩy outbox.
3. Runner: đọc văn bản đã trích xuất (không đọc file trên S3); luật lấy tiêu đề; tra cache; gọi model Groq một lần, thử lại đúng một lần; lỗi thì `RULES_FALLBACK`.
4. Kết quả ghi vào `rag.suggestion_jobs` và đưa vào outbox `SUGGESTIONS_READY`.
5. Dispatcher gửi `PUT /internal/documents/{id}/suggestions` tới core-api.
6. core-api (`document/SuggestionService.java`) lưu bản gợi ý theo phiên bản và chỉ áp dụng khi phiên bản đó là hiện hành. Mỗi trường chỉ đổi khi nguồn không phải `USER`.

### 4.2 Model và cấu hình (theo yêu cầu chủ dự án)

- `config/models.yaml`: `providers.groq` (base URL `https://api.groq.com/openai/v1`, khóa `SOPILOT_GROQ_API_KEY`) và `llm.suggest` với model `qwen/qwen3.8-27b`, `timeout_s` 20, RPM 30, TPM 60 000, `extra_body: {reasoning_format: hidden}`.
- `.env.example`: thêm `SOPILOT_GROQ_API_KEY=<groq-api-key>` và các biến tùy chọn đã chú thích. Không đọc hoặc sửa `.env`.
- `providers/llm.py`: `build_chain` đọc `timeout_s` của từng tác vụ. Các tác vụ cũ giữ 120 s.
- Đã kiểm: `build_chain(config, "suggest")` cho ra `groq`, `qwen/qwen3.8-27b`, `https://api.groq.com/openai/v1`, 30 RPM, 60 000 TPM, timeout 20 s.

### 4.3 Migration

- `infrastructure/db/migrations/rag/V004__suggestion_claim.sql`: chính sách `definer_suggestions` cho chủ sở hữu, hàm `rag.claim_suggestion_job(lease)` SECURITY DEFINER với `search_path`, REVOKE PUBLIC, GRANT cho `sopilot_ai_app`.
- `infrastructure/db/migrations/core/V010__document_suggestions.sql`: bảng `core.document_suggestions` (khóa `version_id`, FK tới `core.documents`), RLS FORCE, GRANT SELECT/INSERT/UPDATE cho `sopilot_core_app`.

### 4.4 Mã thay đổi

ai-service:
- Mới: `suggest/__init__.py`, `suggest/rules.py` (thuần), `suggest/llm.py` (thuần: prompt, kiểm đầu ra, khóa cache), `suggest/runner.py` (IO), `db/repositories/suggestions.py`.
- Sửa: `ingest/handler.py` (enqueue), `worker.py` (`_suggest_deps`, drain), `providers/llm.py` (timeout), `config/models.yaml`, `.env.example`.
- Test: `tests/unit/test_suggest.py` (16), `tests/integration/test_suggestions.py` (10).

core-api:
- Mới: `document/SuggestionService.java`, migration `core/V010`, `DocumentSuggestionIT.java` (7 test).
- Sửa: `document/DocumentRepository.java` (`upsertSuggestion`), `document/InternalDocumentController.java` (PUT), `document/DocumentService.java` (`suggestSpec`, `ingestPayload` nhận tham số `suggest`), `tag/TagService.java` (`names`), `DocumentLifecycleIT.java` (kỳ vọng `suggest.enabled = true`), `tenancy/TenantIsolationApiIT.java` (ca mới cho PUT).

## 5. Quyết định cần rà soát

1. **Groq cho gợi ý.** ADR-006 §4.4 và `CLAUDE.md` đã bỏ Groq khỏi sinh câu trả lời và giám khảo. Gợi ý không phải câu trả lời, nên đưa Groq vào đây là quyết định của chủ dự án; tài liệu ADR/PLAN cần ghi chú lại.
2. **Model id chưa kiểm chứng.** `qwen/qwen3.8-27b` chỉ đến từ yêu cầu của chủ dự án. Chưa gọi được `GET /models` vì không có khóa. Nếu id sai, mọi job sẽ rơi về `RULES_FALLBACK` và log sẽ ghi `suggest_model_failed`.
3. **Thứ tự xử lý.** Suggestion chạy đồng bộ trong vòng lặp worker sau ingest. Mỗi job có thể chờ tới khoảng 40 s (hai lần gọi, mỗi lần 20 s). Trong lúc đó ingest tiếp theo phải đợi. Nếu thành vấn đề, tách thành tiến trình riêng.
4. **Tag.** Model chỉ được gắn tag đã có trong workspace, không tạo tag mới. `proposedCategoryName` chỉ được lưu, không tạo category.
5. **Tiêu đề.** Tiêu đề gợi ý là heading đầu tiên của Markdown, và sẽ thay tên file khi nguồn tiêu đề không phải `USER`. Đây là hành vi mới cho người dùng, nên chủ dự án cần xác nhận.
6. **Hạn mức Groq.** RPM/TPM đặt ở 30/60 000 là giá trị tạm, chưa đo.
7. **Đo lường chưa đủ.** Ticket yêu cầu `t_upload_ack`, `t_ready`, p50/p95. Hiện chỉ ghi `t_suggest_ms`, `llm_ms`, `tokens_in/out` (ước lượng, không phải số thật), `fallback`, `cache_hit`, `attempts`. `t_upload_ack` và `t_ready` chưa được ghi.
8. **Không có kiểm chứng trực tiếp với Groq.** Toàn bộ test dùng `ScriptedChain`. Cần chạy một lần với khóa thật trước khi tick tiêu chí.

## 6. Chưa làm và lý do

- **V2-27**: cần bộ nhãn định tuyến 300–500 câu do chủ dự án duyệt. Không có bộ đó thì không thể đặt ngưỡng hay kiểm tiêu chí ≤ 2%.
- **V2-16**: cần Dockerfile core-api/ai-service và thay đổi `docker-compose*.yml`. Quy tắc dự án yêu cầu hỏi trước.
- **V2-28**: người được giao là `owner`; cần duyệt bộ 30–40 câu và tài liệu nguồn.

## 7. Việc tiếp theo đề xuất

1. Chủ dự án đặt `SOPILOT_GROQ_API_KEY` trong `.env` cục bộ, rồi chạy `GET /models` để xác nhận id, sau đó chạy thử một tài liệu thật và ghi số đo.
2. Quyết định về thứ tự xử lý (mục 5.3) và về tiêu đề (mục 5.5).
3. Duyệt bằng chứng rồi mới đánh dấu V2-13 và V2-25 là `done`; cập nhật PLAN.
4. Bắt đầu V2-16 khi được duyệt thay đổi compose.
