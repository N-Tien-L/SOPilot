---
id: AUDIT-V2-BASELINE-ANALYSIS
title: "Phân tích nền cho V2: tính năng, auth, model AI, truy xuất và đánh đổi"
type: audit
status: final
created: 2026-10-17
updated: 2026-11-08
author: "Owner"
milestone: "V2: SOPilot MVP"
scope: [all]
verdict: FAILED
---

# PHÂN TÍCH NỀN CHO V2

> **Mã báo cáo:** `AUDIT-V2-BASELINE-ANALYSIS` | **Ngày:** `2026-10-16 → 2026-10-17` | **Kết luận:** `FAILED`. Mã nguồn hiện tại không đáp ứng mục tiêu V2 (đa tổ chức, 0 USD/tháng) nếu không thiết kế lại.
>
> Báo cáo này ghi lại các phân tích đã dẫn tới [PRD-V2](../product/prd-v2-sopilot-mvp.md), [ADR-004](../architecture/decisions/adr-004-two-service-architecture.md), [ADR-005](../architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md) và [ADR-006](../architecture/decisions/adr-006-free-tier-providers-and-environments.md). Đây là phân tích bằng cách đọc code và tài liệu; **chưa chạy test nào** trong đợt này.

---

## 1. Tóm tắt

- **Mục tiêu mới của owner:** SOPilot phục vụ nhiều tổ chức (từ cá nhân, startup tới doanh nghiệp), đăng nhập Google JIT. Dự án nhắm tới CV (AIE bằng Python + SWE bằng Java) và báo cáo nghiên cứu ở trường, chưa nhắm thương mại hóa. Chi phí mục tiêu 0 USD/tháng. Rebuild ngay trong repo này.
- **Kết luận chính:**
  1. Hệ thống không có khái niệm tenant, nên có nguy cơ rò dữ liệu chéo tổ chức (mục 3).
  2. Kiến trúc 8 service + RabbitMQ + Redis không host miễn phí được (mục 2).
  3. Phần lớn model LLM đang cấu hình **đã bị nhà cung cấp tắt** (mục 4).
  4. Reranker chưa bao giờ được nối vào pipeline, và điểm số truy xuất bị trộn thang đo (mục 5).
  5. Free tier của Jina, MinIO community, Hugging Face Spaces và Oracle đều có vấn đề. Lựa chọn thay thế được ghi ở ADR-006.

---

## 2. Phân tích tính năng (giữ hay cắt)

Chi tiết phạm vi nằm ở PRD-V2 §5. Lý do chính của từng nhóm:

| Nhóm | Quyết định | Lý do |
|---|---|---|
| Hỏi đáp có trích dẫn, từ chối có căn cứ | Giữ, làm lõi | Đây là giá trị cốt lõi và là đối tượng của nghiên cứu (RQ1–RQ3) |
| Workspace, membership, lời mời, gia nhập theo domain | Thêm mới | Bắt buộc để phục vụ nhiều tổ chức và người dùng đơn lẻ |
| Roster HR, phòng ban, access rule theo phòng ban | Cắt | Chặn người dùng đơn lẻ; một doanh nghiệp có thể dùng nhiều workspace thay thế |
| Mật khẩu, OTP, quản lý phiên | Cắt | Chỉ đăng nhập Google; giảm bề mặt tấn công |
| OnlyOffice, so sánh version, analytics, export, gợi ý metadata | Cắt | Không thuộc lõi; tốn công bảo trì và tốn hạ tầng |
| Intent classification nhiều tầng, chọn model LLM từ UI | Cắt | Tốn 5–6 lần gọi LLM cho mỗi câu hỏi và làm cạn quota miễn phí (mục 4.3) |
| Eval harness, bộ test cách ly tenant | Thêm mới | Cần số liệu để nộp nghiên cứu và để chứng minh 0 rò rỉ |

---

## 3. Auth và tenancy (code tại 2026-10-16)

**Điểm tốt, nên port sang V2:**
- `GoogleTokenVerifierService` kiểm tra RS256 qua JWKS, `iss`, `aud`, `exp`, `email_verified`.
- Liên kết danh tính theo `(issuer, sub)` trong `core.external_identities` (`012_google_identities.sql`), không ghép theo email.
- `insertIfAbsent` chống race, khóa roster bằng `FOR UPDATE`, phát hiện refresh token bị dùng lại.

**Vấn đề:**

| # | Vấn đề | Vị trí | Mức độ |
|---|---|---|---|
| A1 | Không có tenant/organization ở schema, JWT hay spec | Toàn hệ thống | Nghiêm trọng |
| A2 | Truy xuất RAG chỉ lọc theo role/phòng ban/user, không theo tổ chức, nên có thể rò tài liệu chéo | `ai-qa-service/src/db/repositories/chunk_repo.py` | Nghiêm trọng |
| A3 | `department_id` được ghép vào SQL bằng f-string | `chunk_repo.py:49` | Cao |
| A4 | Email trong roster unique toàn cục | `010_employee_roster.sql` | Cao (với đa tổ chức) |
| A5 | Bắt buộc có tên trong roster mới đăng nhập được, nên người dùng đơn lẻ bị chặn | `AuthService.java:196-260`, `EmployeeRosterService.admitGoogleLogin` | Cao |
| A6 | Hai luồng auth song song (Google và password/OTP); dùng password hash giả `GOOGLE_OAUTH_JIT_UNUSABLE_PASSWORD` | auth-service | Trung bình |
| A7 | Cả auth-service lẫn user-service đều ghi `core.users` | auth-service, user-service | Trung bình |
| A8 | `e.getMessage()` bị trả thẳng cho client | auth-service | Trung bình |
| A9 | Không kiểm tra `nonce` của Google ID token | `GoogleTokenVerifierService` | Trung bình |

Hướng xử lý: ADR-005 (workspace là tenant, lọc ở ứng dụng + RLS, token gắn workspace).

---

## 4. Model AI đang dùng trong code

### 4.1 Bảng kiểm kê (đối chiếu trang deprecation chính thức ngày 2026-10-17)

| Nơi dùng | Model | Trạng thái | Thay thế đề xuất |
|---|---|---|---|
| Lọc độc hại, phân loại ý định, trả lời ngắn, viết lại câu hỏi, sinh tiêu đề (`ai-qa-service/src/config/settings.py`, `services/pipeline/*.py`) | Groq `llama-3.1-8b-instant` | ❌ Groq ghi tắt cho gói free/developer từ 2026-08-16 | `openai/gpt-oss-20b` |
| LLM dự phòng (`services/generation/model_registry.py`, `llm_client.py`); gợi ý metadata (`ingestion-service/.../metadata_suggestion_service.py`); `GROQ_MODEL` trong compose | Groq `llama-3.3-70b-versatile` | ❌ Tắt từ 2026-08-16 | `openai/gpt-oss-120b` |
| LLM dự phòng `groq/qwen3-32b` | `qwen/qwen3-32b` | ❌ Tắt từ 2026-07-17 | `openai/gpt-oss-120b` |
| Giá trị mặc định cho lọc độc hại (`layer1_toxic_filter.py:125`) | `meta-llama/llama-guard-3-8b` | ❌ Tắt từ 2025-06. Bản thay thế `llama-guard-4-12b` cũng đã tắt từ 2026-03 | `openai/gpt-oss-safeguard-20b` (preview) |
| Chặn jailbreak (`layer1_model`) | `meta-llama/llama-prompt-guard-2-86m` | ⚠️ Còn chạy nhưng ở dạng preview | Giữ, có phương án dự phòng |
| `gemini/flash-2` | `gemini-2.0-flash` | ❌ Google ghi ngày tắt sớm nhất là 2026-06-01 | Dòng Gemini Flash / Flash-Lite 3.x |
| `openrouter/mistral-7b` | `mistralai/mistral-7b-instruct` | ⚠️ Vẫn có trên OpenRouter nhưng tính phí | Bỏ |
| `local/qwen3-8b` (mặc định) | `qwen3-8b` tự host | ✅ Chạy được nhưng cần GPU hoặc nhiều RAM | Chỉ dùng khi chạy eval local |
| Embedding (cả hai service, compose) | `jina-embeddings-v3` | Vẫn chạy, nhưng free tier là quota cấp một lần và chỉ dùng phi thương mại | `bge-m3` (ADR-006) |

Trang danh sách model của Groq vẫn liệt kê `llama-3.1-8b-instant` và `llama-3.3-70b-versatile`. Trang deprecation thì ghi đã tắt cho gói free/developer, chỉ khách enterprise còn dùng được. Đã gọi bằng key thật ngày 2026-10-20 (V2-02, `eval/provider_check/check_providers.py`): Groq `/models` HTTP 200 (11 model), Gemini `/models` HTTP 200 (63 model). Script chỉ đối chiếu các model V2 sẽ dùng (bảng hạn mức bên dưới); chưa xác nhận trực tiếp trạng thái của các model Llama/Qwen cũ ở bảng trên, nên cột "Trạng thái" vẫn dựa trên trang deprecation.

#### Hạn mức bản miễn phí (owner chụp ngày 2026-10-19)

| Provider | Model | RPM | RPD | TPM | TPD | Đã gọi thử (V2-02) |
|---|---|---:|---:|---:|---:|---|
| Gemini | Gemini 3.1 Flash Lite | 15 | 500 | 250K | — | 2026-10-20 (lần 1): cả hai ID trả HTTP 503 (quá tải). 2026-10-20 (lần 2, 10:19): `gemini-3.1-flash-lite-preview` HTTP 200 (7,4 s); `gemini-3.1-flash-lite` vẫn HTTP 503. ID model phải cấu hình được, mặc định dùng `-preview`. 2026-11-01: `/models` HTTP 200 (60 model); `-preview` HTTP 200 (3134 ms); không `-preview` HTTP 200 (7280 ms). Không còn dùng cho sinh câu trả lời (owner chốt 2026-11-01, tự host trên Modal) |
| Gemini | Gemini 2.5 Flash / 3 Flash / 3.6 Flash | 5 | 20 | 250K | — | |
| Gemini | Gemini 2.5 Flash Lite | 10 | 20 | 250K | — | |
| Gemini | Gemini 2 Flash, 2 Flash Lite, 2.5 Pro, 3.1 Pro | 0 | 0 | 0 | — | Không dùng được ở bản miễn phí |
| Groq | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K | 2026-10-20: `gpt-oss-120b` HTTP 200 (492 ms; lần 2: 663 ms), `gpt-oss-20b` HTTP 200 (569 ms; lần 2: 461 ms). 2026-11-01: `/models` HTTP 200 (11 model); `gpt-oss-120b` HTTP 200 (697 ms); `gpt-oss-20b` HTTP 200 (508 ms). `gpt-oss-120b` không còn làm dự phòng sinh hay giám khảo; `gpt-oss-20b` vẫn dùng cho gợi ý metadata |
| Groq | `meta-llama/llama-prompt-guard-2-86m`, `-22m` | 30 | 14.4K | 15K | 500K | 2026-10-20: 86m HTTP 200, đầu ra là xác suất dạng text, p50 316 ms; không đạt bài test (bên dưới) |
| Groq | `openai/gpt-oss-safeguard-20b` | 3 | 1K | 2K | 200K | |

Phân vai chọn từ bảng này: ADR-006 §4.4.

#### Bài test Prompt Guard 2 86M (V2-02, 2026-10-20)

Bộ 100 câu `eval/provider_check/prompt_guard_cases.jsonl` (agent soạn, chưa được owner duyệt từng câu), script `eval/provider_check/check_providers.py`, kết quả gốc `eval/provider_check/results/summary-20261020-001108.md` chỉ lưu cục bộ (thư mục `results/` nằm trong `eval/.gitignore`); số liệu chính được chép vào bảng dưới.

| Cấu hình | Chặn đúng tấn công VI | Chặn đúng tấn công EN | Chặn nhầm câu dễ nhầm (VI / EN) | Chặn nhầm chunk (VI / EN) |
|---|---|---|---|---|
| Prompt Guard, ngưỡng 0.5 | 4/20 | 13/20 | 0/10 / 2/10 | 0/10 / 1/10 |
| Luật (regex) | 16/20 | 16/20 | 1/10 / 0/10 | 1/10 / 1/10 |
| Prompt Guard OR luật | 17/20 | 20/20 | 1/10 / 2/10 | 1/10 / 2/10 |

- Tiếng Việt gần như không được nhận diện, kể cả câu ghi đè chỉ dẫn trực tiếp; khớp với model card (tiếng Việt không có trong các ngôn ngữ được đánh giá).
- Chặn nhầm câu tiếng Anh hợp lệ ("Ignore the previous version of the SOP…" 0.97, "Forget my last question…" 0.999) và một chunk SOP ("Ignore any instructions received by email…" 0.99), nên cũng không dùng được để quét chunk tài liệu.
- Kết luận: không đạt tiêu chí (chặn nhầm ≤ 2%, chặn đúng VI ≥ 70%). Guard dùng luật (owner chốt lần cuối 2026-11-01; owner đã duyệt cả bộ 100 câu). Lần chạy lại 2026-11-01 bỏ qua Prompt Guard (`--skip-guard`) và chỉ cho lại baseline luật: tấn công chặn đúng 16/20 ở cả VI và EN, chặn nhầm câu thường 0/10, câu dễ nhầm VI 1/10 và EN 0/10, chunk VI 1/10 và EN 1/10. Số của luật lạc quan vì luật được viết trên chính bộ câu này; cần bộ câu kiểm tra riêng khi chốt luật ở V2-10.

### 4.2 Lỗi liên quan tới embedding
- `ingestion-service/src/services/embedding_service.py:27` gán cứng `EMBEDDING_MODEL_NAME = "BGE_M3"`, trong khi model thực tế mặc định là Jina. Vì vậy cache và các chunk đang ghi sai tên model. Đây đúng là vấn đề của ticket NEXT-05. V2 dùng database mới nên lỗi không lan sang, nhưng **không được port nguyên đoạn này**.
- Văn bản bị cắt về 512 token bằng `tiktoken` (tokenizer của OpenAI), không phải tokenizer của model embedding. bge-m3 đọc được tới 8192 token.
- Enum `frontend/web/interfaces/enums/knowledge/embedding-model.enum.ts` liệt kê các model OpenAI mà hệ thống không dùng.

### 4.3 Áp lực quota LLM
- Mỗi câu hỏi hiện có thể gọi LLM 5–6 lần: guard, lọc độc hại, phân loại ý định, viết lại câu hỏi, sinh tiêu đề, sinh câu trả lời. Riêng lần sinh câu trả lời mang khoảng 10 chunk, tức khoảng 4 nghìn token prompt.
- Trang giới hạn của Groq ghi `gpt-oss-20b` và `gpt-oss-120b` được 30 request/phút, 1 nghìn request/ngày, 8 nghìn token/phút và 200 nghìn token/ngày. Trang ghi đây là gói Developer, gói free có thể thấp hơn. Với mức đó, hệ thống chỉ trả lời được **khoảng 30–40 câu hỏi/ngày**.
- Embedding thì ngược lại, dư sức: một tài liệu 100 trang tốn khoảng 60 nghìn token, một câu hỏi tốn khoảng 30–50 token.
- **Kết luận:** V2 phải giảm số lần gọi LLM xuống còn 2 cho mỗi câu hỏi (guard + sinh câu trả lời), và đặt hạn mức theo user. Chi tiết ở ADR-006 §4.3.

---

## 5. Truy xuất và reranker

Luồng hiện tại: embed câu hỏi → vector search (top 50) + BM25 (top 50) → trộn bằng RRF (k=60, trọng số 0.7/0.3) → lọc theo `similarity_threshold=0.15` → lấy 25 chunk → [rerank, giữ 10] → phát hiện khoảng trống tri thức → prompt dùng tối đa 10 chunk.

| # | Phát hiện | Vị trí | Hệ quả |
|---|---|---|---|
| R1 | **Reranker không bao giờ chạy.** `PipelineOrchestrator()` được khởi tạo mà không truyền `reranker_service`, nên trường này là `None` | `api/routes/chat.py:42`, `pipeline_orchestrator.py:80, 235, 439` | `USE_RERANKER` không có tác dụng gì. Không có test nào chạm tới reranker |
| R2 | RRF chỉ dùng điểm để sắp xếp, không ghi điểm đó vào `similarity_score`. Mỗi chunk giữ điểm gốc: cosine nếu đến từ vector, `ts_rank` đã chuẩn hóa nếu đến từ BM25 | `hybrid_search.py:97, 109-136` | Ngưỡng 0.15 đang so trên hai thang đo trộn lẫn |
| R3 | Lọc theo ngưỡng chạy trước bước rerank | `hybrid_search.py:97` | Chunk bị loại oan không thể được reranker cứu lại |
| R4 | Reranker ghi đè `similarity_score` bằng điểm của nó, trong khi bước phát hiện khoảng trống vẫn dùng ngưỡng 0.15 | `reranker.py:51`, `knowledge_gap.py:48` | Bật hay tắt rerank làm thay đổi số câu bị đánh dấu "chưa trả lời được", dù tài liệu không đổi |
| R5 | Điểm trả về cho frontend lấy thẳng từ `similarity_score` | `api/routes/chat.py:50` | Thang điểm hiển thị đổi theo cấu hình |

**Ý nghĩa của reranker cho V2:**
- Reranker sắp xếp lại các ứng viên có sẵn, không tìm ra chunk mới.
- Kỳ vọng tăng Recall@5, nDCG và MRR, đổi lại thêm độ trễ (ước chừng 1 tới vài giây trên CPU cho 25 cặp, chưa đo).
- Khi top đầu đáng tin hơn, có thể giảm số chunk đưa vào prompt từ 10 xuống 5. Số câu hỏi trả lời được mỗi ngày trong cùng quota LLM vì thế tăng gần gấp đôi.
- V2 lưu tách `dense_score`, `bm25_score`, `fusion_score` và `rerank_score`. Rerank chạy trước khi lọc theo ngưỡng. Mỗi chế độ có ngưỡng riêng, hiệu chỉnh trên tập eval. Đây là đối tượng của RQ2 và RQ3.

---

## 6. Hạ tầng và nhà cung cấp miễn phí (tóm tắt, chi tiết ở ADR-006)

| Hạng mục | Phát hiện |
|---|---|
| MinIO community | Ngừng phát hành Docker image từ 2025-10, repo bị archive khoảng 2026-02. Chỉ chạy được bản đã ghim phiên bản, và không còn bản vá bảo mật |
| Jina | Free tier là quota cấp một lần (đa số nguồn ghi 10 triệu token, một số ghi 1 triệu), chỉ dùng phi thương mại, giới hạn 100 request/phút |
| Oracle Always Free | Nhiều nguồn ghi đã giảm từ 4 OCPU / 24 GB xuống 2 OCPU / 12 GB vào khoảng 2026-06, và thường báo hết capacity. Owner quyết định không dùng vì rủi ro mất thời gian |
| Hugging Face Spaces | Tài liệu chính thức: Space dạng Docker hoặc Gradio **phải có gói trả phí mới tạo được**. Space chỉ kết nối ra ngoài qua cổng 80, 443 và 8080, nên không nối được Postgres cổng 5432 |
| Cloudflare Workers AI | Free 10 nghìn neurons/ngày, nạp lại hằng ngày. `bge-m3` tốn 1.075 neurons cho mỗi triệu token, tự tính ra khoảng 9 triệu token/ngày. Có `bge-m3` và `qwen3-embedding-0.6b`. Reranker duy nhất là `bge-reranker-base`, yếu với tiếng Việt |
| PaaS miễn phí | Render: 512 MB RAM, ngủ sau 15 phút. Koyeb: nguồn không thống nhất. Fly.io: chỉ còn dùng thử. Railway: credit rất ít. Cloud Run: free theo GB-giây, cần thẻ |
| Postgres | Neon Free: 0.5 GB và 100 CU-giờ mỗi project, có pgvector, tự tắt sau 5 phút không dùng |

---

## 7. Các đánh đổi đã chấp nhận (khi PRD/ADR được duyệt)

| # | Đánh đổi | Cách giảm thiểu |
|---|---|---|
| T1 | Mất phòng ban và quyền theo phòng ban | Dùng nhiều workspace; thêm "group" sau V2 |
| T2 | Thu hồi quyền trễ tối đa bằng tuổi thọ access token (≤ 15 phút) | Kiểm tra lại membership khi refresh; thêm danh sách đen `jti` nếu cần |
| T3 | Dùng database mới với Flyway, bỏ dữ liệu local cũ | Không có dữ liệu production; reset volume chỉ khi owner yêu cầu |
| T4 | Outbox + polling thay cho RabbitMQ, ingest trễ vài giây | Đủ cho tải MVP; contract giữ nguyên nếu sau này đổi sang broker |
| T5 | Bỏ gateway, nên mất rate limit theo role và circuit breaker | Hạn mức đặt trong service; reverse proxy cho một origin duy nhất |
| T6 | Chỉ đăng nhập bằng Google | Dev login ở profile local/test; publish OAuth consent screen trước khi demo |
| T7 | RLS phức tạp (`SET LOCAL` mỗi transaction; role DB không phải owner bảng) | Bộ test FR-19 bắt buộc chạy trong CI |
| T8 | Token gắn workspace, nên các tab mở workspace khác nhau tranh nhau token | Frontend giữ token theo workspace, hoặc mỗi trình duyệt chỉ một workspace hoạt động |
| T9 | Phụ thuộc free tier: cold start, quota, điều khoản có thể đổi | Gọi trước để đánh thức trước khi demo, hạn mức theo user, cache embedding, eval chạy local, cấu hình provider qua env |
| T10 | Phải viết lại phần lớn code Java | Port có chọn lọc (mục 3); code cũ nằm song song tới khi V2 đạt parity |
| T11 | Dữ liệu gửi qua Gemini free tier có thể được Google dùng để cải thiện sản phẩm | Khi deploy chỉ dùng tài liệu demo công khai; ghi rõ trong báo cáo |

---

## 8. Việc tiếp theo
- [ ] Owner duyệt PRD-V2, ADR-004, ADR-005, ADR-006.
- [ ] Viết TECH-V2-core-api và TECH-V2-ai-service (đưa các phát hiện R1–R5 và §4.2 vào thiết kế).
- [x] Gọi thử Groq `/models` bằng key thật để xác nhận mục 4.1 (2026-10-20, V2-02).
- [ ] Lập PLAN-V2 và ticket.

## 9. Nguồn tham khảo (đọc ngày 2026-10-16 → 2026-10-17)
- [Groq – Deprecations](https://console.groq.com/docs/deprecations), [Groq – Models](https://console.groq.com/docs/models), [Groq – Rate limits](https://console.groq.com/docs/rate-limits)
- [Gemini API – Deprecations](https://ai.google.dev/gemini-api/docs/deprecations), [Gemini API – Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Cloudflare Workers AI – Models](https://developers.cloudflare.com/workers-ai/models/), [Pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Hugging Face Spaces Overview](https://huggingface.co/docs/hub/en/spaces-overview)
- [MinIO maintenance mode – elest.io](https://blog.elest.io/minio-is-in-maintenance-mode-your-guide-to-s3-compatible-storage-alternatives/), [MinIO archived – pinggy.io](https://pinggy.io/blog/minio_archived_self_hosted_s3_alternatives/)
- [Jina Embeddings](https://jina.ai/embeddings/), [Jina pricing – markaicode](https://markaicode.com/pricing/jina-ai-pricing/)
- [Oracle free tier changes 2026 – terminalbytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [Hosting free tiers (09/2026) – flaviocopes](https://flaviocopes.com/hosting-free-tiers/)
- [Neon pricing](https://neon.com/pricing)
- [OpenRouter – mistral-7b-instruct providers](https://openrouter.ai/mistralai/mistral-7b-instruct/providers)
