---
id: TECH-V2-AI-SERVICE
title: "Thiết kế kỹ thuật ai-service (V2): ingest có cấu trúc, truy xuất hybrid có lọc quyền, hỏi đáp có trích dẫn"
status: approved
created: 2026-10-20
updated: 2026-11-09
refs:
  - docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md
  - docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
  - docs/02-architecture/adr/ADR-008-pdf-extraction-docling.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
  - docs/02-architecture/designs/TECH-V2-core-api.md
author: "Owner"
affected_services: [ai-service, core-api, eval]
affected_schemas: [rag]
---

# THIẾT KẾ KỸ THUẬT: ai-service (V2)

> **Mã tài liệu:** `TECH-V2-AI-SERVICE` | **Tham chiếu PRD:** `PRD-V2-SOPILOT-MVP` | **Trạng thái:** `approved` (owner duyệt 2026-10-20, V2-03; câu hỏi mở chốt ở §11)
>
> Contract với core-api (endpoint `/internal/**`, payload, idempotency, thứ tự) định nghĩa ở [TECH-V2-core-api](TECH-V2-core-api.md) §8. Tài liệu này chỉ mô tả phía ai-service xử lý chúng.
>
> **Sửa 2026-10-21 (owner, [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md)):** bỏ TXT; định nghĩa Markdown chuẩn và offset (§5.2); cảnh báo trích xuất (§5.3a); thử lại đưa job `FAILED` về hàng đợi (§3.2, §8); màn xem "Nội dung hệ thống nhận diện" FR-31 chỉ khi `READY` (§7.3); tiêu chí chọn thư viện PDF (§11 Q7, Q8).
>
> **Sửa 2026-10-21 (rà soát trước implement):** `V2-20` dựng khung service và `docproc` nhận tokenizer qua protocol riêng (§1.1); `DocElement` có `page_end` và offset từng hàng bảng (§5.2); phân loại lỗi tự thử lại / dừng ngay và cột `run_after` (§3.2, §5.1); eval và service dùng chung bộ chunk, số liệu RQ chính thức của `V2-07` chạy bằng `docproc` (§6.5).
>
> **Sửa 2026-10-21 (owner, rà soát kiến trúc RAG theo bài toán SOP):** (A) `index_text` có thêm mã tài liệu `docCode` (§5.4); (B) tách đơn vị tìm kiếm khỏi đơn vị đưa cho LLM đọc: sau cổng ngưỡng, mở rộng mỗi chunk trúng thành nhóm cùng mục và gộp các chunk liền nhau (§6.4a), lưu `messages.context_sources` (§3.4); (C) hệ số BM25 khi câu hỏi khác ngôn ngữ chunk, cột `chunks.lang`, mặc định `1.0` (không đổi) cho tới khi `V2-07` đo RQ1b (§6.4). Không thêm lần gọi LLM nào. Các thiết kế GraphRAG, RAPTOR, iterative/agentic, HyDE/multi-query và contextual retrieval bằng LLM không đưa vào V2 (§12a).
>
> **Sửa 2026-10-21 (owner, audit đầu-cuối theo loại query, quyết định D1–D11 ở §11):** (1) cổng `hybrid` luôn có `dense_score` cho ứng viên đầu (§6.4); (2) `outcome` giữ nguyên, thêm `refusal_reason` để tách "không có bằng chứng", "LLM tự nói không tìm thấy", "ngoài phạm vi" và "đầu vào không hợp lệ"; danh sách khoảng trống chỉ gồm loại cần bổ sung tài liệu (§3.4, §7.1, §7.6); (3) `PROCEDURE_STEP` lặp giá trị ô gộp xuống từng hàng (§5.2, §5.4); (4) luật header/footer có số trang tối thiểu (§5.3); (5) `<source>` mang `code`, `rev`, `effective` và prompt có ngày hiện tại, không đổi `index_text` (§7.1 bước 6); (6) đặc tả đầu vào: câu rỗng hoặc quá dài bị từ chối, "token có nghĩa", câu nối tiếp khi viết lại lỗi, prompt sinh nhận câu đã viết lại cộng câu gốc và không nhận lịch sử (§7.1); (7) nhật ký quyết định `route`, `rewrite_status`, `checks` (§3.4); (8) router mở rộng chạy **sau** cổng ngưỡng, che PII, kiểm số/ngày, không fallback sau khi đã stream, term bỏ dấu và nhận diện mã tài liệu trong truy vấn, kiểm model embedding lúc khởi động (§3.3, §6.3, §7.1, §7.4). Không thêm lần gọi LLM nào.

---

## 0. Phạm vi và quy ước

- ai-service là service FastAPI, Python ≥ 3.11, viết mới ở `services/ai-service`. Thay `ai-qa-service` và `ingestion-service` (gỡ ở V2-17). Mã cũ chỉ để tham khảo.
- ai-service là chủ duy nhất của schema `rag`, không đọc schema `core` (ADR-004 §4.3). Mọi thông tin về tài liệu và quyền đi qua job và `rag.document_access`.
- Mỗi câu hỏi gọi LLM sinh **tối đa một lần**; viết lại câu hỏi (chỉ khi có lịch sử) là lần gọi thứ hai và duy nhất còn lại. Guard chạy bằng luật; định tuyến bằng luật rồi semantic router dựa trên embedding, không gọi LLM (PRD FR-13, ADR-006 §4.4).
- Mọi model đi qua interface provider và khai báo trong **một** file `config/models.yaml`; không gán cứng model ID trong code (ADR-006 §4.1).

### Truy vết tới yêu cầu và phát hiện cũ

| Yêu cầu / phát hiện | Mục |
|---|---|
| FR-08, AUDIT-ingestion §5 mục 2–9 | §5 |
| FR-10, R1–R5 | §6 |
| FR-11, FR-12, FR-13, FR-14 | §7.1–§7.3 |
| FR-09 (hạn mức câu hỏi mặc định tắt, giới hạn provider) | §7.4 |
| FR-15, UC-11 (ẩn lịch sử khi mất quyền) | §7.5 |
| FR-16, FR-17 (owner chốt Q1 2026-10-20) | §7.6 |
| FR-25, ADR-007 §4.5 | §3.2, §6.1 |
| FR-28 | §5.7 |
| FR-31 (màn xem nội dung nhận diện), FR-14 | §5.2, §5.3a, §7.3 |
| FR-18 (đồng bộ với `eval/`) | §6.5 |
| FR-19, FR-29 | §9 |
| §4.2 AUDIT-v2: `EMBEDDING_MODEL_NAME = "BGE_M3"`, cắt 512 token bằng `tiktoken` | §4.2, §5.5 |
| Rà soát kiến trúc RAG theo bài toán SOP (owner chốt 2026-10-21): mã tài liệu trong chỉ mục, ghép context theo mục, hệ số BM25 cross-lingual | §5.4, §6.4, §6.4a, §12a |
| Audit đầu-cuối theo loại query (owner chốt 2026-10-21, D1–D11): gate hybrid, `refusal_reason`, ô gộp, metadata trong `<source>`, đầu vào, PII, router sau cổng | §3.3, §3.4, §5.2–§5.4, §6.3, §6.4, §7.1–§7.6, §11, §12a |

---

## 1. Tổng quan kiến trúc và thành phần

| Thành phần | Công nghệ | Ranh giới | Bản chất thay đổi |
|---|---|---|---|
| `services/ai-service` | FastAPI, SQLAlchemy 2 (async, psycopg 3), Pydantic v2, uv | Schema `rag` | Service mới |
| `infrastructure/db/migrations/rag/` | Flyway | Schema `rag` | Chuỗi migration mới (V2-08) |
| Worker ingest và gợi ý metadata | Tiến trình con trong cùng container (`python -m sopilot_ai.worker`) | `rag.ingestion_jobs`, `rag.suggestion_jobs` | Hàng đợi Postgres `FOR UPDATE SKIP LOCKED` |
| Model local | sentence-transformers / transformers trên CPU | — | `bge-m3`, `bge-reranker-v2-m3` (ADR-006 §4.2) |
| LLM API | Một endpoint tự host (vLLM trên Modal) qua API kiểu OpenAI | — | ADR-006 §4.4, [V2-10 mốc 2](../../03-plans/tickets/V2-10-ai-service-qa-pipeline.md) |

API và worker là hai tiến trình dùng chung image và cấu hình. Tách tiến trình để bước embed nặng CPU không chặn event loop của API (lỗi cũ: OCR đồng bộ trong hàm `async`, AUDIT-ingestion §2.1). Truy vấn hỏi đáp vẫn embed câu hỏi trong tiến trình API, qua `run_in_threadpool` với một model đã nạp sẵn.

### 1.1 Cấu trúc package

```
services/ai-service/
├── pyproject.toml      # uv; extra `pdf` cho thư viện ADR-008, extra `local` cho sentence-transformers
├── config/models.yaml
├── src/sopilot_ai/
│   ├── api/            # routers công khai /ai/v1 và nội bộ /internal, SSE
│   ├── auth/           # xác minh JWT qua JWKS core-api, InternalTokenDependency
│   ├── db/             # engine, session có set_config tenant, repositories
│   ├── docproc/        # PACKAGE THUẦN, không phụ thuộc DB/web (V2-20, V2-21, V2-22)
│   │   ├── model.py    #   DocElement, StructuredDocument
│   │   ├── tokens.py   #   Tokenizer protocol + HFTokenizer (AutoTokenizer theo model/revision) (V2-22)
│   │   ├── extract/    #   pdf.py (adapter của thư viện ADR-008), markdown.py (V2-20)
│   │   ├── normalize.py#   NFC, khoảng trắng; render.py: Markdown chuẩn + offset + mốc trang (V2-20)
│   │   ├── clean/      #   boilerplate.py, metadata.py, warnings.py (V2-21)
│   │   └── chunk/      #   family.py, procedure_table.py, chunker.py (V2-22)
│   ├── providers/      # embedding.py, rerank.py, llm.py, registry.py (đọc models.yaml)
│   ├── retrieval/      # access_filter.py, dense.py, lexical.py, fusion.py, gate.py, context.py (§6.4a)
│   ├── qa/             # guard.py, router.py, prompt.py, citations.py, pipeline.py
│   ├── conversations/
│   ├── quota/          # bộ đếm câu hỏi, giới hạn RPM/TPM theo provider
│   ├── ingest/         # job handler gọi docproc → embed → ghi chunk
│   ├── suggest/        # gợi ý metadata (V2-25)
│   ├── outbox/         # gửi trạng thái và gợi ý về core-api
│   └── worker.py
└── tests/
```

`docproc` là package Python thuần: nhận bytes và loại file, trả cấu trúc dữ liệu. `eval/` và test chất lượng trích xuất (V2-19) import trực tiếp package này, nên số đo trên corpus là số đo của đúng code chạy trong service.

**Thứ tự dựng khung.** `V2-20` là ticket đầu tiên viết code vào `services/ai-service`, nên nó tạo `pyproject.toml`, layout `src/sopilot_ai/`, `tests/unit` và scope build/test cho service mới trong `scripts/` (`validate-build.ps1 -Scope ai`, `run-tests.ps1 -Scope ai-service`). `V2-20` chỉ cần `docproc`; các package khác để trống. `V2-09` thêm `api/`, `db/`, `providers/`, `retrieval/`, `ingest/`, `worker.py` và các migration `rag`.

**Tokenizer không đi qua provider.** Chunker (`V2-22`) nhận một `Tokenizer` (protocol trong `docproc/tokens.py`: `count(text) -> int`) được truyền vào, không gọi `EmbeddingProvider`. `HFTokenizer` nạp `transformers.AutoTokenizer` theo `model` và `revision` của embedding đang hoạt động trong `models.yaml`, không cần nạp model embedding. `EmbeddingProvider.tokenizer()` của `V2-09` trả đúng đối tượng này. Nhờ vậy `V2-22` không phụ thuộc `V2-09`, và `eval/` đếm token bằng cùng tokenizer.

---

## 2. Sơ đồ tuần tự

### 2.1 Ingest một phiên bản tài liệu

```mermaid
sequenceDiagram
    autonumber
    participant C as core-api
    participant A as ai-service API
    participant W as ai-service worker
    participant DB as Postgres (rag)
    participant S3 as Object storage

    C->>A: POST /internal/ingestions (Idempotency-Key)
    A->>DB: BEGIN; set_config(app.workspace_id); UPSERT document_access (nếu accessRevision mới hơn); INSERT ingestion_jobs ON CONFLICT (version_id) đưa job FAILED về QUEUED chỉ khi attempt mới hơn (§8); COMMIT
    A-->>C: 202
    A->>W: NOTIFY rag_jobs (đánh thức; worker cũng quét mỗi 5 s)
    W->>DB: rag.claim_ingestion_job() (SECURITY DEFINER, FOR UPDATE SKIP LOCKED, lease 10 phút)
    W->>DB: outbox VERSION_STATUS(PROCESSING)
    W->>S3: GET objectKey
    W->>W: docproc.extract → normalize → clean → render Markdown chuẩn + cảnh báo → chunk (tokenizer của model embedding)
    W->>W: embed (cache theo model, revision, sha256)
    W->>DB: BEGIN; INSERT chunks, chunk_terms, extracted_documents (version mới); UPDATE document_access.active_version_id; DELETE chunks của version cũ; job DONE; outbox VERSION_STATUS(READY); COMMIT
    W->>C: (outbox) PATCH /internal/documents/{id}/versions/{verId}/status (READY + mã cảnh báo)
    W->>DB: INSERT suggestion_jobs (nếu suggest.enabled)
```

### 2.2 Hỏi đáp

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as ai-service
    participant DB as Postgres (rag)
    participant L as LLM provider

    B->>A: POST /ai/v1/conversations/{id}/messages (Bearer, Accept: text/event-stream)
    A->>A: Xác minh JWT (JWKS core-api): sub, wid, wrole, wdept
    A->>DB: Kiểm tra hạn mức user/ngày và trần hệ thống nếu bật (FR-09, mặc định tắt)
    A->>A: Kiểm đầu vào (rỗng, quá dài → SSE refusal INPUT_INVALID, kết thúc), che PII
    A->>A: Guard đầu vào (luật VI/EN): CHẶN → SSE refusal, kết thúc
    A->>A: Router luật: chào hỏi/cảm ơn/hỏi về bot → SSE câu mẫu, kết thúc
    opt Có lịch sử hội thoại
        A->>L: Viết lại câu hỏi thành câu độc lập (LLM call 1)
    end
    A->>DB: Dense + lexical, lọc workspace + quyền TRƯỚC LIMIT (§6.1)
    A->>A: RRF (hệ số BM25 theo ngôn ngữ) → rerank (nếu bật) → cổng ngưỡng theo chế độ (luôn có dense_score)
    alt Dưới ngưỡng
        A-->>B: SSE refusal (NO_EVIDENCE: kèm tài liệu gần nhất, vào danh sách khoảng trống; OUT_OF_SCOPE: không kèm, không vào danh sách)
    else Đủ bằng chứng
        A->>DB: Ghép context: lấy chunk cùng mục của các chunk trúng, lọc quyền (§6.4a)
        A->>L: Sinh câu trả lời, stream (LLM call cuối)
        A-->>B: SSE delta (giữ lại đuôi để kiểm canary)
        A->>A: Kiểm canary, ánh xạ [n], loại trích dẫn không ánh xạ được
        A-->>B: SSE citations + done (văn bản cuối đã làm sạch)
    end
    A->>DB: Lưu message, citations, retrieval_results (4 loại điểm), guard_events
```

---

## 3. Thiết kế dữ liệu (schema `rag`)

- Migration: `infrastructure/db/migrations/rag/V0xx__*.sql`, bảng lịch sử `rag.flyway_schema_history`.
- Extension `vector` (pgvector ≥ 0.8, để có iterative index scan khi lọc) tạo ở migration bootstrap của V2-08.
- Mọi bảng có `workspace_id` bật `ENABLE` + `FORCE ROW LEVEL SECURITY` với policy `workspace_id = rag.current_workspace()` (định nghĩa giống `core.current_workspace()`, TECH-V2-core-api §4.2). Ngoại lệ có lý do ghi ngay tại bảng.
- Không có FK sang `core`. `document_id`, `version_id`, `user_id`, `department_id` là UUID do core-api cấp.

### 3.1 Quyền đọc tài liệu (ADR-007 §4.5)

```sql
CREATE TABLE rag.document_access (
    workspace_id      uuid NOT NULL,
    document_id       uuid PRIMARY KEY,
    visibility        text NOT NULL CHECK (visibility IN ('WORKSPACE','DEPARTMENTS')),
    department_ids    uuid[] NOT NULL DEFAULT '{}',
    access_revision   bigint NOT NULL,
    active_version_id uuid,                 -- phiên bản đang được truy xuất; NULL = chưa READY lần nào
    title             text NOT NULL,        -- để hiển thị trích dẫn và "tài liệu gần nhất"
    deleted_at        timestamptz,          -- đặt ngay khi nhận DELETE, trước khi dọn chunk
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (visibility = 'WORKSPACE' OR cardinality(department_ids) >= 1)
);
CREATE INDEX ix_document_access_ws ON rag.document_access(workspace_id);
CREATE INDEX ix_document_access_depts ON rag.document_access USING gin (department_ids);
```

Không có dòng quyền → chunk không bao giờ được truy xuất vì mọi truy vấn `JOIN` bảng này (fail closed). `title` được core-api gửi kèm job và cập nhật khi đổi tiêu đề sẽ cần thêm một sự kiện; để tránh thêm sự kiện, V2 hiển thị tên tài liệu trong trích dẫn bằng tiêu đề **tại thời điểm ingest**, frontend lấy tiêu đề mới nhất qua core-api khi mở trình xem.

### 3.2 Job ingest và kết quả trích xuất

```sql
CREATE TABLE rag.ingestion_jobs (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    version_id    uuid NOT NULL UNIQUE,     -- idempotent theo phiên bản
    request_attempt int NOT NULL DEFAULT 0, -- `attempt` của core-api; lần thử lại có attempt lớn hơn đưa job FAILED về QUEUED (§8)
    payload       jsonb NOT NULL,           -- nguyên payload POST /internal/ingestions
    status        text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED','CANCELLED')),
    attempts      int NOT NULL DEFAULT 0,
    lease_until   timestamptz,              -- worker chết giữa chừng: job tự trả lại sau khi hết lease
    run_after     timestamptz NOT NULL DEFAULT now(), -- backoff khi tự thử lại lỗi tạm thời (§5.1)
    failure_code  text,
    stage_timings jsonb,                    -- {download_ms, extract_ms, clean_ms, chunk_ms, embed_ms, write_ms}
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ingestion_jobs_due ON rag.ingestion_jobs(created_at) WHERE status IN ('QUEUED','RUNNING');

CREATE TABLE rag.extracted_documents (
    workspace_id   uuid NOT NULL,
    version_id     uuid PRIMARY KEY,
    document_id    uuid NOT NULL,
    structure      jsonb NOT NULL,          -- StructuredDocument đã làm sạch (§5.2), cho trình xem và gợi ý metadata
    markdown       text NOT NULL,           -- Markdown CHUẨN sau làm sạch (§5.2); offset của phần tử và chunk tham chiếu vào đây
    page_index     jsonb,                   -- PDF: [{page, charStart, charEnd}] trên markdown; MD: NULL
    warnings       jsonb NOT NULL DEFAULT '[]', -- [{code, pages?, count?}] (§5.3a)
    normalizer_version text NOT NULL,       -- phiên bản quy tắc chuẩn hóa + renderer; đổi thì phải ingest lại để offset còn đúng
    page_count     int,
    language       text,
    doc_family     text NOT NULL CHECK (doc_family IN ('ISO_PROCEDURE','LEGAL_ARTICLES','MARKDOWN','PROSE')),
    boilerplate    jsonb NOT NULL,          -- phần khung đã tách: header/footer, quốc hiệu, chữ ký, bảng phê duyệt...
    extracted_meta jsonb NOT NULL,          -- {docCode, revisionLabel, effectiveDate, approvedBy}
    extractor      text NOT NULL,           -- tên + phiên bản thư viện (ADR-008, V2-20)
    created_at     timestamptz NOT NULL DEFAULT now()
);
```

`rag.claim_ingestion_job()` là hàm `SECURITY DEFINER` (owner `sopilot_migrator`, `GRANT EXECUTE` cho `sopilot_ai_app`) trả một job `QUEUED` có `run_after <= now()` hoặc `RUNNING` hết lease, đặt `RUNNING`, `lease_until = now() + 10 phút`, `attempts + 1`. Worker cần hàm này vì phải thấy job của mọi workspace; sau khi nhận job, worker đặt `app.workspace_id` theo job và mọi truy vấn tiếp theo chịu RLS bình thường. Khi khởi động, worker quét job còn tồn trước khi chờ `NOTIFY` (FR-08, ADR-006 B1 ràng buộc 3). Chỉ lỗi tạm thời được tự thử lại (§5.1); quá `SOPILOT_INGEST_MAX_ATTEMPTS=3` → `FAILED` giữ mã lỗi của lần cuối. `RETRY_EXHAUSTED` chỉ dùng khi job hết lần thử mà không có mã lỗi nào được ghi (worker chết liên tục, lease hết hạn).

### 3.3 Chunk và chỉ mục

```sql
CREATE TABLE rag.chunks (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL,
    document_id        uuid NOT NULL,
    version_id         uuid NOT NULL,
    ordinal            int  NOT NULL,                 -- thứ tự trong tài liệu
    chunk_type         text NOT NULL CHECK (chunk_type IN ('SECTION','PROCEDURE_STEP','TABLE','PROSE')),
    section_path       text[] NOT NULL,               -- tổ tiên, ví dụ {'5. Nội dung','5.1 Lập đề nghị mua hàng'}
    page_start         int,
    page_end           int,
    char_start         int  NOT NULL,                 -- offset trong extracted_documents.markdown
    char_end           int  NOT NULL,
    content            text NOT NULL,                 -- đoạn hiển thị cho người dùng và gửi LLM
    index_text         text NOT NULL,                 -- "Tên tài liệu [mã] › mục › bước\n" + content: được embed và index lexical (§5.4)
    lang               text,                          -- ngôn ngữ của phiên bản (bước 6 §5.1), dùng cho hệ số BM25 §6.4; NULL = không rõ
    token_count        int  NOT NULL,                 -- đếm bằng tokenizer của embedding_model
    content_sha256     bytea NOT NULL,                -- sha256(index_text), khóa cache embedding
    embedding          vector(1024) NOT NULL,
    embedding_provider text NOT NULL,
    embedding_model    text NOT NULL,
    embedding_dim      int  NOT NULL CHECK (embedding_dim = 1024),
    embedding_revision text NOT NULL,
    lexical_len        int  NOT NULL,                 -- số term gốc của index_text, không tính term bỏ dấu `~` (§6.3); BM25 cần độ dài tài liệu
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_id, ordinal),
    CHECK (char_end > char_start)
);
CREATE INDEX ix_chunks_doc ON rag.chunks(document_id, version_id);
CREATE INDEX ix_chunks_embedding ON rag.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE rag.chunk_terms (                        -- chỉ mục lexical cho BM25 (§6.3)
    workspace_id uuid NOT NULL,
    chunk_id     uuid NOT NULL REFERENCES rag.chunks(id) ON DELETE CASCADE,
    term         text NOT NULL,                       -- unigram, bigram `a_b`, và dạng bỏ dấu `~a`, `~a_b` khi khác dạng gốc (§6.3)
    tf           int  NOT NULL CHECK (tf > 0),
    PRIMARY KEY (chunk_id, term)
);
CREATE INDEX ix_chunk_terms_lookup ON rag.chunk_terms(workspace_id, term);

CREATE TABLE rag.embedding_cache (                    -- KHÔNG có workspace_id, KHÔNG RLS: chỉ chứa vector, khóa theo nội dung
    model        text  NOT NULL,
    revision     text  NOT NULL,
    content_sha256 bytea NOT NULL,
    embedding    vector(1024) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, revision, content_sha256)
);
```

Ghi chú thiết kế:
- **Kích thước vector cố định 1024.** Cả ba model của RQ5 (`bge-m3`, `Qwen3-Embedding-0.6B`, `multilingual-e5-large-instruct`) đều ra 1024 chiều. Ứng dụng chỉ dùng **một** model đang hoạt động; truy vấn luôn lọc `embedding_model = :active AND embedding_revision = :active_rev`, nên vector của hai model không bao giờ bị so với nhau (ADR-006 §4.1.3). Đổi model là chạy lại ingest cho mọi phiên bản; thí nghiệm RQ5 chạy trong `eval/`, không trong DB ứng dụng. Vì chunk của model cũ bị lọc bỏ âm thầm (mọi câu hỏi sẽ bị từ chối), khi khởi động ai-service so `(embedding_model, embedding_revision)` của các chunk thuộc phiên bản đang hoạt động với model đang bật: có lệch thì log `ERROR`, `/health` trả `degraded` kèm số phiên bản lệch, và lệnh quản trị `reindex` (§5.2) ingest lại các phiên bản đó.
- **`embedding_cache` không có `workspace_id`** là ngoại lệ có chủ đích (ADR-007 §4.5: cache embedding chỉ chứa vector theo nội dung). Không trả văn bản từ bảng này; không có đường nào từ hash suy ra workspace.
- **Bốn loại điểm** (`dense_score`, `bm25_score`, `fusion_score`, `rerank_score`) phụ thuộc câu hỏi nên không nằm trên `chunks`; chúng được lưu theo từng lần truy xuất ở `rag.retrieval_results` (§3.4). Điều này thay cho cách cũ ghi đè `similarity_score` (R2, R4, R5).
- `section_path` là chuỗi **tổ tiên**, không phải anh em (lỗi standardizer cũ, AUDIT-ingestion §2.3).

### 3.4 Hội thoại, truy xuất và guard

```sql
CREATE TABLE rag.conversations (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL,
    title        text NOT NULL,                         -- sinh bằng luật từ câu hỏi đầu (cắt 80 ký tự)
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    deleted_at   timestamptz
);
CREATE INDEX ix_conversations_owner ON rag.conversations(workspace_id, user_id, updated_at DESC);

CREATE TABLE rag.messages (
    id              uuid PRIMARY KEY,
    workspace_id    uuid NOT NULL,
    conversation_id uuid NOT NULL REFERENCES rag.conversations(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL,
    role            text NOT NULL CHECK (role IN ('USER','ASSISTANT')),
    content         text NOT NULL,
    standalone_query text,                              -- câu hỏi sau khi viết lại (nếu có)
    outcome         text CHECK (outcome IN ('ANSWERED','REFUSED_NO_EVIDENCE','REFUSED_GUARD','TEMPLATE','QUOTA_EXCEEDED','ERROR')),
    refusal_reason  text CHECK (refusal_reason IN ('NO_EVIDENCE','GENERATOR_NOT_FOUND','OUT_OF_SCOPE','INPUT_INVALID')),  -- NULL khi không từ chối; ngữ nghĩa ở dưới
    route           jsonb,                              -- {layer: 'rule'|'semantic'|'followup_rule'|'none', intent, score, margin}
    rewrite_status  text CHECK (rewrite_status IN ('NONE','OK','FAILED')),   -- NONE: không có lịch sử
    checks          jsonb,                              -- {citationCount, numberWarnings: [...], disclaimers: [...], pii: [rule_id]}
    lang            text,
    retrieval_mode  text,                               -- dense | bm25 | hybrid | hybrid_rerank
    gate_score      real,
    threshold       real,
    model           text,                               -- LLM thực sự sinh (sau fallback)
    prompt_version  text,
    tokens_in       int,
    tokens_out      int,
    latency_ms      jsonb,                              -- {retrieve, rerank, context, first_token, total}
    context_sources jsonb,                              -- [{n, documentId, versionId, hitChunkIds, chunkIds, tokens}] sau ghép context §6.4a; NULL nếu không gọi LLM sinh
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (refusal_reason IS NULL OR outcome IN ('REFUSED_NO_EVIDENCE', 'TEMPLATE'))
);
CREATE INDEX ix_messages_conv ON rag.messages(conversation_id, created_at);

CREATE TABLE rag.message_citations (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages(id) ON DELETE CASCADE,
    n            int  NOT NULL,                         -- số [n] trong câu trả lời
    chunk_id     uuid,                                  -- có thể NULL nếu chunk đã bị xóa khi thay bản mới
    document_id  uuid NOT NULL,
    version_id   uuid NOT NULL,
    page_start   int,
    char_start   int  NOT NULL,
    char_end     int  NOT NULL,
    snippet      text NOT NULL,                         -- bản sao đoạn trích tại thời điểm trả lời
    PRIMARY KEY (message_id, n)
);
CREATE INDEX ix_citations_document ON rag.message_citations(document_id);

CREATE TABLE rag.retrieval_results (                    -- phục vụ RQ2/RQ3 trên dữ liệu thật và gỡ lỗi
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages(id) ON DELETE CASCADE,
    chunk_id     uuid NOT NULL,
    rank         int  NOT NULL,                          -- thứ hạng cuối (sau rerank nếu có)
    dense_score  real,                                   -- cosine
    bm25_score   real,
    fusion_score real,                                   -- RRF
    rerank_score real,
    in_context   boolean NOT NULL,                       -- có được đưa vào prompt không
    PRIMARY KEY (message_id, chunk_id)
);

CREATE TABLE rag.guard_events (                          -- lớp 4 của FR-13
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    message_id   uuid REFERENCES rag.messages(id) ON DELETE CASCADE,
    user_id      uuid NOT NULL,
    layer        text NOT NULL CHECK (layer IN ('INPUT_BLOCK','INPUT_FLAG','OUTPUT_CANARY','OUTPUT_PROMPT_ECHO')),
    rule_id      text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag.usage_counters (                        -- FR-09
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL,
    day          date NOT NULL,                          -- theo UTC
    questions    int  NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, user_id, day)
);
```

**`outcome` và `refusal_reason` (owner chốt 2026-10-21, D2).** `outcome` giữ nguyên tập giá trị; `refusal_reason` cho biết *vì sao* một câu không được trả lời, để RQ3 mức câu trả lời tách được "cổng từ chối" khỏi "LLM tự từ chối" và để danh sách khoảng trống (§7.6) không lẫn câu không liên quan tới thiếu tài liệu:

| `refusal_reason` | `outcome` | Khi nào | Vào danh sách khoảng trống |
|---|---|---|---|
| `NO_EVIDENCE` | `REFUSED_NO_EVIDENCE` | Cổng ngưỡng từ chối (§6.4) và câu không bị xếp `OUT_OF_SCOPE` | Có |
| `GENERATOR_NOT_FOUND` | `REFUSED_NO_EVIDENCE` | Cổng cho qua nhưng LLM trả câu mở đầu cố định "không tìm thấy" (§7.1 bước 6, 9) | Có |
| `OUT_OF_SCOPE` | `REFUSED_NO_EVIDENCE` | Cổng từ chối **và** router xếp `off_topic` vượt ngưỡng (V2-27); không hiện tài liệu gần nhất | Không |
| `INPUT_INVALID` | `TEMPLATE` | Câu rỗng, quá dài, không có token có nghĩa, hoặc câu nối tiếp khi viết lại lỗi (§7.1 bước 2–4); không gọi LLM, không tính hạn mức | Không |

Không có `refusal_reason` cho câu bị lọc quyền: ai-service không truy vấn ngoài quyền (fail closed, §6.1), nên không thể phân biệt "thiếu tài liệu" với "tài liệu ngoài quyền". Câu `ANSWERED` nhưng `checks.citationCount = 0` vẫn là `ANSWERED` và được danh sách khoảng trống lấy thêm (FR-11 bị vi phạm lúc chạy). `messages.content` lưu **nguyên văn** câu hỏi cho người hỏi; việc che PII áp dụng khi gửi LLM, khi viết lại và khi hiện cho admin (§7.1 bước 2, §7.6).

Trần câu hỏi toàn hệ thống cần đếm qua mọi workspace nên nằm trong bảng **không RLS** `rag.system_usage(day date PRIMARY KEY, questions int)`, chỉ chứa số đếm. Cập nhật bằng `INSERT ... ON CONFLICT DO UPDATE SET questions = questions + 1 RETURNING questions`.

### 3.5 Gợi ý metadata và outbox

```sql
CREATE TABLE rag.suggestion_jobs (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    version_id    uuid NOT NULL UNIQUE,
    input         jsonb NOT NULL,      -- categories/tags hiện có từ payload ingest
    status        text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED')),
    result        jsonb,
    method        text CHECK (method IN ('RULES','LLM','RULES_FALLBACK')),
    timings       jsonb,               -- {t_ready, t_suggest, llm_ms, tokens_in, tokens_out}
    attempts      int NOT NULL DEFAULT 0,
    lease_until   timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag.suggestion_cache (
    workspace_id   uuid NOT NULL,
    cache_key      bytea NOT NULL,     -- sha256(workspace_id, content_sha256, prompt_version, model, hash danh sách category)
    result         jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, cache_key)
);

CREATE TABLE rag.outbox_events (    -- cùng cấu trúc và quy tắc với core.outbox_events (TECH-V2-core-api §3.5, §7)
    id              uuid PRIMARY KEY,
    workspace_id    uuid NOT NULL,
    aggregate_id    uuid NOT NULL,
    event_type      text NOT NULL CHECK (event_type IN ('VERSION_STATUS','SUGGESTIONS_READY')),
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','DELIVERED','DEAD')),
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz
);

CREATE TABLE rag.processed_requests (  -- idempotency cho /internal/** (Idempotency-Key từ core-api)
    idempotency_key uuid PRIMARY KEY,
    processed_at    timestamptz NOT NULL DEFAULT now()
);
```

`processed_requests` không có `workspace_id` và không RLS (chỉ chứa UUID); dọn dòng cũ hơn 7 ngày.

---

## 4. Xác thực, cấu hình và provider

### 4.1 Xác thực

- **Request công khai `/ai/v1/**`:** `Authorization: Bearer <access token>` do core-api phát. Xác minh RS256 bằng JWKS `http://core-api:8080/.well-known/jwks.json` (cache 10 phút, tải lại khi gặp `kid` lạ, tối đa 1 lần/phút), kiểm `iss = sopilot-core`, `aud` chứa `sopilot-ai`, `exp` (lệch 60 s). Lấy `sub`, `wid`, `wrole`, `wdept`. Các giá trị này là nguồn duy nhất cho bộ lọc tenant và quyền; **không** đọc `workspaceId` từ body hay query (ADR-005 §4.5).
- **Request nội bộ `/internal/**`:** header `X-Internal-Token`, so sánh thời gian hằng (`hmac.compare_digest`). Router nội bộ không được mount dưới tiền tố `/ai`, nên rewrites của frontend không chạm tới.
- Mọi session DB mở transaction và gọi `SELECT set_config('app.workspace_id', :wid, true), set_config('app.user_id', :sub, true)` ngay đầu (dependency `tenant_session`). Repository không nhận session chưa qua dependency này.

### 4.2 `config/models.yaml`

Đây là nơi **duy nhất** khai báo model (ADR-006 §4.1.2). Giá trị là cấu hình mặc định; ID chính xác của Gemini được giữ cấu hình được vì `gemini-3.1-flash-lite` (GA) còn trả 503 lúc thử, chỉ bản `-preview` trả 200 (V2-02, AUDIT-v2 §4.1, 2026-10-20).

```yaml
embedding:
  active: bge-m3
  models:
    bge-m3:
      provider: local                 # local | cloudflare | openai_compatible
      model: BAAI/bge-m3
      revision: ${EMBEDDING_REVISION}  # ghim HF commit hash; khởi động lỗi nếu trống ở profile eval
      dim: 1024
      max_tokens: 8192
      query_prefix: ""
rerank:
  enabled: ${RERANK_ENABLED:false}
  provider: ${RERANK_PROVIDER:local}   # local | modal | none (V2-35)
  model: BAAI/bge-reranker-v2-m3
  revision: ${RERANK_REVISION}
  max_pairs: 25
  timeout_s: ${RERANK_TIMEOUT_S:30}    # chỉ cho modal
llm:
  # Sửa 2026-11-09 (V2-10 mốc 2, ADR-006 §4.4): một model tự host sau server kiểu OpenAI (vLLM trên
  # Modal). Chuỗi Gemini/Groq đã bỏ (owner 2026-11-01). Endpoint, model id và khóa lấy từ môi trường.
  generate:
    chain:
      - provider: modal
        model: "${SOPILOT_LLM_MODEL:}"
        rpm: "${SOPILOT_LLM_RPM:60}"        # giá trị giữ chỗ, đo trên endpoint thật
        tpm: "${SOPILOT_LLM_TPM:200000}"
        context_max_tokens: "${SOPILOT_LLM_CONTEXT_MAX_TOKENS:}"   # trống = chưa khai báo trần
        extra_body: {chat_template_kwargs: {enable_thinking: false}}
    temperature: 0.2
    max_output_tokens: 800
  rewrite:
    chain: [same entry as generate]
    temperature: 0
    max_output_tokens: 200
providers:
  modal: {base_url: "${SOPILOT_LLM_BASE_URL:}", api_key_env: SOPILOT_LLM_API_KEY}
retrieval:
  candidate_pool: 50      # mỗi nhánh dense / lexical
  rerank_pool: 25
  context_k: 5            # số chunk trúng đưa vào ghép context (§6.4a)
  rrf_k: 60
  rrf_weights: [1.0, 1.0]
  doc_code_boost: 0.02    # cộng vào fusion_score của chunk có docCode khớp mã trong câu hỏi (§6.4); giá trị khởi đầu, chưa hiệu chỉnh (V2-28)
  cross_lingual_bm25_factor: 1.0   # nhân vào trọng số BM25 khi ngôn ngữ câu hỏi ≠ chunks.lang (§6.4); 1.0 = tắt, đổi sau RQ1b (V2-07)
  context:                # ghép context small-to-big (§6.4a)
    expand: true          # false = chỉ đưa chunk trúng, như cách cũ (ablation V2-10)
    section_max_tokens: 1200   # nhóm cùng mục nhỏ hơn mức này thì đưa nguyên nhóm
    max_tokens: 3000      # trần tổng context, đếm bằng token_count của chunk
  thresholds:             # cổng từ chối; hiệu chỉnh trên tập dev của V2-06 (RQ3)
    dense: 0.45
    bm25: null            # BM25 không có thang chung giữa các câu hỏi; chế độ bm25 không tự từ chối
    hybrid: 0.45          # so trên dense cosine của ứng viên đầu, giống harness eval
    hybrid_rerank: 0.30   # so trên rerank score (sigmoid) của ứng viên đầu
  mode: hybrid            # dense | bm25 | hybrid; rerank thêm hậu tố _rerank khi rerank.enabled
chunking:
  target_tokens: 384
  max_tokens: 512         # vừa giới hạn 512 của multilingual-e5 để kết quả RQ5 áp dụng được
  min_tokens: 64          # section nhỏ hơn được gộp với anh em cùng cha
```

Ngưỡng ở trên là giá trị giữ chỗ, phải thay bằng giá trị hiệu chỉnh trên tập dev (V2-07). Khi khởi động, ai-service gọi `/models` của từng provider có key và log `WARNING` cho model không còn trong danh sách (ADR-006 §4.1.2); không chặn khởi động để eval truy xuất vẫn chạy khi không có key LLM.

### 4.3 Interface provider

```python
class EmbeddingProvider(Protocol):
    name: str; model: str; revision: str; dim: int
    def tokenizer(self) -> "Tokenizer": ...                       # tokenizer của chính model này
    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray: ...   # đã chuẩn hóa L2

class RerankProvider(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> np.ndarray: ...       # sigmoid, [0, 1]

class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], *, task: Literal["generate","rewrite","small_task","judge"],
                       response_schema: type[BaseModel] | None = None) -> Completion: ...
    def stream(self, messages: list[Message], *, task: str) -> AsyncIterator[Delta]: ...
```

- `EmbeddingProvider`: `local` (sentence-transformers, chạy trên threadpool), `cloudflare` (Workers AI `@cf/baai/bge-m3`, chỉ cho deploy, ngoài phạm vi V2), `openai_compatible` (TEI hoặc server nhúng khác).
- `RerankProvider`: `local` (cross-encoder `bge-reranker-v2-m3` trên CPU), `modal` (`RemoteRerankProvider`, V2-35: `POST {providers.modal.rerank_base_url}/rerank` tới `/v1/rerank` của container Modal chung GPU với vLLM; server trả logit thô theo thứ tự `passages`, client áp sigmoid như `LocalRerankProvider`; lỗi HTTP, hết thời gian hay JSON sai đều thành `RerankError`, không hạ xuống hybrid), `none`. Khóa là `SOPILOT_LLM_API_KEY`, URL là `SOPILOT_RERANK_BASE_URL`. Một reranker qua API miễn phí có thể thêm sau như một provider mới mà không đổi pipeline (xem câu hỏi mở Q3).
- `LLMProvider`: một lớp duy nhất gọi API kiểu OpenAI `chat/completions` với `base_url` khác nhau. `ChainedLLM` thử lần lượt các model trong `chain`; chuyển sang model kế tiếp khi gặp `429`, `503`, timeout, hoặc khi bộ giới hạn cục bộ báo hết quota (§7.4), và **chỉ trước khi phát `delta` đầu tiên** (§7.4). Ghi model thực sự trả lời vào `messages.model`.

---

## 5. Ingest có cấu trúc (FR-08, V2-19..22)

### 5.1 Các bước của job

| Bước | Module | Đầu ra | Lỗi → `failure_code` |
|---|---|---|---|
| 1. Tải file | `ingest` | bytes | `OBJECT_NOT_FOUND` |
| 2. Trích xuất | `docproc.extract` (PDF: thư viện ADR-008, OCR tắt; MD: parser CommonMark/GFM) | `StructuredDocument` | `UNSUPPORTED_TYPE`, `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING` (MD không phải UTF-8) |
| 2a. Chuẩn hóa | `docproc.normalize` | `StructuredDocument` (NFC, khoảng trắng, giữ số thứ tự nguồn) | — |
| 3. Tách khung, trích metadata, cảnh báo | `docproc.clean` | `StructuredDocument` đã làm sạch + `boilerplate` + `extracted_meta` + `warnings` | — |
| 3a. Render Markdown chuẩn | `docproc.render` | `markdown`, offset của từng phần tử, `page_index` | — |
| 4. Nhận diện họ tài liệu | `docproc.chunk.family` | `ISO_PROCEDURE` \| `LEGAL_ARTICLES` \| `MARKDOWN` \| `PROSE` | — |
| 5. Chunk | `docproc.chunk` | `list[Chunk]` | `EMPTY_CONTENT` khi 0 chunk (sửa lỗi cũ: rỗng vẫn `READY`) |
| 6. Phát hiện ngôn ngữ | `ingest` | `vi` / `en` / khác, ghi vào `extracted_documents.language` và `chunks.lang` | — |
| 7. Embed | `providers.embedding` + cache | vector 1024 chiều | `EMBEDDING_ERROR` (có thử lại) |
| 8. Ghi và kích hoạt | `ingest` | transaction §5.6 | — |

`failure_message` gửi về core-api là câu cố định theo `failure_code` (VI/EN), không bao giờ là message của exception. Lỗi không rõ nguyên nhân trong bước 2–5 ghi `EXTRACTION_ERROR`.

**Lỗi nào được tự thử lại.** Worker chỉ tự thử lại lỗi tạm thời; lỗi do nội dung file là tất định nên dừng ngay ở lần đầu, giữ đúng mã để giao diện gợi ý "Thay file" (TECH-V2-core-api §5.5).

| Loại | Mã | Hành vi của worker |
|---|---|---|
| Tạm thời | `OBJECT_NOT_FOUND`, `EMBEDDING_ERROR`, lỗi kết nối DB/storage, worker chết (lease hết hạn) | Job về `QUEUED`, `run_after = now() + 30 s × 2^(attempts − 1)`, **không** gửi callback `FAILED`; phiên bản vẫn `PROCESSING` ở core-api. Hết `SOPILOT_INGEST_MAX_ATTEMPTS` → `FAILED` với mã của lần cuối |
| Tất định | `UNSUPPORTED_TYPE`, `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING`, `EMPTY_CONTENT`, `EXTRACTION_ERROR` | `FAILED` ngay, gửi callback một lần. Người dùng vẫn bấm thử lại được (`attempt + 1`, §8) |

Thử lại chạy lại toàn bộ các bước cho đúng phiên bản đó; không lưu kết quả trung gian giữa các lần thử (trích xuất là tất định, chi phí nhỏ so với embed, và embed đã có cache §5.5).

### 5.2 Cấu trúc tài liệu trung gian (đầu ra V2-20)

```python
class DocElement(BaseModel):
    kind: Literal["heading", "paragraph", "list_item", "table", "page_break", "code"]
    text: str                       # đã chuẩn hóa NFC; với list_item giữ số thứ tự hiện trong nguồn ("5.1", "a)")
    level: int | None = None        # heading 1..6; list nesting
    number: str | None = None       # số thứ tự đã render, nếu có
    rows: list[list[str]] | None = None   # table: hàng đầu là tiêu đề cột nếu nhận ra; ô gộp ghi một lần ở ô đầu (xem cell_spans)
    cell_spans: list[tuple[int, int, int, int]] | None = None  # table: (row, col, rowspan, colspan) của từng ô gộp, chỉ các ô có rowspan > 1 hoặc colspan > 1; None nếu thư viện không trả span (ghi vào ADR-008)
    page: int | None = None         # PDF: trang bắt đầu (số trang thật, từ 1); MD: None
    page_end: int | None = None     # PDF: trang kết thúc, = page nếu không kéo qua trang (bảng nhiều trang); MD: None
    row_pages: list[int] | None = None    # table PDF: trang của từng hàng trong rows, cùng độ dài rows
    char_start: int | None = None   # offset trên Markdown chuẩn, do render đặt; None với phần tử không render (role ∉ {content, figure_text})
    char_end: int | None = None
    row_spans: list[tuple[int, int]] | None = None  # table: [char_start, char_end) của từng hàng trong Markdown chuẩn, do render đặt
    role: Literal["content", "header", "footer", "boilerplate", "figure_text"] = "content"  # figure_text: chữ lớp chữ PDF trong vùng ảnh mà Docling không xuất (sơ đồ), được render như nội dung; chữ trong vùng ảnh nằm 15% đầu/10% cuối trang giữ role header/footer

class StructuredDocument(BaseModel):
    file_type: Literal["PDF", "MD"]
    elements: list[DocElement]      # theo thứ tự đọc; bảng nằm đúng vị trí trong thân
    page_count: int | None
    frontmatter: dict | None        # MD

def render(doc: StructuredDocument) -> RenderedDocument: ...   # docproc.render: markdown, offset từng phần tử, page_index
```

**Markdown chuẩn (owner chốt 2026-10-21).** `extracted_documents.markdown` là chuỗi do `docproc.render` sinh từ các phần tử `role = content` hoặc `figure_text` **sau** chuẩn hóa và làm sạch. Đây là bản duy nhất dùng cho chunk, `index_text`, trích dẫn, gợi ý metadata, trình xem trích dẫn (FR-14) và màn xem FR-31. Quy tắc:
- Renderer là code của SOPilot, tất định, có `normalizer_version`. Chuỗi Markdown do thư viện PDF tự xuất (nếu có) **không** được dùng làm nguồn offset. Thư viện chỉ cung cấp cây phần tử qua adapter `extract/pdf.py`; đây là nơi duy nhất phụ thuộc thư viện.
- Render: heading → `#` theo level; đoạn → một khối, các dòng bị ngắt cứng trong PDF được nối bằng khoảng trắng; list item giữ số thứ tự nguồn (`5.1`, `a)`); bảng → bảng GFM, xuống dòng trong ô thay bằng khoảng trắng, ô gộp ghi một lần ở ô đầu, các ô còn lại để trống, ký tự `|` trong ô được escape; khối cách nhau đúng một dòng trống.
- Offset `[char_start, char_end)` tính theo **Unicode code point** (chỉ số chuỗi Python) trên `markdown`. Bất biến kiểm thử: với mọi phần tử nội dung, `markdown[char_start:char_end]` bằng đúng đoạn render của phần tử đó. API công khai trả thêm offset UTF-16 (`charStart16`, `charEnd16`) để trình duyệt cắt chuỗi đúng khi có ký tự ngoài BMP.
- Bảng: `row_spans[i]` là đoạn của hàng `rows[i]` trong bảng GFM (từ `|` đầu tới `|` cuối, không gồm xuống dòng); dòng phân cách `|---|` không thuộc hàng nào. Bất biến: `row_spans` tăng dần, nằm trong `[char_start, char_end)` của bảng. Đây là offset mà chunk `PROCEDURE_STEP` và chunk bảng cắt theo hàng dùng (§5.4).
- Ô gộp (owner chốt 2026-10-21): Markdown chuẩn vẫn ghi giá trị một lần ở ô đầu (hiển thị và offset không đổi), nhưng `cell_spans` cho biết ô đó phủ những hàng/cột nào để chunker lặp giá trị xuống từng hàng khi dựng chunk `PROCEDURE_STEP` (§5.4). Docling (ADR-008) có trả span ô gộp hay không là một mục xác nhận của `V2-20` (chưa đo); nếu không trả span, `cell_spans = None`, chunker không đoán giá trị cho ô trống, và hạn chế này được ghi vào ADR-008 §6.
- Bảng kéo qua nhiều trang là **một** phần tử (adapter nối các phần bảng liên tiếp có cùng tiêu đề cột), `page` là trang đầu, `page_end` là trang cuối, `row_pages` cho trang của từng hàng. Phần tử khác có `page_end = page`.
- `page_index` (PDF): danh sách `{page, charStart, charEnd}` liên tiếp, không chồng nhau, theo trang của phần tử; bảng nhiều trang được chia tại ranh giới hàng theo `row_pages`; trang không có phần tử nội dung không xuất hiện. Màn xem dùng nó để chèn mốc "Trang N".
- Markdown đầu vào được parse rồi render lại, nên Markdown chuẩn có thể khác định dạng gốc (ví dụ `*` thành `-`, heading Setext thành `#`). File gốc vẫn tải xuống được. Không cam kết cùng nội dung ở PDF và MD cho ra Markdown giống hệt.
- Không gọi LLM ở bất kỳ bước nào của trích xuất, chuẩn hóa hay render.
- Tọa độ (bbox) không thuộc contract MVP: không lưu cột, không có tiêu chí nghiệm thu, không có UI dùng tới. Trình xem chỉ nhảy trang PDF.
- Đổi `normalizer_version` làm offset cũ mất hiệu lực: phải ingest lại các phiên bản đang hoạt động (lệnh quản trị `python -m sopilot_ai.admin reindex`, không tự động trong MVP). Cùng lệnh này dùng khi đổi model embedding hoặc tokenizer BM25 (§3.3, §6.3).

Quy tắc theo định dạng (V2-20; PDF dùng Docling theo ADR-008, xác nhận theo tiêu chí §11 Q8):
- **Chỉ PDF và MD.** DOCX hoãn sau MVP (owner chốt 2026-10-20), TXT bỏ khỏi MVP (owner chốt 2026-10-21): core-api từ chối bằng `415`, không tạo job. Worker vẫn kiểm tra allowlist PDF/MD trước khi parse (`UNSUPPORTED_TYPE`).
- **PDF có lớp chữ:** dùng cấu trúc của **một** thư viện (heading/đoạn/list/bảng/thứ tự đọc/số trang) đưa thẳng vào `DocElement`; không trích plain text rồi dựng lại cấu trúc, không fallback sang thư viện thứ hai. OCR **tắt** trong cấu hình thư viện và có test chứng minh trang ảnh cho 0 ký tự. Giữ số trang; thứ tự đọc đúng với trang nhiều cột; bảng giữ hàng/cột. Toàn tài liệu gần như không có chữ (tỷ lệ trang có chữ < 10% hoặc tổng < 200 ký tự) → `NO_TEXT_LAYER`; một phần trang không có chữ → vẫn xử lý, cảnh báo `PAGES_WITHOUT_TEXT` (§5.3a).
- **MD:** parser CommonMark + GFM (bảng, list) thuần Python, HTML nhúng giữ dạng văn bản; bỏ frontmatter khỏi nội dung và lưu vào `frontmatter`; xóa shortcode Hugo `{{< ... >}}` (corpus GitLab của V2-06). File không phải UTF-8 hợp lệ → `INVALID_ENCODING` (core-api đã chặn trước, đây là lớp thứ hai).

### 5.3 Tách khung và metadata (V2-21)

- Header/footer lặp: dòng xuất hiện ở ≥ 40% số trang (owner chốt 2026-11-04, đổi từ 60%: phụ lục biểu mẫu dùng header khác nên header chính chỉ phủ 41–57% số trang; đo trên corpus V2-19 cho khung lọt 19,8% ở 60% và 8,1% ở 40%, không thêm lỗi xóa nhầm thật) tại cùng vùng đầu/cuối trang (sau khi thay số trang bằng `#`) → `role = header|footer`, bỏ khỏi nội dung. **Chỉ áp dụng khi PDF có ít nhất `SOPILOT_HEADER_FOOTER_MIN_PAGES` trang (mặc định 3, giá trị khởi đầu chốt trên corpus V2-19)**: với 1–2 trang mọi dòng đầu/cuối đều đạt ≥ 60% nên luật sẽ xóa tiêu đề và đoạn cuối. Phần tử `heading` đầu tiên của tài liệu không bao giờ bị đánh `header`.
- Khối khung VI/EN nhận diện bằng luật: quốc hiệu/tiêu ngữ, số/ký hiệu, nơi nhận, khối chữ ký, bảng Soạn thảo/Soát xét/Phê duyệt (Prepared/Reviewed/Approved), bảng theo dõi sửa đổi (Revision history). Đánh `role = boilerplate`, lưu vào `extracted_documents.boilerplate`.
- Metadata trích từ khung trước khi bỏ: `docCode` (mã số/mã hiệu), `revisionLabel` (lần ban hành), `effectiveDate`, `approvedBy`. Gửi về core-api trong callback `READY`.
- Không xóa nội dung thật: V2-21 báo cáo tỷ lệ khung lọt vào nội dung và tỷ lệ nội dung bị xóa nhầm trên corpus V2-19.
- Khối khung đã loại được lưu trong `boilerplate` dạng `[{kind, page, text}]` để màn xem FR-31 liệt kê; không vào `markdown`, chunk hay index.

### 5.3a Cảnh báo trích xuất (FR-31)

Chỉ sinh khi có tín hiệu cụ thể; không có điểm tin cậy. Lưu ở `extracted_documents.warnings`, gửi mã về core-api trong callback `READY` (`warningCodes`).

| Mã | Điều kiện | Dữ liệu kèm |
|---|---|---|
| `PAGES_WITHOUT_TEXT` | PDF có lớp chữ nhưng có trang < `SOPILOT_PAGE_MIN_CHARS` (mặc định 20) ký tự | `pages` |
| `UNMAPPED_GLYPHS` | Văn bản sau trích xuất có `U+FFFD`, chuỗi `(cid:n)` hoặc ký tự Private Use | `pages`, `count` |
| `NO_HEADINGS_DETECTED` | Tài liệu nhiều hơn một trang (PDF) hoặc dài hơn `chunking.max_tokens` (MD) mà không có phần tử `heading` | — |
| `BOILERPLATE_REMOVED` | Có khối bị đánh `header`/`footer`/`boilerplate` (thông tin) | `count` |
| `CONVERTER_WARNING` | Thư viện ADR-008 trả cảnh báo có cấu trúc cho trang/phần tử (chỉ khi thư viện có API này) | `pages`, `kind` |

Cảnh báo không làm `FAILED` và không chặn `READY`.

### 5.4 Họ tài liệu và chunk (V2-22)

Nhận diện heading theo thứ tự ưu tiên: heading Markdown (`#`) → mẫu đánh số (`1.`, `5.1`, `I.`, `Điều n`, `Chương n`, `Article n`) đứng đầu dòng ngắn → heuristic (dòng in hoa, chữ đậm). Câu kết thúc bằng dấu chấm và dài hơn 120 ký tự không bao giờ là heading (chặn lỗi "căn cứ ⏎ Điều 5 Luật Doanh nghiệp.").

| Họ | Nhận diện | Đơn vị chunk |
|---|---|---|
| `ISO_PROCEDURE` | Có các mục Mục đích/Phạm vi/Nội dung (Purpose/Scope/Procedure) hoặc bảng có cột Trách nhiệm + Bước/Mô tả | Section theo heading; **mỗi hàng của bảng quy trình là một chunk `PROCEDURE_STEP`**, nội dung dạng `Bước: … \| Trách nhiệm: … \| Mô tả: … \| Biểu mẫu: …`; ô gộp dọc (`cell_spans`, §5.2) được **lặp xuống từng hàng** mà nó phủ, nên bước 3 và 4 dưới một ô "Trách nhiệm" gộp vẫn mang đúng người phụ trách |
| `LEGAL_ARTICLES` | ≥ 3 heading dạng `Điều n` / `Article n` | Mỗi Điều một chunk; Điều dài cắt theo Khoản |
| `MARKDOWN` | File MD hoặc heading `#` | Section theo heading |
| `PROSE` | Không thuộc các họ trên | Đoạn văn; gộp đoạn tới `target_tokens`, cắt theo câu, không cắt cứng giữa câu |

Quy tắc chung:
- Đếm token bằng tokenizer của model embedding đang hoạt động, truyền vào chunker dưới dạng `docproc.tokens.Tokenizer` (§1.1), **không** dùng `tiktoken` (AUDIT-v2 §4.2). Chunk ≤ `max_tokens` tính cả tiền tố đường dẫn tiêu đề.
- Section < `min_tokens` gộp với anh em kế tiếp cùng cha; section > `max_tokens` cắt theo đoạn rồi theo câu. Cắt trên ranh giới ký tự Unicode, không trên byte.
- `index_text` = `"{title} [{docCode}] › {section_path joined by ' › '}\n{content}"`; phần ` [{docCode}]` chỉ có khi V2-21 trích được mã (`extracted_meta.docCode`), ngược lại tiền tố giữ dạng `"{title} › …"`. Tiền tố có trong cả vector lẫn chỉ mục lexical (V2-22). Lý do có mã (owner chốt 2026-10-21): mã nằm trong header/footer nên bị tách khỏi nội dung ở §5.3; thiếu nó, câu hỏi kiểu "QT-MH-01 bước 2 ai duyệt?" không khớp lexical, và hai tài liệu trùng tên khác mã không phân biệt được. Chỉ đưa `docCode`, **không** đưa `revisionLabel` hay `effectiveDate`: hai trường này đổi ở mỗi lần ban hành nên sẽ đổi `content_sha256` của mọi chunk và làm mất cache embedding (§5.5), trong khi người dùng hiếm khi hỏi theo lần ban hành. Chunker nhận `title` và `doc_code` làm tham số, không tự đọc metadata.
- Bảng thường (không phải bảng quy trình) dài hơn `max_tokens` cắt theo hàng, lặp lại hàng tiêu đề cột ở mỗi phần.
- Chunk mang `page_start/page_end` (PDF) và `char_start/char_end` trên Markdown chuẩn (mọi định dạng) để trình xem tô sáng (FR-14). Chunk thường là chuỗi con của `markdown`; chunk `PROCEDURE_STEP` có `content` dạng `Bước: … | Trách nhiệm: …` nên không phải chuỗi con, offset của nó là `row_spans[i]` của hàng nguồn và `page_start = page_end = row_pages[i]`. Chunk bảng cắt theo hàng lấy offset từ `row_spans` của hàng đầu tới hàng cuối trong phần đó, trang từ `row_pages`.

### 5.5 Embedding và cache

- Embed theo lô 16, trên threadpool. Trước khi embed, tra `rag.embedding_cache` theo `(model, revision, sha256(index_text))`, tức hash của đúng chuỗi được embed; chỉ embed phần thiếu rồi ghi lại cache. Không cam kết tỉ lệ cache hit. Không dùng hash của `markdown` để bỏ qua cả phiên bản: quyết định bỏ qua chỉ dựa trên SHA-256 của file ở core-api (FR-07).
- Ghi `embedding_provider/model/dim/revision` đúng giá trị của provider đang hoạt động; không có hằng số như `EMBEDDING_MODEL_NAME = "BGE_M3"` cũ.
- `revision` rỗng ở profile `eval` là lỗi khởi động; ở profile `local` cho phép nhưng log cảnh báo và ghi `revision = "unpinned"`.

### 5.6 Kích hoạt phiên bản (thay bản mới, FR-07)

Một transaction, sau khi đã có đủ vector:
1. `INSERT` chunks, chunk_terms, extracted_documents của phiên bản mới (`extracted_documents` chỉ được ghi ở đây, nên màn xem FR-31 không bao giờ thấy phiên bản chưa kích hoạt).
2. `UPDATE rag.document_access SET active_version_id = :new WHERE document_id = :doc AND deleted_at IS NULL`. Không có dòng (tài liệu đã bị xóa giữa chừng) → rollback, job `CANCELLED`.
3. `DELETE FROM rag.chunks WHERE document_id = :doc AND version_id <> :new` (chunk_terms xóa theo cascade).
4. Job `DONE`; outbox `VERSION_STATUS(READY)`.

Trong lúc bản mới xử lý, truy xuất vẫn dùng bản cũ vì lọc `version_id = active_version_id`. Bản mới `FAILED` không đụng tới bản cũ.

### 5.7 Gợi ý metadata chạy nền (FR-28, V2-25)

- Sau bước 8, nếu `suggest.enabled`, tạo `suggestion_jobs`. Worker xử lý job gợi ý **sau** job ingest, nên gợi ý không nằm trên đường tới `READY`.
- Đầu vào chỉ từ `extracted_documents` (cấu trúc và Markdown chuẩn đã làm sạch): tiêu đề (heading đầu hoặc tên file), dàn ý heading, tối đa 3 đoạn đại diện, trần `SOPILOT_SUGGEST_MAX_INPUT_TOKENS=1500`. Không tải hay parse lại file.
- Luật trước: tiêu đề, ngôn ngữ, `docCode`/`revisionLabel`/`effectiveDate` từ §5.3.
- Một lần gọi `small_task` với structured output `{description, category_id | null, proposed_category_name | null, tags[]}`; `category_id` phải thuộc danh sách category trong payload, sai thì bỏ. Timeout `SOPILOT_SUGGEST_TIMEOUT=20s`, thử lại tối đa 1 lần; lỗi → chỉ gửi kết quả luật với `method = RULES_FALLBACK`.
- Cache theo khóa §3.5; không dùng chung giữa workspace.
- Gửi về core-api qua outbox `SUGGESTIONS_READY` → `PUT /internal/documents/{id}/suggestions`. Gợi ý không chứa phạm vi hiển thị hay phòng ban.
- Ghi số đo theo job (`t_ready`, `t_suggest`, `llm_ms`, token vào/ra, fallback) cho báo cáo p50/p95 của V2-25.

---

## 6. Truy xuất (FR-10, FR-25)

### 6.1 Bộ lọc quyền dùng chung

Mọi nhánh truy xuất dùng cùng một điều kiện, tham số hóa hoàn toàn (sửa A3: không f-string):

```sql
-- :wrole, :wdept lấy từ token; :model, :rev là embedding đang hoạt động. RLS đã giới hạn workspace_id.
WITH allowed AS (
    SELECT da.document_id, da.active_version_id, da.title
    FROM rag.document_access da
    WHERE da.deleted_at IS NULL
      AND da.active_version_id IS NOT NULL
      AND ( :wrole IN ('OWNER','ADMIN')
            OR da.visibility = 'WORKSPACE'
            OR (:wdept IS NOT NULL AND :wdept = ANY(da.department_ids)) )
)
```

Điều kiện `workspace_id = :wid` được viết thêm tường minh ở tầng ứng dụng trong mọi truy vấn, cạnh RLS (hai lớp, ADR-005). Hàm `access_filter.allowed_cte()` là nơi duy nhất sinh đoạn SQL này; test FR-29 gọi trực tiếp nó.

### 6.2 Dense

```sql
SET LOCAL hnsw.iterative_scan = relaxed_order;   -- pgvector ≥ 0.8: tiếp tục quét khi bộ lọc loại nhiều ứng viên
SET LOCAL hnsw.ef_search = 100;
<allowed CTE>
SELECT c.id, 1 - (c.embedding <=> :qvec) AS dense_score
FROM rag.chunks c
JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
WHERE c.workspace_id = :wid
  AND c.embedding_model = :model AND c.embedding_revision = :rev
ORDER BY c.embedding <=> :qvec
LIMIT :candidate_pool;
```

Lọc nằm trong `WHERE`/`JOIN` nên áp dụng **trước** `LIMIT` (FR-25). Với quy mô MVP (≤ 50 tài liệu mỗi workspace) Postgres thường chọn quét tuần tự có lọc, kết quả chính xác tuyệt đối; HNSW chỉ có tác dụng khi dữ liệu lớn hơn.

### 6.3 Lexical (BM25 trong SQL)

Tokenizer giống hệt harness `eval/sopilot_eval/retrievers.py::tokenize`: chữ thường, NFC, `\w+`, unigram + bigram (`a_b`), giữ dấu tiếng Việt, **cộng term bỏ dấu** (owner chốt 2026-10-21, D11): với mỗi unigram/bigram có dấu, thêm một term cùng `tf` ở dạng bỏ dấu với tiền tố `~` (NFD, bỏ dấu kết hợp, `đ → d`; `mua_hàng` sinh thêm `~mua_hang`); term không đổi khi bỏ dấu (từ tiếng Anh, từ vốn không dấu) không sinh term thêm; `lexical_len` chỉ đếm term gốc. Truy vấn có ký tự tiếng Việt có dấu thì dùng term gốc như cũ; truy vấn **không** có dấu nào thì dùng cả term gốc lẫn term `~` tương ứng, để "quy trinh mua hang" khớp "quy trình mua hàng" mà tiếng Anh vẫn khớp bằng term gốc. Chỉ mục lớn lên tối đa khoảng 2 lần (nhỏ ở quy mô ≤ 50 tài liệu). Vì tokenizer dùng chung với harness và đổi nó buộc `reindex` (§5.2), việc này được chốt **trước** số liệu chính thức của `V2-07`. Một module `sopilot_ai.retrieval.lexical.tokenize` được dùng chung cho ingest (sinh `chunk_terms`, `lexical_len`), truy vấn và harness eval (harness import module này thay cho bản sao, V2-09). Tham số BM25 giống harness: `k1 = 1.5`, `b = 0.75`, `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`.

```sql
<allowed CTE>,
scope AS (                -- tập chunk người hỏi được đọc: thống kê BM25 chỉ tính trên tập này
    SELECT c.id, c.lexical_len FROM rag.chunks c
    JOIN allowed a ON a.document_id = c.document_id AND a.active_version_id = c.version_id
    WHERE c.workspace_id = :wid
),
stats AS (SELECT count(*)::float AS n, avg(lexical_len)::float AS avgdl FROM scope),
q AS (SELECT unnest(CAST(:terms AS text[])) AS term),
df AS (
    SELECT t.term, count(*)::float AS df
    FROM rag.chunk_terms t JOIN scope s ON s.id = t.chunk_id JOIN q ON q.term = t.term
    WHERE t.workspace_id = :wid
    GROUP BY t.term
)
SELECT t.chunk_id AS id,
       sum( ln(1 + (st.n - df.df + 0.5) / (df.df + 0.5))
            * t.tf * (1.5 + 1)
            / (t.tf + 1.5 * (1 - 0.75 + 0.75 * s.lexical_len / st.avgdl)) ) AS bm25_score
FROM rag.chunk_terms t
JOIN scope s ON s.id = t.chunk_id
JOIN df ON df.term = t.term
CROSS JOIN stats st
WHERE t.workspace_id = :wid
GROUP BY t.chunk_id
ORDER BY bm25_score DESC
LIMIT :candidate_pool;
```

Lý do chọn BM25 tự viết thay cho `ts_rank` hay extension: (1) điểm khớp harness eval, nên kết quả RQ1 đo bằng `eval/` áp dụng được cho service (V2-09 yêu cầu khớp trong sai số); (2) Postgres không có từ điển tiếng Việt, `ts_rank` không phải BM25 (R2); (3) extension như `pg_search` cần image Postgres riêng. Thống kê `N`, `df`, `avgdl` tính trên **tập được phép đọc**, nên điểm của người hỏi không chịu ảnh hưởng từ tài liệu ngoài quyền. Chi phí chấp nhận được ở quy mô MVP; nếu RQ4 hoặc số đo độ trễ cho thấy chậm, bước tối ưu đầu tiên là bảng thống kê theo workspace, không đổi công thức.

### 6.4 Gộp, rerank và cổng ngưỡng

1. **RRF** trên hai danh sách đã lọc: `fusion(c) = Σ wᵢ / (rrf_k + rankᵢ(c))`, `rrf_k = 60`, trọng số `[1.0, 1.0]` (cấu hình được; trọng số cũ 0.7/0.3 là một cấu hình trong RQ1, không phải mặc định).
   - **Hệ số BM25 theo ngôn ngữ (owner chốt 2026-10-21).** Với chunk có `lang` khác ngôn ngữ câu hỏi (§7.1), trọng số nhánh BM25 của chunk đó nhân thêm `cross_lingual_bm25_factor`. Lý do: khi hỏi tiếng Việt trên tài liệu tiếng Anh, BM25 chỉ khớp vài từ rời (tên công cụ, "laptop") nên danh sách của nó gần như ngẫu nhiên, nhưng RRF vẫn cộng điểm theo thứ hạng và có thể đẩy chunk sai lên trên chunk đúng của nhánh dense. `lang` của chunk hoặc câu hỏi là `NULL`/ngoài `vi`, `en` → hệ số `1.0`. Mặc định `1.0` (không đổi hành vi); chỉ đổi khi `V2-07` (RQ1b) cho thấy hybrid thua dense ở nhóm cross-lingual, và giá trị chọn trên tập dev. Không dịch câu hỏi bằng LLM.
   - **Mã tài liệu trong câu hỏi (owner chốt 2026-10-21).** Câu hỏi chứa chuỗi khớp mẫu mã (`qa/doc_code.py`, regex khởi đầu `[A-ZĐ]{1,6}(?:[-/][A-Z0-9]{1,8}){1,3}` trên bản chữ hoa, ví dụ `QT-MH-01`) thì chunk của phiên bản có `extracted_meta.docCode` trùng (so sau khi chuẩn hóa chữ hoa, bỏ khoảng trắng) được cộng `retrieval.doc_code_boost` vào `fusion_score` trước khi lấy `rerank_pool`. Chỉ tra `extracted_documents` theo `version_id` của ứng viên đã qua bộ lọc quyền. Giá trị khởi đầu `0.02` (cỡ đóng góp của hạng 1 một nhánh), chưa hiệu chỉnh: chỉnh trên bộ kiểm V2-28.
2. Lấy `rerank_pool = 25` ứng viên đầu theo `fusion_score`.
3. **Rerank (nếu bật)** chạy trên 25 ứng viên đó **trước** cổng ngưỡng (sửa R3), xếp lại theo `rerank_score`.
4. **Cổng ngưỡng** so điểm của ứng viên đầu với ngưỡng của chế độ đang chạy (`retrieval.thresholds`, sửa R2/R4):

| Chế độ | Điểm dùng cho cổng | Lý do |
|---|---|---|
| `dense` | `dense_score` (cosine) | Thang chung giữa các câu hỏi |
| `bm25` | Không có cổng | BM25 không có thang chung; chế độ này chỉ dùng cho eval |
| `hybrid` | `dense_score` (cosine) của ứng viên đầu theo `fusion_score`, **luôn có giá trị** (xem dưới) | RRF là điểm theo thứ hạng, không hiệu chỉnh được; giống harness |
| `hybrid_rerank` | `rerank_score` (sigmoid) của ứng viên đầu | Cross-encoder có thang chung |

**`dense_score` luôn có (owner chốt 2026-10-21, D2/P0-1).** Ứng viên chỉ nằm ở nhánh lexical không có điểm dense từ nhánh dense. Sau RRF, với mọi ứng viên trong `rerank_pool` thiếu `dense_score`, tính cosine trực tiếp bằng một truy vấn theo id (`SELECT id, 1 - (embedding <=> :qvec) FROM rag.chunks WHERE id = ANY(:missing) AND embedding_model = :active AND embedding_revision = :active_rev`, qua cùng bộ lọc quyền §6.1). Nhờ đó cổng không bao giờ so một giá trị `NULL`, và `retrieval_results.dense_score` đủ cho 25 ứng viên. Hàm `fusion.gate_score` là một và được `eval/` import; test dùng ứng viên chỉ có điểm BM25. Không thêm lần gọi model: vector câu hỏi đã có.

5. Đủ ngưỡng → `context_k = 5` chunk đầu là **chunk trúng**, đưa vào bước ghép context (§6.4a). Ghi cả 25 ứng viên kèm bốn điểm vào `rag.retrieval_results` (`in_context` đánh dấu 5 chunk trúng). Điểm trả cho frontend là `rank` và (tùy chọn hiển thị) điểm của cổng, không phải một `similarity_score` đổi thang theo cấu hình (R5).

### 6.4a Ghép context: tìm bằng chunk nhỏ, đọc bằng nhóm cùng mục (owner chốt 2026-10-21)

**Vấn đề.** Chunk là đơn vị tốt để *tìm* (một hàng bảng quy trình, một Khoản), nhưng quá hẹp để *đọc*. Ví dụ mục "5.1 Lập đề nghị mua hàng" mở đầu bằng "Áp dụng cho đơn dưới 50 triệu; từ 50 triệu theo mục 5.3", sau đó là bảng bước. Câu hỏi "Đơn 80 triệu trưởng phòng duyệt trong bao lâu?" trúng đúng chunk `PROCEDURE_STEP` bước 2 ("Duyệt trong 2 ngày làm việc"), nhưng nếu chỉ đưa chunk đó, LLM không thấy điều kiện áp dụng và trả lời sai. Điều kiện, ngoại lệ và phạm vi của SOP thường nằm ở đầu mục chứ không lặp lại ở từng bước.

**Cách làm.** Không đổi chunk, chỉ số hay cổng ngưỡng. Sau §6.4 bước 5, module `retrieval/context.py` (hàm thuần, `eval/` import được) dựng danh sách source:

1. **Nhóm cùng mục** của một chunk trúng = các chunk cùng `version_id` và cùng `section_path`, theo `ordinal`. Lấy bằng một truy vấn cho mọi chunk trúng, `JOIN` bộ lọc quyền §6.1 như mọi truy vấn khác (fail closed, dù chunk cùng phiên bản với chunk đã được phép).
2. **Mở rộng:**
   - Tổng `token_count` của nhóm ≤ `context.section_max_tokens` → lấy nguyên nhóm (một Điều có nhiều Khoản, một mục ngắn có bảng ít bước).
   - Lớn hơn → lấy chunk trúng và chunk liền trước, liền sau trong nhóm; nếu chunk trúng là `PROCEDURE_STEP` hoặc `TABLE`, lấy thêm chunk `SECTION`/`PROSE` đầu tiên của nhóm (đoạn dẫn của mục) nếu có.
3. **Gộp:** các cửa sổ của cùng phiên bản chồng nhau hoặc liền `ordinal` gộp thành **một** source; thứ hạng của source là thứ hạng tốt nhất của chunk trúng trong nó.
4. **Trần token:** thêm source theo thứ hạng tới `context.max_tokens`. Source tiếp theo không vừa thì thu về chỉ các chunk trúng của nó; vẫn không vừa thì dừng. Source của chunk trúng hạng 1 luôn được đưa vào (chunk ≤ `max_tokens` của chunking nên luôn vừa).
5. **Render:** nội dung source = `content` các chunk theo `ordinal`, cách nhau một dòng trống, mở đầu bằng dòng `section_path`; `page` của source = `page_start` nhỏ nhất. Chunk `PROCEDURE_STEP` đã ở dạng `Bước: … | Trách nhiệm: …` nên không cần lặp hàng tiêu đề cột.
6. `context.expand = false` → mỗi chunk trúng là một source, không gộp (hành vi trước sửa đổi, dùng cho ablation).

**Trích dẫn.** `[n]` trỏ tới source n. `message_citations` của `[n]` lưu `chunk_id` của chunk trúng hạng cao nhất trong source, `char_start`/`char_end` là khoảng phủ các chunk trúng của source (các chunk này liền nhau sau bước 3), `snippet` là `content` của chúng. Trình xem tô sáng phần trúng, không tô cả mục. `messages.context_sources` ghi đủ `hitChunkIds` và `chunkIds` của từng source để đo faithfulness và gỡ lỗi.

**Không làm.** Không gọi LLM để tóm tắt hay chọn đoạn; không mở rộng sang mục khác hay tài liệu khác (tham chiếu chéo "theo mục 5.3" chỉ được trả lời nếu mục 5.3 tự trúng); không đổi điểm hay thứ hạng sau cổng ngưỡng. Owner chốt 2026-10-21 (D6): **chưa** mở ngoại lệ cho tham chiếu trong cùng tài liệu; `V2-19` đếm tần suất tham chiếu chéo trên corpus, chỉ xét lại khi số đếm cho thấy đáng kể (§12a).

**Chi phí.** Một truy vấn theo `(document_id, version_id)` dùng `ix_chunks_doc`; không thêm lần gọi model. Prompt dài hơn một chút (trần 3.000 token, so với tối đa khoảng 2.560 khi chỉ đưa 5 chunk 512 token, và thường chỉ vài trăm token khi chunk trúng là hàng bảng), nằm trong TPM của chuỗi `generate` (§4.2).

### 6.5 Đồng bộ với harness eval

- `eval/` import `sopilot_ai.docproc` (chunk), `sopilot_ai.retrieval.lexical` (tokenizer, BM25), `sopilot_ai.retrieval.fusion` (RRF, cổng, hệ số BM25 theo ngôn ngữ) và `sopilot_ai.retrieval.context` (ghép context §6.4a, từ `V2-10`) thay cho bản sao hiện có. Harness vẫn chạy in-memory, không cần DB hay stack.
- **Cùng bộ chunk.** Bộ chunk hiện tại của harness (`eval/sopilot_eval/corpus.py`, cửa sổ 800/100 ký tự) chỉ dùng cho smoke và lần chạy thăm dò. Số liệu RQ1–RQ3 và RQ5 chính thức (`V2-07`) và việc hiệu chỉnh ngưỡng `retrieval.thresholds` chạy với `chunking: docproc` (384/512 token, tokenizer của model đang đo), vì phân bố điểm và thứ hạng phụ thuộc kích thước chunk. RQ5 so model khác nhau thì đếm token bằng tokenizer của từng model nhưng giữ cùng `target/max`.
- `sopilot_ai.retrieval.lexical` và `fusion` thuộc `V2-09`; trước khi có, `V2-07` dùng tokenizer BM25 và RRF của harness, vốn là bản gốc mà service phải khớp (§6.3).
- Kiểm tra V2-09: cùng corpus V2-06, cùng cấu hình → top-10 của service (qua DB, một workspace, OWNER) và của harness trùng ≥ 95% theo Jaccard trung bình; khác biệt chỉ do HNSW xấp xỉ.

---

## 7. Hỏi đáp (FR-11..FR-15)

### 7.1 Các bước

**Sửa 2026-11-08 (owner chốt, [HANDOFF-V2-10](../../04-reports/HANDOFF-V2-10-qa-pipeline-2026-11-08.md)): pipeline là chuỗi bước, `QueryFrame`, cổng ngưỡng lỏng.** Kiến trúc QA không đổi; ba điều chỉnh dưới đây chỉ đổi cách tổ chức và cách hiệu chỉnh.

- **Chuỗi bước và `Decision`.** `qa/pipeline.py` chạy một danh sách bước theo đúng thứ tự 1–12 bên dưới (hạn mức → kiểm đầu vào → PII → guard → router luật → token có nghĩa → viết lại/nối tiếp → truy xuất + cổng → ghép context → prompt → sinh/stream + canary → hậu xử lý trích dẫn → nhận diện tự từ chối → kiểm số/ngày). Mỗi bước nhận một context dùng chung và trả về `Decision` thuộc `continue | template | refuse | clarify`: `continue` chuyển sang bước kế; `template` trả câu mẫu (`outcome = TEMPLATE`); `refuse` là từ chối (guard: `outcome = REFUSED_GUARD`, không có `refusal_reason`; thiếu bằng chứng: `NO_EVIDENCE`; `OUT_OF_SCOPE` do `V2-27` thêm); `clarify` chỉ khai báo trong kiểu, **chưa bước nào phát ra** (dành cho ticket sau, không có nhánh hỏi lại ở V2-10). Điểm gắn `OUT_OF_SCOPE` của `V2-27` nằm ở bước từ chối sau cổng (bước 8). Số lần gọi LLM vẫn tối đa 2 (viết lại khi có lịch sử, và sinh).
- **`QueryFrame`.** `qa/query_frame.py` là hàm thuần, dựng `QueryFrame` **một lần** sau bước PII (văn bản đã che, trước guard), gom: ngôn ngữ (tỉ lệ ký tự có dấu, ghi đè được bằng `lang` của request), mã tài liệu (dùng lại `qa/doc_code.py`), ngày và số tiền, dấu hiệu nối tiếp (`qa/followup_rules.yaml`), dấu hiệu so sánh/nhiều ý (từ khóa trong YAML như "so sánh", "khác nhau", "khác gì", "vs", "compare", "difference", hoặc ≥ 2 mã tài liệu) và số token có nghĩa (tính sau "bóc"). Router, truy xuất và prompt đọc từ `QueryFrame`, không tự phát hiện lại. Dấu hiệu so sánh **chỉ ghi** vào `messages.route` (`route.signals.comparison = true`), không rẽ nhánh và không đổi truy xuất (tách câu nhiều ý vẫn hoãn, D9).
- **Cổng ngưỡng để lỏng, LLM tự từ chối.** Giữ ngưỡng giữ chỗ trong `config/models.yaml` (`hybrid: 0.45`); cổng chỉ chặn khi điểm rất thấp, không hạ thêm và không đặt giá trị mới từ số RQ3. Lý do: cosine là cổng yếu (khoảng điểm của câu trả lời được và câu ngoài kho chồng lấn, [AUDIT-eval-rq1-rq3](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) §6; V2-07 §6, chốt 2026-11-07), nên đặt ngưỡng chặt sẽ từ chối nhầm câu hợp lệ. Phần còn lại giao cho LLM sinh: câu qua cổng nhưng LLM mở đầu bằng câu cố định của bước 6 → `GENERATOR_NOT_FOUND` (D2, bước 10). Mọi câu có truy xuất đều ghi `gate_score`, `threshold` và loại từ chối (`NO_EVIDENCE` | `GENERATOR_NOT_FOUND` | không từ chối) vào `messages.route` để hiệu chỉnh sau.

- **Quyết định khi triển khai (V2-10 mốc 3, 2026-11-09).**
  - *Hạn mức.* Bước 1 đặt chỗ nguyên tử (`INSERT … ON CONFLICT … DO UPDATE … WHERE questions < giới_hạn`) và hoàn lại khi kết thúc bằng `TEMPLATE`, `REFUSED_GUARD` hoặc `ERROR`. `ANSWERED` và `REFUSED_NO_EVIDENCE` (cả `GENERATOR_NOT_FOUND`) vẫn tính vì đã tốn embedding hoặc LLM. Cả hai giới hạn bằng 0 thì không đọc hay ghi bảng nào.
  - *Lịch sử cho bước viết lại* là tối đa 3 cặp (câu hỏi, câu trả lời) có `outcome = ANSWERED` và chưa bị ẩn (§7.5); lượt bị từ chối hay trả bằng câu mẫu không phải lịch sử. Hội thoại chưa có lượt `ANSWERED` nào thì không có gì để viết lại và câu đi tiếp với câu gốc.
  - *Kiểm echo bỏ câu mở đầu cố định.* Văn bản `protected` mà output guard so sánh không chứa câu mở đầu của bước 6, vì LLM được yêu cầu nói đúng câu đó. Nếu để lại, mọi `GENERATOR_NOT_FOUND` bị đổi thành `REFUSED_GUARD` (integration test phát hiện ở mốc 3).
  - *Ghi một lần ở cuối.* Hội thoại mới (nếu có), tin USER, tin ASSISTANT, trích dẫn, `retrieval_results` và `guard_events` ghi trong **một** `tenant_tx` sau khi pipeline xong; `citations` và `done` chỉ phát sau khi ghi xong. Client ngắt giữa chừng: ghi tin `ERROR` kèm `route.aborted = true`, nội dung là phần văn bản client đã nhận (không gồm đoạn guard đang giữ lại), và hoàn lượt hạn mức; luồng đọc LLM tự đóng kết nối ở thread đọc sau lần đọc hiện tại. `tokens_in`/`tokens_out` để `NULL` vì stream không trả `usage`; `messages.model` là model thực sự trả lời (`on_start` của `LLMChain`).
  - *Dựng service lúc có câu hỏi đầu tiên* (nạp embedder, kiểm `/models`), không phải lúc khởi động, để API vẫn chạy khi chưa có model hay endpoint LLM; thiếu cấu hình thì câu hỏi nhận `503`. Tiêu đề hội thoại là ≤ 60 ký tự đầu của câu hỏi đã che PII, cắt ở ranh giới từ.

1. **Hạn mức** (§7.4), bỏ qua khi tắt (mặc định). Hết → SSE `error {code: QUOTA_EXCEEDED}`; không gọi gì thêm.
2. **Kiểm đầu vào và guard** (lớp 1 FR-13):
   - **Hợp lệ (D4):** câu rỗng hoặc chỉ có khoảng trắng sau NFC, hoặc dài hơn `SOPILOT_MAX_QUESTION_CHARS=1000` ký tự (đếm code point sau NFC) thì **từ chối, không cắt bớt**: SSE `refusal {reason: "INPUT_INVALID"}` với câu mẫu nêu giới hạn (câu quá dài) hoặc đề nghị nhập câu hỏi (câu rỗng), `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, không gọi LLM, không tính hạn mức. Không có phần nào của câu quá dài lọt qua guard.
   - **Che PII (D8):** `qa/pii.py` nhận diện bằng luật: email; số điện thoại VN (`+84` hoặc `0` kèm 9 chữ số, cho phép khoảng trắng, dấu chấm, gạch ngang); số CCCD/CMND (9–12 chữ số; owner chốt 2026-11-08, che cả độ dài 10–11 thường gặp) và số tài khoản (9–16 chữ số) **chỉ khi** đi sau một từ khóa trong 20 ký tự (`cccd`, `cmnd`, `căn cước`, `hộ chiếu`, `passport`, `stk`, `số tài khoản`, `account`), để số tiền như `500.000.000` không bị che nhầm. Thay bằng `[EMAIL]`, `[PHONE]`, `[ID]`, `[ACCOUNT]`, ghi `guard_events(INPUT_FLAG)` với `rule_id = pii.email|phone|id|account` và `messages.checks.pii`. Bản đã che là **văn bản làm việc** cho mọi bước sau (guard, router, viết lại, embed, prompt) và cho các lượt lịch sử gửi đi viết lại; `messages.content` lưu nguyên văn.
   - **Guard:** chuẩn hóa (NFC, bỏ dấu, leetspeak `0→o, 1→i, 3→e, 4→a, 5→s, 7→t`). Luật VI/EN hai mức, viết trong `qa/guard_rules.yaml` (không trong code):
   - **Chặn:** đòi lộ system prompt/quy tắc ẩn/khóa API; ghi đè chỉ dẫn nhắm vào chỉ dẫn/prompt; giả mạo vai trò hệ thống (`system:`, `[INST]`, `<|im_start|>`). Trả câu từ chối cố định, `outcome = REFUSED_GUARD`, ghi `guard_events(INPUT_BLOCK)`.
   - **Gắn cờ:** đóng vai, "bỏ qua bước", nhắc workspace khác. Vẫn trả lời, ghi `guard_events(INPUT_FLAG)`.
   - **Nhóm có hại thật (V2-10):** đe dọa, tự hại, quấy rối (`harm.threat|self_harm|harassment`) có luật chặn riêng, chỉ khớp khi có ý định rõ (ví dụ "muốn quấy rối đồng nghiệp", không khớp "quy trình xử lý quấy rối"). Trả câu cố định (`harm_block`); tự hại trả `self_harm` kèm đầu mối liên hệ cấu hình được (`PipelineContext.support_contact`, nguồn cấu hình thêm ở mốc API), chưa cấu hình thì dùng `self_harm_no_contact`. `guard_events(INPUT_BLOCK)` chỉ lưu `rule_id`.
   - **Từ điển thô tục** trong `guard_rules.yaml` (mục `abuse`), so khớp theo ranh giới từ trên token, không theo chuỗi con: danh sách có dấu, danh sách bỏ dấu chỉ cho teencode không có nghĩa khác, và danh sách `standalone_only` ("cc", "đm", "vl"… có thể là "chứng chỉ", "định mức", "vật liệu") chỉ tính khi câu không quá `standalone_max_tokens` token và token không dính `-`/`/` (mã tài liệu như `QT-VL-02`). Từ thô tục không tự quyết định gì: router bóc chúng ra rồi xét phần còn lại, ghi `guard_events(INPUT_FLAG)` `abuse.profanity|abuse.standalone`.
   - Luật khởi đầu port từ `eval/provider_check/check_providers.py::RULE_PATTERNS`, sau đó điều chỉnh bằng **bộ câu kiểm tra riêng** của V2-10 (không trùng bộ dùng để viết luật). Luật chặn viết hẹp có chủ đích để không chặn câu SOP thường gặp ("quy tắc ăn mặc", "quy tắc nội bộ", "tắt bộ lọc spam"): "ẩn" và "an" trùng khi bỏ dấu nên luật "quy tắc ẩn" so trên văn bản còn dấu.
3. **Router luật:** chào hỏi/cảm ơn/hỏi về bot (VI/EN) → câu mẫu, `outcome = TEMPLATE`, không gọi LLM, không tính hạn mức. Câu luật chưa quyết đi qua **semantic router** (owner chốt 2026-10-20, chi tiết và ngưỡng ở `V2-27`): so embedding câu hỏi gốc với câu mẫu trong `qa/router_exemplars.yaml`, rẽ sang câu mẫu chỉ khi vượt ngưỡng của intent và `margin` so với câu SOP mẫu gần nhất; không gọi LLM, bật/tắt bằng `SOPILOT_SEMANTIC_ROUTER_ENABLED`. Vector của câu gốc chỉ được dùng lại cho dense retrieval khi chưa có lịch sử **và** văn bản làm việc (đã che PII, đã bóc token chào hỏi/thô tục theo V2-10) trùng câu gốc; ngược lại truy xuất embed lại đúng chuỗi dùng để tìm (D5). Quyết định của router ghi vào `messages.route`.
   - **"Bóc rồi xét" (V2-10):** router bóc token chào hỏi, cảm ơn, hỏi về bot (từ khóa trong `qa/templates.yaml`, so sau khi bỏ dấu) và token thô tục khỏi câu. Hết token → câu mẫu theo loại đã bóc (thô tục > hỏi về bot > cảm ơn > chào); còn token nhưng dưới ngưỡng token có nghĩa → cùng quy tắc, và nếu không bóc được gì thì "chưa hiểu câu hỏi". Còn nội dung → RAG trên câu đã bóc. `refusal_reason = INPUT_INVALID` chỉ đi với câu mẫu "chưa hiểu câu hỏi".
   - **Token có nghĩa (D4):** sau "bóc rồi xét" (V2-10), token có nghĩa là token `\w+` (chữ thường, NFC) có trong `rag.chunk_terms` của tập tài liệu người hỏi được đọc (cùng CTE `scope` của §6.3, nên không lộ từ ngoài quyền) hoặc trong `qa/lexicon.yaml` (từ VI/EN thông dụng, owner duyệt; khớp không dấu chỉ cho cụm nhiều từ vì một từ đơn bỏ dấu dễ trùng nghĩa, ví dụ "đúng"/"dùng"). Số token có nghĩa dưới `min_meaningful_tokens` (mặc định 1, trong `qa/guard_rules.yaml`) → câu mẫu "chưa hiểu câu hỏi", `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, không truy xuất.
   - **Router mở rộng (D1, V2-27):** `off_topic` **không** rẽ ở đây: nó chỉ có hiệu lực sau khi cổng từ chối (bước 8) vì router không biết kho chứa gì. `action_request`, `personal_data`, `legal_medical` chỉ gắn câu miễn trừ (bước 12), vẫn chạy RAG. `about_source` (cần có lịch sử) và `feedback_in_chat` (chỉ khi phần còn lại sau "bóc" rỗng) trả câu mẫu ngay, không gọi LLM: `about_source` liệt kê lại trích dẫn của lượt trước từ `message_citations`, `feedback_in_chat` hướng dẫn bấm 👎.
4. **Viết lại câu hỏi** chỉ khi hội thoại có ≥ 1 lượt trước: gửi tối đa 3 lượt gần nhất (chỉ câu hỏi và câu trả lời đã làm sạch, không gửi chunk) cho `llm.rewrite`, nhận câu hỏi độc lập; các lượt lịch sử cũng dùng bản đã che PII (bước 2). Ghi `messages.rewrite_status` (`OK` | `FAILED`; `NONE` khi không có lịch sử). Lỗi → dùng câu hỏi gốc, **trừ khi** câu có dấu hiệu nối tiếp (luật `qa/followup_rules.yaml`: đại từ chỉ định như "đó", "này", "vậy còn", "thế còn", "it", "that", "what about", hoặc ít hơn `SOPILOT_FOLLOWUP_MAX_TOKENS` token) thì **không truy xuất**: trả câu mẫu đề nghị nêu đầy đủ câu hỏi, `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, `route.layer = 'followup_rule'` (D5). Câu không có dấu hiệu nối tiếp đi tiếp với câu gốc. Câu đã viết lại được đưa tiếp cho truy xuất và cho prompt sinh (bước 5, 6).
5. **Truy xuất** (§6) trên văn bản làm việc (câu đã viết lại nếu có, ngược lại câu đã che và bóc). Dưới ngưỡng → bước 8. Đủ ngưỡng → ghép context (§6.4a).
6. **Ghép prompt** (lớp 2): system prompt cố định theo `prompt_version`, chứa canary token ngẫu nhiên sinh mỗi request và quy tắc: chỉ dùng dữ liệu trong thẻ, trả lời theo ngôn ngữ câu hỏi, mỗi khẳng định gắn `[n]`, thiếu thông tin thì **bắt đầu câu trả lời bằng đúng câu mở đầu cố định** theo ngôn ngữ ("Không tìm thấy thông tin này trong các tài liệu hiện có." / "I could not find this in the available documents.", D2), giữ điều kiện áp dụng và ngoại lệ có trong source; với câu tình huống (có dữ kiện cụ thể của người hỏi) thì liệt kê điều kiện liên quan, nói điều kiện nào thỏa và điều kiện nào chưa đủ dữ kiện rồi trả lời dạng "nếu … thì …"; khi câu hỏi về mã tài liệu, lần ban hành hay ngày hiệu lực thì dùng `code`, `rev`, `effective` của source. System prompt có dòng "Hôm nay là {YYYY-MM-DD}" theo múi giờ `SOPILOT_TIMEZONE` (mặc định `Asia/Ho_Chi_Minh`) để hiểu "tuần trước", "hiện hành". Đổi prompt thì đổi `prompt_version`. Mỗi source của §6.4a bọc trong `<source n="1" title="…" page="3" code="QT-MH-01" rev="03" effective="2026-03-01">…</source>` (D3): `code`, `rev`, `effective` lấy từ `extracted_documents.extracted_meta` (`docCode`, `revisionLabel`, `effectiveDate`) của `version_id` của source, trong bảng `rag` (không đọc `core`); thuộc tính không có thì bỏ; giá trị được escape như nội dung. Các trường này chỉ vào prompt, **không** vào `index_text` (giữ cache embedding, §5.4). Escape `<`, `>`, `&` trong nội dung. Câu hỏi nằm ở message `user` riêng, không ghép vào system, và **không có lịch sử hội thoại** (D5): lịch sử chỉ được bước 4 dùng để làm rõ câu hỏi. Message `user` gồm `Câu hỏi:` là câu đã viết lại (khi bước 4 thành công) hoặc câu đã che PII, và thêm `Câu gốc:` khi hai câu khác nhau, để LLM đối chiếu nếu bước viết lại lệch ý.
7. **Sinh và stream** (lớp 3): SSE `delta` phát văn bản nhưng **giữ lại** `max(len(canary), 40) + 32` ký tự cuối chưa phát (40 là cửa sổ echo; canary 23 ký tự cho 72). Mỗi delta mới, kiểm tra buffer có chứa canary hoặc đoạn ≥ 40 ký tự liên tiếp của system prompt không. Có → dừng stream, phát `replace` với câu từ chối cố định, `outcome = REFUSED_GUARD`, `guard_events(OUTPUT_CANARY | OUTPUT_PROMPT_ECHO)`.
8. **Từ chối thiếu bằng chứng** (FR-12): câu trả lời cố định theo ngôn ngữ câu hỏi + tối đa 3 "tài liệu gần nhất" (tiêu đề của tài liệu chứa ứng viên đầu, đã qua bộ lọc quyền nên không lộ tài liệu ngoài quyền), `outcome = REFUSED_NO_EVIDENCE`, `refusal_reason = NO_EVIDENCE`. Không gọi LLM sinh. Nếu router xếp câu `off_topic` vượt ngưỡng (V2-27, chỉ xét tại bước này, D1) thì `refusal_reason = OUT_OF_SCOPE`: cùng câu từ chối nhưng **không** kèm "tài liệu gần nhất". Router không bao giờ làm đổi một quyết định "cho qua" của cổng.
9. **Hậu xử lý trích dẫn** (FR-11): tìm `[n]` trong văn bản cuối; `n` không ứng với source nào trong prompt → xóa khỏi văn bản. Mỗi `n` hợp lệ lưu `message_citations` theo quy tắc trích dẫn của §6.4a (đoạn trích là `content` của các chunk trúng trong source). Ghi `messages.checks.citationCount` = số `[n]` hợp lệ còn lại.
10. **Nhận diện LLM tự từ chối (D2):** nếu văn bản cuối (đã `strip`, so không phân biệt hoa thường, bỏ dấu câu ở đầu) bắt đầu bằng câu mở đầu cố định của bước 6 thì `outcome = REFUSED_NO_EVIDENCE`, `refusal_reason = GENERATOR_NOT_FOUND`, không lưu trích dẫn. So khớp chuỗi tất định; unit test cho cả hai ngôn ngữ.
11. **Kiểm số và ngày (V2-10):** `qa/checks.py` (hàm thuần) trích số, ngày, số tiền từ `finalText`, chuẩn hóa (bỏ dấu phân cách nghìn, `dd/mm/yyyy` về ISO) và đối chiếu với nội dung các source đã đưa vào prompt. Giá trị không có trong source → `done.warnings: [{code: "NUMBER_NOT_IN_SOURCES", values: […]}]` và `messages.checks.numberWarnings`. **Chỉ gắn cờ, không sửa hay xóa văn bản** (đã stream ra); số viết bằng chữ không được nhận diện nên không báo.
12. **Câu miễn trừ (V2-27):** câu router gắn `action_request`, `personal_data` hoặc `legal_medical` vẫn được trả lời; sau khi sinh xong, phát thêm một `delta` chứa câu miễn trừ cố định theo ngôn ngữ (lấy từ `qa/templates.yaml`) trước `citations`, đưa vào `finalText` và ghi `messages.checks.disclaimers`. Router không chặn câu nào.

Ngôn ngữ câu hỏi phát hiện bằng luật nhẹ (tỷ lệ ký tự có dấu tiếng Việt) và có thể ghi đè bằng `lang` trong request.

### 7.2 SSE

`POST /ai/v1/conversations/{conversationId}/messages` với `Accept: text/event-stream`. Body `{ "content": "…", "lang": "vi" | "en" | null }`. `conversationId = "new"` tạo hội thoại mới.

| Sự kiện | Dữ liệu | Khi nào |
|---|---|---|
| `meta` | `{conversationId, messageId, mode, lang}` | Đầu tiên |
| `delta` | `{text}` | Mỗi đoạn văn bản |
| `replace` | `{text, reason: "GUARD"}` | Phát hiện canary/echo giữa chừng |
| `refusal` | `{text, reason: "NO_EVIDENCE" \| "OUT_OF_SCOPE" \| "INPUT_INVALID" \| "GUARD", nearestDocuments: [{documentId, title}]}` | Từ chối, thay cho `delta`. `nearestDocuments` chỉ có (và có thể rỗng) khi `NO_EVIDENCE`; các lý do khác không kèm tài liệu |
| `citations` | `[{n, documentId, versionId, title, page, charStart, charEnd, snippet}]` | Sau khi sinh xong |
| `done` | `{finalText, outcome, refusalReason, warnings: [{code, values}], usage: {questionsLeftToday}}` (`usage` là `null` khi hạn mức tắt; `refusalReason` là `null` khi không từ chối; `warnings` rỗng khi không có cờ, §7.1 bước 11) | Cuối cùng; frontend thay văn bản đã stream bằng `finalText` (đã xóa `[n]` không hợp lệ) |
| `error` | `{code, message}` | `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR` |

**Kết quả → sự kiện (triển khai mốc 3).**

| Kết quả | Sự kiện |
|---|---|
| `ANSWERED` | `delta`…, `citations` (nếu có), `done` |
| Câu mẫu không phải từ chối (chào hỏi, cảm ơn, hỏi về bot, chỉ chửi) | một `delta` rồi `done`; `outcome = TEMPLATE`, `refusalReason = null` |
| `INPUT_INVALID` (rỗng, quá dài, không hiểu, nối tiếp không rõ) | `refusal`, `done` |
| Guard đầu vào | `refusal {reason: "GUARD"}`, `done` (`REFUSED_GUARD`) |
| Guard đầu ra (canary, echo) | `delta`… đã phát, rồi `replace`, `done` (`REFUSED_GUARD`) |
| `NO_EVIDENCE` | `refusal` kèm `nearestDocuments`, `done` |
| `GENERATOR_NOT_FOUND` | câu của model đã stream bằng `delta`; chỉ `done`, không `citations` |
| `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR` | chỉ `error` (không có `done`); lượt vẫn được ghi (`outcome` là `QUOTA_EXCEEDED` hoặc `ERROR`) |

Body `content` tối đa 20.000 ký tự (vượt thì `422`); từ 1.001 đến 20.000 ký tự nhận câu mẫu "quá dài" (D4). `conversationId` không phải `new` hay UUID, hoặc không phải của người gọi, là `404`.

Header `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Ping comment `: ping` mỗi 15 s để proxy không cắt kết nối.

### 7.3 Trình xem trích dẫn (FR-14) và "Nội dung hệ thống nhận diện" (FR-31)

`GET /ai/v1/documents/{documentId}/versions/{versionId}/content` trả từ `extracted_documents`, chỉ khi tài liệu qua bộ lọc §6.1 và `versionId` là phiên bản đang hoạt động (`active_version_id`); ngược lại `404` (không phân biệt "không tồn tại", "ngoài quyền" và "chưa READY"):

```json
{ "documentId": "…", "versionId": "…", "fileType": "PDF", "normalizerVersion": "1",
  "markdown": "# Quy trình mua hàng\n\n…",
  "pages": [ {"page": 1, "charStart": 0, "charEnd": 812, "charStart16": 0, "charEnd16": 812} ],
  "warnings": [ {"code": "PAGES_WITHOUT_TEXT", "pages": [3, 7]} ],
  "removedBlocks": [ {"kind": "footer", "page": 1, "text": "QT-MH-01 | Lần ban hành 03 | Trang 1/7"} ] }
```

- Màn xem FR-31 và trình xem trích dẫn dùng chung response này. PDF gốc được frontend mở bằng URL ký sẵn của core-api (`/api/v1/documents/{id}/download-url`) và nhảy tới `page`; MD hiển thị `markdown` và tô sáng `[charStart16, charEnd16)`.
- Chỉ có endpoint cho phiên bản đang hoạt động; không có đường đọc phiên bản đang xử lý hay `FAILED` (owner chốt 2026-10-21: màn xem chỉ mở khi `READY`). Frontend lấy `currentVersion` và `latestVersion` từ core-api để gắn nhãn phiên bản.
- `removedBlocks` giới hạn 200 mục; `markdown` trả nguyên văn, frontend render không thực thi HTML.

### 7.4 Hạn mức và giới hạn provider (FR-09)

Hạn mức thương mại tạm tắt (owner chốt 2026-10-20, PRD-V2 §8.10): hai biến dưới đây mặc định `0` = không giới hạn, không đọc/ghi `usage_counters` và `system_usage`. Bảng vẫn có trong migration để bật lại không cần đổi schema.

- **Theo user:** `SOPILOT_QUOTA_QUESTIONS_PER_USER_DAY` (tham khảo `20` theo PRD FR-09 khi bật). Tăng `usage_counters` trong transaction đầu request, **trước** khi gọi LLM; câu `TEMPLATE` và `REFUSED_GUARD` không tính.
- **Toàn hệ thống:** `SOPILOT_QUOTA_QUESTIONS_SYSTEM_DAY` (tham khảo `400` khi bật) qua `rag.system_usage`.
- Bộ giới hạn theo provider bên dưới **luôn bật** vì là giới hạn kỹ thuật của free tier, không phải hạn mức thương mại.
- **Theo provider:** token bucket trong bộ nhớ cho RPM và TPM của từng `(provider, model)` lấy từ `models.yaml` (một tiến trình API nên không cần Redis). Ước lượng token prompt trước khi gọi; hết bucket → coi như `429` và chuyển model kế tiếp trong `chain`. Hết cả chuỗi → `error LLM_UNAVAILABLE`, hoàn lại lượt hạn mức của user nếu hạn mức đang bật.
- **Không chuyển model giữa chừng (owner chốt 2026-10-21, P1-5).** Chỉ được chuyển sang model kế tiếp **trước khi** phát `delta` đầu tiên. Lỗi sau đó (ngắt kết nối, `5xx`, hết bucket) → `error LLM_UNAVAILABLE`, `outcome = ERROR`, hoàn lượt hạn mức; không chạy lại bằng model khác vì văn bản đã phát sẽ bị lặp.
- **Trần context theo model.** Mỗi mục trong `chain` có `context_max_tokens` (§4.2). Chuyển sang model có trần thấp hơn `context.max_tokens` thì ghép lại context với trần đó (cắt source hạng thấp trước, source hạng 1 giữ nguyên) rồi mới gọi. Ước lượng token prompt dùng tokenizer của chính model nếu `models.yaml` khai báo `tokenizer`, ngược lại dùng ước lượng thô theo số ký tự; chỉ để tính ngân sách, không dùng để chunk (chunk dùng tokenizer của embedding, §5.4).

### 7.5 Hội thoại (FR-15) và lịch sử khi mất quyền

| Method & path | Ghi chú |
|---|---|
| `GET /ai/v1/conversations` | Hội thoại của `sub` trong `wid`, mới nhất trước |
| `GET /ai/v1/conversations/{id}` | Tin nhắn + trích dẫn; `404` nếu không phải của mình |
| `PATCH /ai/v1/conversations/{id}` | Đổi tên |
| `DELETE /ai/v1/conversations/{id}` | Xóa mềm |
| `POST /ai/v1/conversations/{id}/messages` | §7.2 |

Mọi truy vấn có `workspace_id = :wid AND user_id = :sub` (ngoài RLS). Khi đọc lại hội thoại, mỗi câu trả lời được kiểm với bộ lọc §6.1 hiện tại trên **mọi tài liệu nó được sinh ra từ đó**: mọi `documentId` trong `messages.context_sources` (source đã đưa vào prompt) hợp với `message_citations.document_id`. Nếu **bất kỳ** tài liệu nào trong tập đó không còn đọc được (đổi phạm vi, đổi phòng ban, bị xóa), toàn bộ câu trả lời và đoạn trích của nó bị thay bằng `{hidden: true, reason: "ACCESS_REVOKED" | "DOCUMENT_DELETED"}`; câu hỏi vẫn hiện (PRD §8.8). Lý do là `DOCUMENT_DELETED` khi một tài liệu trong tập đã xóa hoặc không còn dòng quyền, ngược lại `ACCESS_REVOKED`; điều kiện "đọc được" dùng đúng vị từ của `allowed_cte()` (`cited_access_cte()` trong `access_filter.py`). Viết lại câu hỏi (§7.1 bước 4) chỉ dùng các lượt chưa bị ẩn.

**Ẩn theo context, không chỉ theo trích dẫn (owner chốt 2026-11-09, V2-10 mốc 3).** Bản trước chỉ kiểm `message_citations`, nên câu trả lời không có `[n]` hợp lệ (`ANSWERED` với `checks.citationCount = 0`, `GENERATOR_NOT_FOUND`, `ERROR` giữa chừng) vẫn hiện sau khi mất quyền dù văn bản lấy từ source, và câu `ANSWERED` như vậy còn vào lịch sử viết lại. ADR-007 §4.4 tính "context LLM" là một hình thức đọc, nên mọi source trong context đều quyết định việc ẩn. Đánh đổi đã chấp nhận: ẩn thừa khi tài liệu bị thu quyền chỉ nằm trong context mà câu trả lời không thực sự dùng; trạng thái ẩn tính lại mỗi lần đọc nên câu trả lời hiện lại khi quyền được cấp lại. Trích dẫn vẫn được hợp vào tập kiểm (fail closed) dù mỗi trích dẫn đã trỏ vào một source của context.

**Trích dẫn tới phiên bản cũ (owner chốt 2026-10-21, D10).** Core-api xóa bản cũ khi có bản mới nên `/content` (§7.3) chỉ phục vụ phiên bản đang hoạt động và trả `404` cho `version_id` cũ. Khi đọc lại hội thoại, mỗi trích dẫn có thêm `isCurrentVersion` (so `version_id` của trích dẫn với `rag.document_access.active_version_id`). Trích dẫn không còn là bản hiện hành vẫn hiện `snippet` đã lưu (`message_citations.snippet`), frontend gắn nhãn "Phiên bản cũ" và không mở trình xem. MVP không giữ `extracted_documents` của phiên bản cũ.

### 7.6 Phản hồi và khoảng trống tri thức (FR-16, FR-17)

Owner chốt 2026-10-20 (TECH-V2-core-api §11 Q1, ADR-004 §4.1): FR-16/FR-17 nằm ở ai-service.

```sql
CREATE TABLE rag.message_feedback (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages(id) ON DELETE CASCADE,
    user_id      uuid NOT NULL,
    vote         smallint NOT NULL CHECK (vote IN (-1, 1)),
    comment      text CHECK (length(comment) <= 1000),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, user_id)
);
CREATE TABLE rag.knowledge_gap_status (
    workspace_id uuid NOT NULL,
    message_id   uuid PRIMARY KEY REFERENCES rag.messages(id) ON DELETE CASCADE,
    resolved_by  uuid NOT NULL,
    resolved_at  timestamptz NOT NULL DEFAULT now(),
    note         text
);
```

- `PUT /ai/v1/messages/{id}/feedback` `{vote, comment}`: chỉ người tạo hội thoại, chỉ tin nhắn `ASSISTANT`.
- `GET /ai/v1/knowledge-gaps?status=open|resolved`: OWNER, ADMIN; gồm (owner chốt 2026-10-21, D2) câu có `refusal_reason` là `NO_EVIDENCE` hoặc `GENERATOR_NOT_FOUND`, câu trả lời bị downvote, và câu `ANSWERED` có `checks.citationCount = 0`; kèm câu hỏi, thời gian, phản hồi. **Loại** câu `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE` và `REFUSED_GUARD`. Không kèm tên người hỏi (giữ riêng tư hội thoại FR-15). Câu hỏi hiện cho admin là bản **đã che PII** (§7.1 bước 2, tính lại bằng `qa/pii.py` khi trả lời, không lưu bản thứ hai); người hỏi vẫn xem được nguyên văn câu của mình.
- `POST /ai/v1/knowledge-gaps/{messageId}/resolve`: OWNER, ADMIN.

---

## 8. API nội bộ phía ai-service

Định nghĩa contract ở TECH-V2-core-api §8. Phía ai-service:
- Mọi endpoint `/internal/**` kiểm `Idempotency-Key`: đã có trong `processed_requests` → trả lại response thành công, không làm lại. Ghi khóa trong cùng transaction với thay đổi.
- `POST /internal/ingestions`: `UPSERT rag.document_access` chỉ khi `accessRevision` lớn hơn bản đang có (hoặc chưa có); `INSERT ingestion_jobs ... ON CONFLICT (version_id) DO UPDATE SET status = 'QUEUED', attempts = 0, failure_code = NULL, request_attempt = EXCLUDED.request_attempt, lease_until = NULL WHERE ingestion_jobs.status = 'FAILED' AND EXCLUDED.request_attempt > ingestion_jobs.request_attempt`; `NOTIFY rag_jobs`. Nghĩa là: gửi lại cùng yêu cầu (cùng `attempt`) không tạo job mới; thử lại của người dùng (`attempt` tăng, TECH-V2-core-api §5.5) đưa job `FAILED` về hàng đợi; job đang chạy hoặc `DONE` không bị đụng. (Sửa 2026-10-21: bản trước dùng `DO NOTHING` nên thử lại sẽ không bao giờ chạy.)
- `PUT /internal/document-access/{documentId}`: cập nhật nếu `accessRevision` mới hơn; trả `{applied}`. Không động tới chunk (FR-26: đổi phạm vi không embed lại).
- `DELETE /internal/documents/{documentId}`: đặt `document_access.deleted_at` (truy xuất bỏ tài liệu ngay), hủy job đang chờ, xóa chunk, `extracted_documents`, `suggestion_jobs`, rồi xóa dòng `document_access`. `message_citations` giữ lại để lịch sử hiện lý do `DOCUMENT_DELETED`.
- Gửi về core-api: outbox `rag.outbox_events`, dispatcher giống core-api (đẩy ngay sau commit + quét mỗi 5 s, backoff, `DEAD` sau 20 lần, `4xx` không thử lại).

---

## 9. Chiến lược kiểm thử

| Lớp | Nội dung | Công cụ |
|---|---|---|
| Unit `docproc` | Fixture PDF hai cột, bảng giữa thân, ô gộp, header/footer lặp; MD (frontmatter, GFM table, HTML nhúng, shortcode); từ chối DOCX/TXT; SOP ISO có bảng quy trình; văn bản Điều/Khoản có câu dẫn chiếu "Điều 5" giữa câu; kiểm `section_path` là tổ tiên; không cắt giữa ký tự; chunk ≤ `max_tokens` theo tokenizer của model | pytest |
| Markdown chuẩn và offset | Bất biến `markdown[char_start:char_end]` = đoạn render của phần tử, cho mọi phần tử của mọi fixture và mọi file corpus V2-19; offset chunk nằm trong `markdown`; `row_spans` tăng dần, nằm trong bảng, `markdown[row_spans[i]]` chứa đúng các ô của `rows[i]`; bảng nhiều trang có `page_end > page`; `page_index` liên tiếp, không chồng, trang trong `1..page_count`; offset UTF-16 đúng với chuỗi có ký tự ngoài BMP; render hai lần cùng đầu vào cho cùng chuỗi; văn bản NFC; không phần tử khung nào xuất hiện trong `markdown` | pytest (property test trên fixture) |
| Cảnh báo | Mỗi mã §5.3a có một fixture sinh ra nó và một fixture sạch không sinh ra nó; OCR tắt: trang chỉ có ảnh cho 0 ký tự | pytest |
| Chất lượng trích xuất | Chỉ số trên corpus V2-19 (heading recall, khung lọt, nội dung bị xóa nhầm) | Script trong `eval/`, không chạy trong CI |
| Unit truy xuất | BM25 SQL và BM25 harness cho cùng điểm (sai số 1e-4) trên corpus nhỏ; RRF; hệ số BM25 theo ngôn ngữ (`1.0` cho kết quả như RRF thường, `lang` NULL không bị giảm); cổng ngưỡng từng chế độ; ghép context §6.4a (nhóm nhỏ lấy nguyên, nhóm lớn lấy ±1 kèm đoạn dẫn cho `PROCEDURE_STEP`, gộp cửa sổ liền nhau, trần token, source hạng 1 luôn có, `expand = false` giữ hành vi cũ, khoảng trích dẫn chỉ phủ chunk trúng); trích dẫn `[n]` không hợp lệ bị loại; canary bị phát hiện kể cả khi bị cắt qua hai delta | pytest |
| Integration | Testcontainers Postgres + pgvector với role `sopilot_ai_app` thật: RLS, job lease hết hạn được nhận lại, lỗi tạm thời được tự thử lại sau `run_after` mà không gửi `FAILED`, lỗi tất định `FAILED` ngay ở lần đầu, thay bản mới không làm gián đoạn truy xuất, `accessRevision` cũ bị bỏ qua, idempotency; thử lại job `FAILED` với `attempt` mới chạy lại đúng một lần, gửi lại cùng `attempt` không tạo job; `/content` trả `404` cho phiên bản chưa kích hoạt, `FAILED` và ngoài quyền, trả phiên bản cũ trong lúc bản mới xử lý | pytest + testcontainers |
| FR-19 (phần ai-service) | Hai workspace, tài liệu chứa chuỗi bí mật riêng: hỏi đáp, hội thoại, trình xem nội dung, retrieval_results không bao giờ chứa chuỗi của workspace kia; connection tái dùng không mang `app.workspace_id` cũ | CI |
| FR-29 (phần ai-service) | Cùng workspace: tài liệu `DEPARTMENTS` có chuỗi bí mật không xuất hiện trong dense, BM25, rerank, chunk mở rộng của ghép context, prompt gửi LLM (provider giả ghi lại prompt), trích dẫn, lịch sử, "tài liệu gần nhất"; các ca đổi phòng ban (token mới), thu hẹp phạm vi, xóa tài liệu | CI, LLM giả |
| Guard | Bộ câu kiểm tra riêng V2-10: chặn nhầm ≤ 2%, 0 lần lộ canary | CI |
| Đầu vào và PII | Câu rỗng và > 1000 ký tự bị từ chối (không cắt); câu không có token có nghĩa; nối tiếp khi viết lại lỗi trả câu mẫu, không truy xuất; PII được che đúng, số tiền như `500.000.000` không bị che; `messages.content` nguyên văn nhưng danh sách khoảng trống hiện bản đã che | pytest |
| Outcome | `refusal_reason` đúng cho bốn trường hợp (§3.4); LLM giả mở đầu bằng câu cố định (VI/EN) → `GENERATOR_NOT_FOUND`; danh sách khoảng trống loại `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE`, `REFUSED_GUARD` và lấy `ANSWERED` không có trích dẫn; router `off_topic` không bao giờ đổi quyết định "cho qua" của cổng | pytest, LLM giả |
| Truy xuất bổ sung | Cổng `hybrid` với ứng viên đầu chỉ có điểm BM25 (harness và service cùng `gate_score`); term `~`: "quy trinh mua hang" khớp "quy trình mua hàng", câu tiếng Anh không đổi; mã `QT-MH-01` nhận diện và cộng `doc_code_boost` | pytest |
| Ô gộp và khung | `cell_spans` → `PROCEDURE_STEP` lặp giá trị ô gộp xuống từng hàng; PDF 1–2 trang không mất tiêu đề hay đoạn cuối do luật header/footer | pytest |
| Prompt | Provider giả ghi lại prompt: `<source>` có `code/rev/effective`, có dòng ngày hiện tại, **không** có lịch sử, có cả câu viết lại lẫn câu gốc; fallback không chuyển model sau `delta` đầu tiên; kiểm số/ngày chỉ gắn cờ | pytest, LLM giả |
| Contract | Cùng JSON Schema `services/contracts/` với core-api | CI |

---

## 10. Cấu hình (biến môi trường)

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `SOPILOT_DB_URL` | — | Role `sopilot_ai_app` |
| `SOPILOT_CORE_JWKS_URL`, `SOPILOT_CORE_BASE_URL` | `http://core-api:8080/.well-known/jwks.json`, `http://core-api:8080` | |
| `SOPILOT_INTERNAL_TOKEN` | — | Dùng chung với core-api |
| `SOPILOT_S3_ENDPOINT`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_AI_ACCESS_KEY`, `SOPILOT_S3_AI_SECRET_KEY` | — | Credential chỉ đọc |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | — | Chỉ trong `.env` |
| `SOPILOT_MODELS_CONFIG` | `config/models.yaml` | |
| `EMBEDDING_REVISION`, `RERANK_REVISION`, `RERANK_ENABLED` | —, —, `false` | |
| `SOPILOT_LLM_BASE_URL`, `SOPILOT_LLM_MODEL`, `SOPILOT_LLM_API_KEY` | —, —, — | Endpoint Modal (OpenAI-compatible); model id lấy từ `GET /models`. Thiếu thì lỗi khi khởi động (không có mặc định) |
| `SOPILOT_LLM_RPM`, `SOPILOT_LLM_TPM`, `SOPILOT_LLM_CONTEXT_MAX_TOKENS` | `60`, `200000`, trống | Giữ chỗ, đo trên endpoint; trống trần = chưa khai báo |
| `SOPILOT_QUOTA_QUESTIONS_PER_USER_DAY`, `SOPILOT_QUOTA_QUESTIONS_SYSTEM_DAY` | `0`, `0` | FR-09, `0` = tắt (giai đoạn nghiên cứu) |
| `SOPILOT_INGEST_MAX_ATTEMPTS`, `SOPILOT_SUGGEST_TIMEOUT`, `SOPILOT_SUGGEST_MAX_INPUT_TOKENS` | `3`, `20s`, `1500` | |
| `SOPILOT_MAX_QUESTION_CHARS` | `1000` | §7.1 bước 2: dài hơn thì từ chối, không cắt (D4); đếm code point sau NFC |
| `SOPILOT_FOLLOWUP_MAX_TOKENS` | `4` | §7.1 bước 4: câu ngắn hơn mức này được coi là có dấu hiệu nối tiếp; giá trị khởi đầu, chưa đo, chỉnh bằng V2-27 |
| `SOPILOT_TIMEZONE` | `Asia/Ho_Chi_Minh` | Múi giờ của dòng "Hôm nay là …" trong system prompt (§7.1 bước 6) |
| `SOPILOT_HEADER_FOOTER_MIN_PAGES` | `3` | §5.3; giá trị khởi đầu, chốt trên corpus V2-19 |
| `SOPILOT_PAGE_MIN_CHARS` | `20` | Ngưỡng cảnh báo `PAGES_WITHOUT_TEXT` (§5.3a); giá trị khởi đầu, chưa hiệu chỉnh |
| `SOPILOT_PDF_ARTIFACTS_PATH` | `/models/pdf` (volume) | Model của thư viện PDF (nếu có) tải trước, không tải lúc xử lý |
| `HF_HOME` | `/models` (volume) | Model tải một lần, không tải lại mỗi lần khởi động |

---

## 11. Câu hỏi mở (owner chốt 2026-10-20)

Owner duyệt toàn bộ theo đề xuất bên dưới.

| # | Câu hỏi | Quyết định |
|---|---|---|
| Q1 | Phản hồi và khoảng trống tri thức ở service nào? | ai-service (§7.6); xem TECH-V2-core-api §11 Q1. |
| Q2 | BM25 tự viết trong SQL hay dùng extension? | Tự viết (§6.3) để khớp harness và không cần image Postgres riêng. |
| Q3 | Rerank: chỉ local, hay thêm provider API miễn phí (ví dụ Pinecone bge-reranker-v2-m3) cho máy yếu? | Local cho eval (ADR-006); interface đã cho phép thêm provider, chỉ làm khi đo thấy rerank local quá chậm cho demo. |
| Q4 | Kích thước chunk mặc định | `target 384 / max 512` token theo tokenizer bge-m3; V2-07 có thể đổi sau khi đo, cấu hình harness và service phải giống nhau. |
| Q5 | Worker cùng container với API hay container riêng? | Cùng image, hai tiến trình (hai service trong compose dùng chung image) để embed không chặn API và giới hạn RAM riêng được. |
| Q6 | Ngưỡng từ chối mặc định trước khi có V2-07 | Giữ chỗ (§4.2); không công bố chỉ số từ chối nào trước khi hiệu chỉnh trên tập dev. |
| Q7 | Màn xem FR-31 mở ngay sau convert/clean hay chỉ khi `READY`? (owner chốt 2026-10-21) | Chỉ khi `READY`. Mở sớm cần ghi `extracted_documents` trước embed, một đường đọc phiên bản chưa kích hoạt (phải test FR-19/FR-29), dọn dữ liệu khi lỗi và một trạng thái UI; ước lượng thêm 1–2 ngày trong khi khoảng chờ embed còn lại nhỏ. Xét lại khi số đo `t_ready` cho thấy cần. |
| Q8 | Thư viện PDF nào? (owner chốt 2026-10-21, [ADR-008](../adr/ADR-008-pdf-extraction-docling.md)) | **Docling** (MIT), ADR `approved`, **chưa có số đo spike**; PyMuPDF 2.x (AGPL-3.0 hoặc thương mại) không dùng. `V2-20` xác nhận Docling theo các tiêu chí dưới đây và điền kết quả vào ADR-008 §6; ràng buộc cứng không đạt thì dừng và hỏi owner. Ràng buộc cứng: offline trên CPU, OCR tắt được, số trang cho từng phần tử, tiếng Việt NFC, giấy phép (AGPL cần owner xác nhận). So sánh: heading/bảng theo họ tài liệu V2-19, thời gian và RAM đỉnh mỗi trang trên máy owner, công bảo trì. Timebox 2 ngày; chỉ một thư viện trong runtime. Chi tiết: [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) §6. |

### 11a. Quyết định từ audit đầu-cuối theo loại query (owner chốt 2026-10-21)

Owner chốt toàn bộ theo đề xuất của audit; không quyết định nào phá ràng buộc "một lần sinh, không LLM classifier, CPU, lọc quyền trước `LIMIT`".

| # | Câu hỏi | Quyết định | Nơi áp dụng |
|---|---|---|---|
| D1 | `off_topic` rẽ trước truy xuất hay chỉ gán nhãn sau khi cổng từ chối? | Sau cổng: chỉ khi cổng đã từ chối thì gán `OUT_OF_SCOPE`; router không bao giờ đổi quyết định "cho qua". Router không biết kho chứa gì nên không được chặn trước | §7.1 bước 3, 8; V2-27 |
| D2 | Thêm `refusal_reason` và câu mở đầu cố định khi LLM tự từ chối? | Có | §3.4, §7.1 bước 6, 10; §7.6; V2-10, V2-13 |
| D3 | Thêm `code`, `rev`, `effective` vào `<source>` và ngày hiện tại vào prompt? | Có; `index_text` không đổi; chunk thẻ `DOC_INFO` hoãn (§12a) | §7.1 bước 6; V2-10 |
| D4 | Câu > 1000 ký tự: từ chối hay cắt bớt? | Từ chối; câu rỗng cũng bị từ chối | §7.1 bước 2; V2-10 |
| D5 | Viết lại lỗi với câu nối tiếp: câu mẫu hỏi lại thay vì chạy RAG? | Có. Prompt sinh nhận câu đã viết lại cộng câu gốc, không nhận lịch sử; embed lại khi văn bản làm việc khác câu gốc | §7.1 bước 3–6; V2-10, V2-27 |
| D6 | Mở ngoại lệ §6.4a cho tham chiếu trong cùng tài liệu? | Chưa; `V2-19` đếm tần suất tham chiếu chéo trước | §6.4a, §12a; V2-19 |
| D7 | Thêm ticket bộ kiểm SOP tiếng Việt (30–40 câu)? | Có: `V2-28`, `total_tickets` 27 → 28 | PLAN-V2 |
| D8 | PII: che ở đâu, lưu bản nào? | Che khi gửi LLM, khi viết lại và trong danh sách khoảng trống; `messages.content` lưu nguyên văn cho người hỏi | §7.1 bước 2, §7.6; V2-10, V2-13 |
| D9 | Tách câu nhiều ý (N truy xuất, một lần sinh) trong V2? | Hoãn (P2), chỉ làm khi số đo "nhiều passage" của `V2-07`/`V2-10` kém | §12a |
| D10 | Trích dẫn tới phiên bản cũ? | Chỉ hiện đoạn trích kèm nhãn "Phiên bản cũ", không giữ Markdown bản cũ | §7.5; V2-15 |
| D11 | Term bỏ dấu cho BM25: chốt trước hay sau `V2-07`? | Trước, để tokenizer đóng băng một lần | §6.3; V2-07, V2-09 |

---

## 12. Không port từ hệ thống cũ

- `EMBEDDING_MODEL_NAME = "BGE_M3"` gán cứng, cắt 512 token bằng `tiktoken`, `cl100k_base` cho tiếng Việt (AUDIT-v2 §4.2, AUDIT-ingestion §2.4).
- Ba bộ trích xuất song song, OCR tesseract đồng bộ, dedup ngữ nghĩa theo 3 cửa sổ (AUDIT-ingestion §2.1, §2.5).
- Trích xuất TXT, `preview_extractor.py` parse lại file để gợi ý metadata, render Markdown có `rehype-raw` ở frontend.
- Intent classification nhiều tầng, lọc độc hại bằng LLM, Llama Prompt Guard 2 (FR-13, V2-02).
- Sao chép `allowed_roles/allowed_departments/allowed_users` vào từng chunk; `department_id` ghép bằng f-string (A2, A3, ADR-007).
- Ngưỡng 0.15 trên thang điểm trộn; ghi đè `similarity_score` bằng điểm rerank (R2, R4).

## 12a. Thiết kế RAG đã xét và không đưa vào V2 (owner chốt 2026-10-21)

Đặc điểm bài toán: mỗi workspace ≤ 50 tài liệu SOP/quy chế có cấu trúc; câu hỏi chủ yếu tra cứu bước, vai trò, thời hạn, điều kiện và ngoại lệ trong một tài liệu; VI/EN và cross-lingual; trích dẫn tới trang/đoạn; CPU, LLM miễn phí, tối đa một lần gọi sinh và một lần viết lại. V2 đã có dạng nhẹ của hai ý tưởng: cổng ngưỡng rồi từ chối là nhánh "không đủ bằng chứng" của Corrective RAG (fallback là từ chối kèm tài liệu gần nhất, không web search); router luật/semantic bỏ truy xuất cho chào hỏi là Adaptive RAG rút gọn (câu hỏi nghiệp vụ luôn truy xuất).

| Thiết kế | Lý do không đưa vào V2 | Xét lại khi |
|---|---|---|
| GraphRAG, LightRAG, HippoRAG | Kho nhỏ, câu hỏi tra cứu cục bộ, không cần tổng hợp toàn kho; dựng graph tốn LLM và dễ sai thực thể | Đo thấy nhiều câu cần nối tham chiếu chéo giữa SOP ("theo QT-05", "biểu mẫu BM-01"); khi đó thử liên kết theo luật trước |
| RAPTOR, cây tóm tắt | Cây heading của tài liệu đã có sẵn và được dùng ở §6.4a; tóm tắt bằng LLM có thể sai lệch | Có câu hỏi tổng quan trên tài liệu dài mà §6.4a không phủ |
| Iterative, multi-hop, agentic RAG, Self-RAG | Phá ràng buộc một lần gọi sinh và quota miễn phí, khó tái lập; Self-RAG cần model huấn luyện riêng | — |
| HyDE, multi-query, dịch câu hỏi bằng LLM | Thêm lần gọi LLM; `bge-m3` đa ngôn ngữ đã xử lý cross-lingual ở nhánh dense; nhánh BM25 xử lý bằng hệ số §6.4 | RQ1b cho thấy dense cũng yếu ở cross-lingual |
| Contextual retrieval bằng LLM | Tiền tố `title [docCode] › section_path` (§5.4) là bản tất định của cùng ý tưởng | Sau `V2-07`, theo PLAN-V2 |
| Long-context theo tài liệu | Cần giữ ánh xạ trích dẫn tới đoạn; chưa có số đo | Sau ablation §6.4a, thử cho tài liệu ngắn khi chunk trúng tập trung vào một tài liệu |
| Multimodal/visual RAG, SQL RAG | Ngoài phạm vi: không OCR, không dữ liệu bảng sống. Rủi ro đã biết: phần "Nội dung" SOP ISO dạng lưu đồ vẽ bằng shape có thể trích sai thứ tự đọc; `V2-19` nên có file lưu đồ để đo | Sau MVP |
| Tách câu nhiều ý và câu so sánh bằng luật (tối đa 3 truy vấn con, gộp RRF, một lần sinh) | Rủi ro giảm recall nếu tách sai; chưa có số đo (D9) | Số đo "nhiều passage" của `V2-07`/`V2-10` kém |
| Hỏi lại khi câu mơ hồ (top hit trải trên ≥ 3 tài liệu điểm gần nhau, câu ngắn) | Cần số đo phân bố điểm trước khi đặt điều kiện | Sau `V2-07`, khi có số đo |
| Mở rộng tham chiếu trong cùng tài liệu ("theo mục 5.3", "Điều 12") bằng luật | Phá "Không làm" của §6.4a, thêm token (D6) | `V2-19` đếm tham chiếu chéo trên corpus cho thấy đáng kể |
| Chunk thẻ tài liệu `DOC_INFO` (mã, lần ban hành, ngày hiệu lực, người duyệt, dàn ý) | Đổi CHECK `chunk_type` và quy ước offset trích dẫn; `<source code rev effective>` (§7.1 bước 6) đã trả lời phần lớn câu về mã và hiệu lực | Bộ kiểm `V2-28` cho thấy câu về hiệu lực/phê duyệt vẫn sai |
| `lang` theo chunk (SOP song ngữ); tiêu đề trong `index_text` cập nhật khi đổi tên tài liệu; từ điển viết tắt theo workspace | Chỉ có ý nghĩa khi hệ số cross-lingual ≠ 1, hoặc cần đo trước. Hạn chế đã biết: `index_text` giữ tiêu đề lúc ingest (§5.4), đổi tên tài liệu không cập nhật chỉ mục cho tới khi `reindex` | Sau `V2-07`, khi có nhu cầu thật |
| Dùng `wdept` hay cấp bậc người hỏi để diễn giải câu hỏi; dịch câu hỏi bằng LLM | Token chỉ có UUID, ai-service không đọc `core`, dễ lọc ngầm quá tay | — |
