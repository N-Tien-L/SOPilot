---
id: TECH-V2-AI-SERVICE
title: "ai-service technical design (V2): structured ingest, access-filtered hybrid retrieval, cited Q&A"
status: approved
created: 2026-10-20
updated: 2026-11-13
refs:
  - docs/04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-004-two-service-architecture.md
  - docs/architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/architecture/decisions/adr-008-pdf-extraction-docling.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
  - docs/architecture/components/core-api.md
author: "Owner"
affected_services: [ai-service, core-api, eval]
affected_schemas: [rag]
---

# TECHNICAL DESIGN: ai-service (V2)

> **Document id:** `TECH-V2-AI-SERVICE` | **PRD:** `PRD-V2-SOPILOT-MVP` | **Status:** `approved` (owner approval 2026-10-20, V2-03; open questions settled in §11)
>
> The contract with core-api (the `/internal/**` endpoints, payloads, idempotency, ordering) is defined in [TECH-V2-core-api](core-api.md) §8. This document only describes how ai-service handles them.
>
> **Changed 2026-10-21 (owner, [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md)):** TXT dropped; canonical Markdown and offsets defined (§5.2); extraction warnings (§5.3a); a retry puts a `FAILED` job back in the queue (§3.2, §8); the "Nội dung hệ thống nhận diện" (recognized-content) FR-31 view only at `READY` (§7.3); PDF library selection criteria (§11 Q7, Q8).
>
> **Changed 2026-10-21 (pre-implementation review):** `V2-20` scaffolds the service and `docproc` receives the tokenizer through its own protocol (§1.1); `DocElement` has `page_end` and per-row table offsets (§5.2); errors are classified as auto-retry / stop immediately, with a `run_after` column (§3.2, §5.1); eval and the service share the same chunker, and `V2-07`'s official RQ numbers run on `docproc` (§6.5).
>
> **Changed 2026-10-21 (owner, RAG architecture review for the SOP problem):** (A) `index_text` also carries the document code `docCode` (§5.4); (B) the search unit is separated from the unit the LLM reads: after the threshold gate, each hit chunk is expanded to its same-section group and adjacent chunks are merged (§6.4a), stored in `messages.context_sources` (§3.4); (C) a BM25 weight when the question's language differs from the chunk's, column `chunks.lang`, default `1.0` (no change) until `V2-07` measures RQ1b (§6.4). No extra LLM call. GraphRAG, RAPTOR, iterative/agentic, HyDE/multi-query and LLM-based contextual retrieval are not in V2 (§12a).
>
> **Changed 2026-10-21 (owner, end-to-end audit by query type, decisions D1–D11 in §11):** (1) the `hybrid` gate always has a `dense_score` for the top candidate (§6.4); (2) `outcome` stays, and `refusal_reason` is added to separate "no evidence", "the LLM itself said not found", "out of scope" and "invalid input"; the gap list contains only the kinds that need documents added (§3.4, §7.1, §7.6); (3) `PROCEDURE_STEP` repeats merged-cell values down each row (§5.2, §5.4); (4) header/footer rules have a minimum page count (§5.3); (5) `<source>` carries `code`, `rev`, `effective`, and the prompt has today's date, without changing `index_text` (§7.1 step 6); (6) input specification: empty or overlong questions are refused, "meaningful tokens", follow-up questions when rewriting fails, the generation prompt receives the rewritten question plus the original and no history (§7.1); (7) a decision log of `route`, `rewrite_status`, `checks` (§3.4); (8) the extended router runs **after** the threshold gate, masks PII, checks numbers/dates, no fallback once streaming has started, diacritic-free terms and recognition of document codes in queries, the embedding model checked at startup (§3.3, §6.3, §7.1, §7.4). No extra LLM call.
>
> **Implementation status (ticket files, 2026-11-13):** the tickets implementing this design are V2-09, V2-10, V2-20, V2-21, V2-22, V2-35 (`done`) and V2-13, V2-25, V2-27 (`review`). Where code and this document disagree, the code wins (`services/ai-service/src/sopilot_ai/`, `config/models.yaml`). Translated from Vietnamese on 2026-11-13 without design changes; **section numbers are stable** (code, CI and migrations cite them).

---

## 0. Scope and conventions

- ai-service is a FastAPI, Python ≥ 3.11 service, written from scratch in `services/ai-service`. It replaces `ai-qa-service` and `ingestion-service` (removed in V2-17). The old code is only a reference.
- ai-service is the sole owner of schema `rag` and does not read schema `core` (ADR-004 §4.3). Everything about documents and access arrives through jobs and `rag.document_access`.
- Each question calls the generation LLM **at most once**; rewriting the question (only when there is history) is the second and only other call. The guard runs on rules; routing uses rules and then an embedding-based semantic router, with no LLM call (PRD FR-13, ADR-006 §4.4).
- Every model goes through a provider interface and is declared in **one** file, `config/models.yaml`; no model id is hard-coded (ADR-006 §4.1).

### Traceability to requirements and earlier findings

| Requirement / finding | Section |
|---|---|
| FR-08, AUDIT-ingestion §5 items 2–9 | §5 |
| FR-10, R1–R5 | §6 |
| FR-11, FR-12, FR-13, FR-14 | §7.1–§7.3 |
| FR-09 (question quota off by default, provider limits) | §7.4 |
| FR-15, UC-11 (hiding history after losing access) | §7.5 |
| FR-16, FR-17 (owner decision Q1 2026-10-20) | §7.6 |
| FR-25, ADR-007 §4.5 | §3.2, §6.1 |
| FR-28 | §5.7 |
| FR-31 (recognized-content view), FR-14 | §5.2, §5.3a, §7.3 |
| FR-18 (kept in sync with `eval/`) | §6.5 |
| FR-19, FR-29 | §9 |
| AUDIT-v2 §4.2: `EMBEDDING_MODEL_NAME = "BGE_M3"`, 512-token cut with `tiktoken` | §4.2, §5.5 |
| RAG architecture review for the SOP problem (owner decision 2026-10-21): document code in the index, context assembly by section, cross-lingual BM25 weight | §5.4, §6.4, §6.4a, §12a |
| End-to-end audit by query type (owner decision 2026-10-21, D1–D11): hybrid gate, `refusal_reason`, merged cells, metadata in `<source>`, input, PII, router after the gate | §3.3, §3.4, §5.2–§5.4, §6.3, §6.4, §7.1–§7.6, §11, §12a |

---

## 1. Architecture overview and components

| Component | Technology | Boundary | Nature of the change |
|---|---|---|---|
| `services/ai-service` | FastAPI, SQLAlchemy 2 (async, psycopg 3), Pydantic v2, uv | Schema `rag` | New service |
| `infrastructure/db/migrations/rag/` | Flyway | Schema `rag` | New migration chain (V2-08) |
| Ingest and metadata-suggestion worker | A child process in the same container (`python -m sopilot_ai.worker`) | `rag.ingestion_jobs`, `rag.suggestion_jobs` | Postgres `FOR UPDATE SKIP LOCKED` queue |
| Local models | sentence-transformers / transformers on CPU | — | `bge-m3`, `bge-reranker-v2-m3` (ADR-006 §4.2) |
| LLM API | One self-hosted endpoint (vLLM on Modal) through an OpenAI-style API | — | ADR-006 §4.4, [V2-10 milestone 2](../../execution/initiatives/v2-sopilot-mvp/tickets/V2-10-ai-service-qa-pipeline.md) |

The API and the worker are two processes sharing the image and configuration. They are separate so that CPU-heavy embedding does not block the API's event loop (an old bug: synchronous OCR inside an `async` function, AUDIT-ingestion §2.1). Q&A requests still embed the question inside the API process, through `run_in_threadpool` with a preloaded model.

### 1.1 Package structure

```
services/ai-service/
├── pyproject.toml      # uv; extra `pdf` for the ADR-008 library, extra `local` for sentence-transformers
├── config/models.yaml
├── src/sopilot_ai/
│   ├── api/            # public /ai/v1 and internal /internal routers, SSE
│   ├── auth/           # JWT verification through core-api's JWKS, InternalTokenDependency
│   ├── db/             # engine, sessions with tenant set_config, repositories
│   ├── docproc/        # PURE PACKAGE, no DB/web dependencies (V2-20, V2-21, V2-22)
│   │   ├── model.py    #   DocElement, StructuredDocument
│   │   ├── tokens.py   #   Tokenizer protocol + HFTokenizer (AutoTokenizer by model/revision) (V2-22)
│   │   ├── extract/    #   pdf.py (adapter for the ADR-008 library), markdown.py (V2-20)
│   │   ├── normalize.py#   NFC, whitespace; render.py: canonical Markdown + offsets + page markers (V2-20)
│   │   ├── clean/      #   boilerplate.py, metadata.py, warnings.py (V2-21)
│   │   └── chunk/      #   family.py, procedure_table.py, chunker.py (V2-22)
│   ├── providers/      # embedding.py, rerank.py, llm.py, registry.py (reads models.yaml)
│   ├── retrieval/      # access_filter.py, dense.py, lexical.py, fusion.py, gate.py, context.py (§6.4a)
│   ├── qa/             # guard.py, router.py, prompt.py, citations.py, pipeline.py
│   ├── conversations/
│   ├── quota/          # question counters, per-provider RPM/TPM limits
│   ├── ingest/         # job handler calling docproc → embed → write chunks
│   ├── suggest/        # metadata suggestions (V2-25)
│   ├── outbox/         # sends status and suggestions to core-api
│   └── worker.py
└── tests/
```

`docproc` is a pure Python package: it takes bytes and a file type and returns data structures. `eval/` and the extraction-quality tests (V2-19) import this package directly, so measurements on the corpus are measurements of exactly the code running in the service.

**Scaffolding order.** `V2-20` is the first ticket that writes code in `services/ai-service`, so it creates `pyproject.toml`, the `src/sopilot_ai/` layout, `tests/unit` and the build/test scopes for the new service in `scripts/` (`validate-build.ps1 -Scope ai`, `run-tests.ps1 -Scope ai-service`). `V2-20` needs only `docproc`; the other packages stay empty. `V2-09` adds `api/`, `db/`, `providers/`, `retrieval/`, `ingest/`, `worker.py` and the `rag` migrations.

**The tokenizer does not go through a provider.** The chunker (`V2-22`) receives a `Tokenizer` (a protocol in `docproc/tokens.py`: `count(text) -> int`) passed in, and does not call `EmbeddingProvider`. `HFTokenizer` loads `transformers.AutoTokenizer` for the `model` and `revision` of the active embedding in `models.yaml`, without loading the embedding model. `V2-09`'s `EmbeddingProvider.tokenizer()` returns this same object. So `V2-22` does not depend on `V2-09`, and `eval/` counts tokens with the same tokenizer.

---

## 2. Sequence diagrams

### 2.1 Ingesting a document version

```mermaid
sequenceDiagram
    autonumber
    participant C as core-api
    participant A as ai-service API
    participant W as ai-service worker
    participant DB as Postgres (rag)
    participant S3 as Object storage

    C->>A: POST /internal/ingestions (Idempotency-Key)
    A->>DB: BEGIN; set_config(app.workspace_id); UPSERT document_access (if accessRevision is newer); INSERT ingestion_jobs ON CONFLICT (version_id) moves a FAILED job back to QUEUED only when attempt is newer (§8); COMMIT
    A-->>C: 202
    A->>W: NOTIFY rag_jobs (wake-up; the worker also scans every 5 s)
    W->>DB: rag.claim_ingestion_job() (SECURITY DEFINER, FOR UPDATE SKIP LOCKED, 10-minute lease)
    W->>DB: outbox VERSION_STATUS(PROCESSING)
    W->>S3: GET objectKey
    W->>W: docproc.extract → normalize → clean → render canonical Markdown + warnings → chunk (embedding model's tokenizer)
    W->>W: embed (cache by model, revision, sha256)
    W->>DB: BEGIN; INSERT chunks, chunk_terms, extracted_documents (new version); UPDATE document_access.active_version_id; DELETE chunks of the old version; job DONE; outbox VERSION_STATUS(READY); COMMIT
    W->>C: (outbox) PATCH /internal/documents/{id}/versions/{verId}/status (READY + warning codes)
    W->>DB: INSERT suggestion_jobs (if suggest.enabled)
```

### 2.2 Q&A

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as ai-service
    participant DB as Postgres (rag)
    participant L as LLM provider

    B->>A: POST /ai/v1/conversations/{id}/messages (Bearer, Accept: text/event-stream)
    A->>A: Verify the JWT (core-api JWKS): sub, wid, wrole, wdept
    A->>DB: Check the per-user/day quota and the system cap if enabled (FR-09, off by default)
    A->>A: Input check (empty, too long → SSE refusal INPUT_INVALID, end), mask PII
    A->>A: Input guard (VI/EN rules): BLOCK → SSE refusal, end
    A->>A: Rule router: greeting/thanks/question about the bot → SSE template, end
    opt Conversation history exists
        A->>L: Rewrite the question as a standalone one (LLM call 1)
    end
    A->>DB: Dense + lexical, filtered by workspace + access BEFORE LIMIT (§6.1)
    A->>A: RRF (language-dependent BM25 weight) → rerank (if on) → mode-specific threshold gate (always has dense_score)
    alt Below the threshold
        A-->>B: SSE refusal (NO_EVIDENCE: with the closest documents, goes to the gap list; OUT_OF_SCOPE: without, not in the list)
    else Enough evidence
        A->>DB: Assemble context: same-section chunks of the hit chunks, access-filtered (§6.4a)
        A->>L: Generate the answer, streamed (the final LLM call)
        A-->>B: SSE delta (holding back a tail for the canary check)
        A->>A: Canary check, map [n], drop unmappable citations
        A-->>B: SSE citations + done (the cleaned final text)
    end
    A->>DB: Store message, citations, retrieval_results (4 kinds of score), guard_events
```

---

## 3. Data design (schema `rag`)

- Migrations: `infrastructure/db/migrations/rag/V0xx__*.sql`, history table `rag.flyway_schema_history`.
- The `vector` extension (pgvector ≥ 0.8, for iterative index scans with filtering) is created in V2-08's bootstrap migration.
- Every table with `workspace_id` enables `ENABLE` + `FORCE ROW LEVEL SECURITY` with the policy `workspace_id = rag.current_workspace()` (defined like `core.current_workspace()`, TECH-V2-core-api §4.2). Exceptions are justified at the table itself.
- No FKs to `core`. `document_id`, `version_id`, `user_id`, `department_id` are UUIDs issued by core-api.

### 3.1 Document read access (ADR-007 §4.5)

```sql
CREATE TABLE rag.document_access (
    workspace_id      uuid NOT NULL,
    document_id       uuid PRIMARY KEY,
    visibility        text NOT NULL CHECK (visibility IN ('WORKSPACE','DEPARTMENTS')),
    department_ids    uuid[] NOT NULL DEFAULT '{}',
    access_revision   bigint NOT NULL,
    active_version_id uuid,                 -- the version being retrieved; NULL = never READY yet
    title             text NOT NULL,        -- to display citations and "closest documents"
    deleted_at        timestamptz,          -- set as soon as DELETE arrives, before chunks are cleaned up
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (visibility = 'WORKSPACE' OR cardinality(department_ids) >= 1)
);
CREATE INDEX ix_document_access_ws ON rag.document_access(workspace_id);
CREATE INDEX ix_document_access_depts ON rag.document_access USING gin (department_ids);
```

No access row → the chunks are never retrieved, because every query `JOIN`s this table (fail closed). `title` is sent by core-api with the job; updating it when the title changes would need an extra event. To avoid that event, V2 shows the document name in citations using the title **at ingest time**, and the frontend fetches the latest title from core-api when the viewer opens.

### 3.2 Ingest jobs and extraction results

```sql
CREATE TABLE rag.ingestion_jobs (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    version_id    uuid NOT NULL UNIQUE,     -- idempotent per version
    request_attempt int NOT NULL DEFAULT 0, -- core-api's `attempt`; a retry with a larger attempt moves a FAILED job back to QUEUED (§8)
    payload       jsonb NOT NULL,           -- the raw POST /internal/ingestions payload
    status        text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED','CANCELLED')),
    attempts      int NOT NULL DEFAULT 0,
    lease_until   timestamptz,              -- a worker dying midway: the job returns by itself after the lease expires
    run_after     timestamptz NOT NULL DEFAULT now(), -- backoff when auto-retrying transient errors (§5.1)
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
    structure      jsonb NOT NULL,          -- the cleaned StructuredDocument (§5.2), for the viewer and metadata suggestions
    markdown       text NOT NULL,           -- the CANONICAL Markdown after cleaning (§5.2); element and chunk offsets refer to it
    page_index     jsonb,                   -- PDF: [{page, charStart, charEnd}] over the markdown; MD: NULL
    warnings       jsonb NOT NULL DEFAULT '[]', -- [{code, pages?, count?}] (§5.3a)
    normalizer_version text NOT NULL,       -- version of the normalization rules + renderer; changing it requires re-ingest so offsets stay right
    page_count     int,
    language       text,
    doc_family     text NOT NULL CHECK (doc_family IN ('ISO_PROCEDURE','LEGAL_ARTICLES','MARKDOWN','PROSE')),
    boilerplate    jsonb NOT NULL,          -- the separated boilerplate: header/footer, national motto, signatures, approval tables...
    extracted_meta jsonb NOT NULL,          -- {docCode, revisionLabel, effectiveDate, approvedBy}
    extractor      text NOT NULL,           -- library name + version (ADR-008, V2-20)
    created_at     timestamptz NOT NULL DEFAULT now()
);
```

`rag.claim_ingestion_job()` is a `SECURITY DEFINER` function (owner `sopilot_migrator`, `GRANT EXECUTE` to `sopilot_ai_app`) that returns a `QUEUED` job with `run_after <= now()` or a `RUNNING` job whose lease has expired, sets `RUNNING`, `lease_until = now() + 10 minutes`, `attempts + 1`. The worker needs it because it must see jobs of every workspace; after taking a job, the worker sets `app.workspace_id` from the job and every following query is under normal RLS. At startup the worker scans for pending jobs before waiting for `NOTIFY` (FR-08, ADR-006 B1 constraint 3). Only transient errors are retried automatically (§5.1); beyond `SOPILOT_INGEST_MAX_ATTEMPTS=3` → `FAILED`, keeping the last attempt's error code. `RETRY_EXHAUSTED` is used only when a job ran out of attempts without any recorded error code (the worker died repeatedly, the lease expired).

### 3.3 Chunks and indexes

```sql
CREATE TABLE rag.chunks (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL,
    document_id        uuid NOT NULL,
    version_id         uuid NOT NULL,
    ordinal            int  NOT NULL,                 -- order within the document
    chunk_type         text NOT NULL CHECK (chunk_type IN ('SECTION','PROCEDURE_STEP','TABLE','PROSE')),
    section_path       text[] NOT NULL,               -- ancestors, for example {'5. Nội dung','5.1 Lập đề nghị mua hàng'}
    page_start         int,
    page_end           int,
    char_start         int  NOT NULL,                 -- offset in extracted_documents.markdown
    char_end           int  NOT NULL,
    content            text NOT NULL,                 -- the passage shown to users and sent to the LLM
    index_text         text NOT NULL,                 -- "Document title [code] › section › step\n" + content: embedded and lexically indexed (§5.4)
    lang               text,                          -- the version's language (step 6 of §5.1), used for the §6.4 BM25 weight; NULL = unknown
    token_count        int  NOT NULL,                 -- counted with embedding_model's tokenizer
    content_sha256     bytea NOT NULL,                -- sha256(index_text), the embedding cache key
    embedding          vector(1024) NOT NULL,
    embedding_provider text NOT NULL,
    embedding_model    text NOT NULL,
    embedding_dim      int  NOT NULL CHECK (embedding_dim = 1024),
    embedding_revision text NOT NULL,
    lexical_len        int  NOT NULL,                 -- number of original terms in index_text, excluding `~` diacritic-free terms (§6.3); BM25 needs the document length
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_id, ordinal),
    CHECK (char_end > char_start)
);
CREATE INDEX ix_chunks_doc ON rag.chunks(document_id, version_id);
CREATE INDEX ix_chunks_embedding ON rag.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE rag.chunk_terms (                        -- the lexical index for BM25 (§6.3)
    workspace_id uuid NOT NULL,
    chunk_id     uuid NOT NULL REFERENCES rag.chunks(id) ON DELETE CASCADE,
    term         text NOT NULL,                       -- unigrams, bigrams `a_b`, and diacritic-free forms `~a`, `~a_b` when they differ from the original (§6.3)
    tf           int  NOT NULL CHECK (tf > 0),
    PRIMARY KEY (chunk_id, term)
);
CREATE INDEX ix_chunk_terms_lookup ON rag.chunk_terms(workspace_id, term);

CREATE TABLE rag.embedding_cache (                    -- NO workspace_id, NO RLS: holds only vectors, keyed by content
    model        text  NOT NULL,
    revision     text  NOT NULL,
    content_sha256 bytea NOT NULL,
    embedding    vector(1024) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, revision, content_sha256)
);
```

Design notes:
- **Fixed vector size 1024.** All three RQ5 models (`bge-m3`, `Qwen3-Embedding-0.6B`, `multilingual-e5-large-instruct`) output 1024 dimensions. The application uses **one** active model; queries always filter `embedding_model = :active AND embedding_revision = :active_rev`, so vectors of two models are never compared (ADR-006 §4.1.3). Changing the model means re-running ingest for every version; the RQ5 experiments run in `eval/`, not in the application DB. Because chunks of an old model would be filtered out silently (every question would be refused), at startup ai-service compares the `(embedding_model, embedding_revision)` of chunks in active versions with the enabled model: on a mismatch it logs `ERROR`, `/health` returns `degraded` with the number of mismatched versions, and the admin command `reindex` (§5.2) re-ingests those versions.
- **`embedding_cache` has no `workspace_id`**, a deliberate exception (ADR-007 §4.5: the embedding cache holds only content-keyed vectors). No text is returned from this table; there is no way from a hash back to a workspace.
- **Four kinds of score** (`dense_score`, `bm25_score`, `fusion_score`, `rerank_score`) depend on the question, so they are not on `chunks`; they are stored per retrieval in `rag.retrieval_results` (§3.4). This replaces the old approach of overwriting `similarity_score` (R2, R4, R5).
- `section_path` is the chain of **ancestors**, not siblings (a bug in the old standardizer, AUDIT-ingestion §2.3).

### 3.4 Conversations, retrieval and guard

```sql
CREATE TABLE rag.conversations (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL,
    title        text NOT NULL,                         -- generated by a rule from the first question (cut at 80 characters)
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
    standalone_query text,                              -- the question after rewriting (if any)
    outcome         text CHECK (outcome IN ('ANSWERED','REFUSED_NO_EVIDENCE','REFUSED_GUARD','TEMPLATE','QUOTA_EXCEEDED','ERROR')),
    refusal_reason  text CHECK (refusal_reason IN ('NO_EVIDENCE','GENERATOR_NOT_FOUND','OUT_OF_SCOPE','INPUT_INVALID')),  -- NULL when not refused; semantics below
    route           jsonb,                              -- {layer: 'rule'|'semantic'|'followup_rule'|'none', intent, score, margin}
    rewrite_status  text CHECK (rewrite_status IN ('NONE','OK','FAILED')),   -- NONE: no history
    checks          jsonb,                              -- {citationCount, numberWarnings: [...], disclaimers: [...], pii: [rule_id]}
    lang            text,
    retrieval_mode  text,                               -- dense | bm25 | hybrid | hybrid_rerank
    gate_score      real,
    threshold       real,
    model           text,                               -- the LLM that actually generated (after fallback)
    prompt_version  text,
    tokens_in       int,
    tokens_out      int,
    latency_ms      jsonb,                              -- {retrieve, rerank, context, first_token, total}
    context_sources jsonb,                              -- [{n, documentId, versionId, hitChunkIds, chunkIds, tokens}] after §6.4a context assembly; NULL when the generator was not called
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (refusal_reason IS NULL OR outcome IN ('REFUSED_NO_EVIDENCE', 'TEMPLATE'))
);
CREATE INDEX ix_messages_conv ON rag.messages(conversation_id, created_at);

CREATE TABLE rag.message_citations (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages(id) ON DELETE CASCADE,
    n            int  NOT NULL,                         -- the [n] number in the answer
    chunk_id     uuid,                                  -- may be NULL if the chunk was deleted when a new version replaced it
    document_id  uuid NOT NULL,
    version_id   uuid NOT NULL,
    page_start   int,
    char_start   int  NOT NULL,
    char_end     int  NOT NULL,
    snippet      text NOT NULL,                         -- a copy of the passage at answer time
    PRIMARY KEY (message_id, n)
);
CREATE INDEX ix_citations_document ON rag.message_citations(document_id);

CREATE TABLE rag.retrieval_results (                    -- serves RQ2/RQ3 on real data and debugging
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages(id) ON DELETE CASCADE,
    chunk_id     uuid NOT NULL,
    rank         int  NOT NULL,                          -- the final rank (after rerank if any)
    dense_score  real,                                   -- cosine
    bm25_score   real,
    fusion_score real,                                   -- RRF
    rerank_score real,
    in_context   boolean NOT NULL,                       -- whether it went into the prompt
    PRIMARY KEY (message_id, chunk_id)
);

CREATE TABLE rag.guard_events (                          -- layer 4 of FR-13
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
    day          date NOT NULL,                          -- UTC
    questions    int  NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, user_id, day)
);
```

**`outcome` and `refusal_reason` (owner decision 2026-10-21, D2).** `outcome` keeps its set of values; `refusal_reason` says *why* a question was not answered, so answer-level RQ3 can separate "the gate refused" from "the LLM refused by itself", and so the gap list (§7.6) does not mix in questions unrelated to missing documents:

| `refusal_reason` | `outcome` | When | In the gap list |
|---|---|---|---|
| `NO_EVIDENCE` | `REFUSED_NO_EVIDENCE` | The threshold gate refused (§6.4) and the question was not classified `OUT_OF_SCOPE` | Yes |
| `GENERATOR_NOT_FOUND` | `REFUSED_NO_EVIDENCE` | The gate let it through but the LLM returned the fixed "not found" opening sentence (§7.1 steps 6, 9) | Yes |
| `OUT_OF_SCOPE` | `REFUSED_NO_EVIDENCE` | The gate refused **and** the router classified `off_topic` above its threshold (V2-27); no closest documents are shown | No |
| `INPUT_INVALID` | `TEMPLATE` | Empty, overlong, no meaningful tokens, or a follow-up when the rewrite failed (§7.1 steps 2–4); no LLM call, not counted against quotas | No |

There is no `refusal_reason` for questions filtered by access: ai-service never queries outside access (fail closed, §6.1), so it cannot tell "missing document" from "document outside access". An `ANSWERED` message with `checks.citationCount = 0` stays `ANSWERED` and is also picked up by the gap list (FR-11 violated at runtime). `messages.content` stores the question **verbatim** for the asker; PII masking applies when sending to the LLM, when rewriting and when showing to admins (§7.1 step 2, §7.6).

The system-wide question cap must count across all workspaces, so it lives in the **non-RLS** table `rag.system_usage(day date PRIMARY KEY, questions int)`, which holds only counts. It is updated with `INSERT ... ON CONFLICT DO UPDATE SET questions = questions + 1 RETURNING questions`.

### 3.5 Metadata suggestions and outbox

```sql
CREATE TABLE rag.suggestion_jobs (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    version_id    uuid NOT NULL UNIQUE,
    input         jsonb NOT NULL,      -- existing categories/tags from the ingest payload
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
    cache_key      bytea NOT NULL,     -- sha256(workspace_id, content_sha256, prompt_version, model, hash of the category list)
    result         jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, cache_key)
);

CREATE TABLE rag.outbox_events (    -- same structure and rules as core.outbox_events (TECH-V2-core-api §3.5, §7)
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

CREATE TABLE rag.processed_requests (  -- idempotency for /internal/** (Idempotency-Key from core-api)
    idempotency_key uuid PRIMARY KEY,
    processed_at    timestamptz NOT NULL DEFAULT now()
);
```

`processed_requests` has no `workspace_id` and no RLS (it holds only UUIDs); rows older than 7 days are cleaned up.

---

## 4. Authentication, configuration and providers

### 4.1 Authentication

- **Public requests `/ai/v1/**`:** `Authorization: Bearer <access token>` issued by core-api. RS256 verified with the JWKS at `http://core-api:8080/.well-known/jwks.json` (cached 10 minutes, reloaded on an unknown `kid`, at most once per minute); checks `iss = sopilot-core`, `aud` containing `sopilot-ai`, `exp` (60 s skew). Takes `sub`, `wid`, `wrole`, `wdept`. These values are the only source for the tenant and access filters; `workspaceId` is **never** read from the body or query (ADR-005 §4.5).
- **Internal requests `/internal/**`:** header `X-Internal-Token`, compared in constant time (`hmac.compare_digest`). The internal router is not mounted under the `/ai` prefix, so the frontend rewrites never reach it.
- Every DB session opens a transaction and calls `SELECT set_config('app.workspace_id', :wid, true), set_config('app.user_id', :sub, true)` first (dependency `tenant_session`). Repositories accept no session that has not gone through this dependency.

> **Implementation note (2026-11-13):** the implemented form is `async with tenant_tx(engine, workspace_id, user_id)` in `db/engine.py` (with `system_tx` only for SECURITY DEFINER helpers and the non-RLS tables); tenant binding outside `db/engine.py` fails `tests/unit/test_architecture.py`.

### 4.2 `config/models.yaml`

This is the **only** place models are declared (ADR-006 §4.1.2). The values are the default configuration; the exact Gemini id was kept configurable because `gemini-3.1-flash-lite` (GA) still returned 503 in testing and only the `-preview` version returned 200 (V2-02, AUDIT-v2 §4.1, 2026-10-20).

```yaml
embedding:
  active: bge-m3
  models:
    bge-m3:
      provider: local                 # local | cloudflare | openai_compatible
      model: BAAI/bge-m3
      revision: ${EMBEDDING_REVISION}  # pin the HF commit hash; startup fails if empty in the eval profile
      dim: 1024
      max_tokens: 8192
      query_prefix: ""
rerank:
  enabled: ${RERANK_ENABLED:false}
  provider: ${RERANK_PROVIDER:local}   # local | modal | none (V2-35)
  model: BAAI/bge-reranker-v2-m3
  revision: ${RERANK_REVISION}
  max_pairs: 25
  timeout_s: ${RERANK_TIMEOUT_S:30}    # modal only
llm:
  # Changed 2026-11-09 (V2-10 milestone 2, ADR-006 §4.4): one self-hosted model behind an OpenAI-style server (vLLM on
  # Modal). The Gemini/Groq chain was dropped (owner 2026-11-01). Endpoint, model id and key come from the environment.
  generate:
    chain:
      - provider: modal
        model: "${SOPILOT_LLM_MODEL:}"
        rpm: "${SOPILOT_LLM_RPM:60}"        # placeholder, measure on the real endpoint
        tpm: "${SOPILOT_LLM_TPM:200000}"
        context_max_tokens: "${SOPILOT_LLM_CONTEXT_MAX_TOKENS:}"   # empty = no declared ceiling
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
  candidate_pool: 50      # per dense / lexical branch
  rerank_pool: 25
  context_k: 5            # number of hit chunks fed into context assembly (§6.4a)
  rrf_k: 60
  rrf_weights: [1.0, 1.0]
  doc_code_boost: 0.02    # added to the fusion_score of chunks whose docCode matches a code in the question (§6.4); starting value, not calibrated (V2-28)
  cross_lingual_bm25_factor: 1.0   # multiplies the BM25 weight when the question language ≠ chunks.lang (§6.4); 1.0 = off, changed after RQ1b (V2-07)
  context:                # small-to-big context assembly (§6.4a)
    expand: true          # false = only the hit chunks, the old way (V2-10 ablation)
    section_max_tokens: 1200   # a same-section group below this is sent whole
    max_tokens: 3000      # total context ceiling, counted with the chunks' token_count
  thresholds:             # refusal gate; calibrated on the V2-06 dev set (RQ3)
    dense: 0.45
    bm25: null            # BM25 has no common scale across questions; bm25 mode never refuses by itself
    hybrid: 0.45          # compared with the top candidate's dense cosine, as in the eval harness
    hybrid_rerank: 0.30   # compared with the top candidate's rerank score (sigmoid)
  mode: hybrid            # dense | bm25 | hybrid; rerank adds the _rerank suffix when rerank.enabled
chunking:
  target_tokens: 384
  max_tokens: 512         # fits multilingual-e5's 512 limit so the RQ5 results apply
  min_tokens: 64          # smaller sections are merged with siblings under the same parent
```

The thresholds above are placeholders to be replaced with values calibrated on the dev set (V2-07). At startup ai-service calls `/models` of each provider that has a key and logs a `WARNING` for models no longer listed (ADR-006 §4.1.2); it does not block startup, so retrieval eval still runs without an LLM key. The file in the repository (`services/ai-service/config/models.yaml`) is the source of the actual values.

### 4.3 Provider interfaces

```python
class EmbeddingProvider(Protocol):
    name: str; model: str; revision: str; dim: int
    def tokenizer(self) -> "Tokenizer": ...                       # this model's own tokenizer
    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray: ...   # L2-normalized

class RerankProvider(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> np.ndarray: ...       # sigmoid, [0, 1]

class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], *, task: Literal["generate","rewrite","small_task","judge"],
                       response_schema: type[BaseModel] | None = None) -> Completion: ...
    def stream(self, messages: list[Message], *, task: str) -> AsyncIterator[Delta]: ...
```

- `EmbeddingProvider`: `local` (sentence-transformers, on the threadpool), `cloudflare` (Workers AI `@cf/baai/bge-m3`, deployment only, out of scope for V2), `openai_compatible` (TEI or another embedding server).
- `RerankProvider`: `local` (the `bge-reranker-v2-m3` cross-encoder on CPU), `modal` (`RemoteRerankProvider`, V2-35: `POST {providers.modal.rerank_base_url}/rerank` to `/v1/rerank` of the Modal container sharing the GPU with vLLM; the server returns raw logits in `passages` order, and the client applies a sigmoid like `LocalRerankProvider`; HTTP errors, timeouts or bad JSON all become `RerankError`, with no downgrade to hybrid), `none`. The key is `SOPILOT_LLM_API_KEY`, the URL `SOPILOT_RERANK_BASE_URL`. A free API reranker could be added later as a new provider without changing the pipeline (see open question Q3).
- `LLMProvider`: a single class calling an OpenAI-style `chat/completions` API with different `base_url`s. `ChainedLLM` tries the models in `chain` in turn; it moves to the next model on `429`, `503`, a timeout, or when the local limiter reports an exhausted quota (§7.4), and **only before the first `delta` is emitted** (§7.4). The model that actually answered is recorded in `messages.model`.

---

## 5. Structured ingest (FR-08, V2-19..22)

### 5.1 Job steps

| Step | Module | Output | Error → `failure_code` |
|---|---|---|---|
| 1. Download the file | `ingest` | bytes | `OBJECT_NOT_FOUND` |
| 2. Extract | `docproc.extract` (PDF: the ADR-008 library, OCR off; MD: a CommonMark/GFM parser) | `StructuredDocument` | `UNSUPPORTED_TYPE`, `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING` (MD that is not UTF-8) |
| 2a. Normalize | `docproc.normalize` | `StructuredDocument` (NFC, whitespace, source numbering kept) | — |
| 3. Separate boilerplate, extract metadata, warnings | `docproc.clean` | cleaned `StructuredDocument` + `boilerplate` + `extracted_meta` + `warnings` | — |
| 3a. Render canonical Markdown | `docproc.render` | `markdown`, each element's offsets, `page_index` | — |
| 4. Detect the document family | `docproc.chunk.family` | `ISO_PROCEDURE` \| `LEGAL_ARTICLES` \| `MARKDOWN` \| `PROSE` | — |
| 5. Chunk | `docproc.chunk` | `list[Chunk]` | `EMPTY_CONTENT` with 0 chunks (fixes an old bug: empty still became `READY`) |
| 6. Detect the language | `ingest` | `vi` / `en` / other, written to `extracted_documents.language` and `chunks.lang` | — |
| 7. Embed | `providers.embedding` + cache | 1024-dimension vectors | `EMBEDDING_ERROR` (retried) |
| 8. Write and activate | `ingest` | the §5.6 transaction | — |

The `failure_message` sent to core-api is a fixed sentence per `failure_code` (VI/EN), never an exception message. Errors of unknown cause in steps 2–5 record `EXTRACTION_ERROR`.

**Which errors are retried automatically.** The worker retries only transient errors; errors caused by the file content are deterministic, so it stops on the first attempt and keeps the exact code so the UI can suggest "Replace file" (TECH-V2-core-api §5.5).

| Kind | Codes | Worker behaviour |
|---|---|---|
| Transient | `OBJECT_NOT_FOUND`, `EMBEDDING_ERROR`, DB/storage connection errors, a dead worker (expired lease) | The job goes back to `QUEUED`, `run_after = now() + 30 s × 2^(attempts − 1)`, **no** `FAILED` callback is sent; the version stays `PROCESSING` in core-api. After `SOPILOT_INGEST_MAX_ATTEMPTS` → `FAILED` with the last attempt's code |
| Deterministic | `UNSUPPORTED_TYPE`, `NO_TEXT_LAYER`, `ENCRYPTED_PDF`, `CORRUPT_FILE`, `INVALID_ENCODING`, `EMPTY_CONTENT`, `EXTRACTION_ERROR` | `FAILED` immediately, one callback. The user can still click retry (`attempt + 1`, §8) |

A retry reruns every step for that exact version; no intermediate results are kept between attempts (extraction is deterministic and cheap compared with embedding, and embedding already has the §5.5 cache).

### 5.2 Intermediate document structure (V2-20 output)

```python
class DocElement(BaseModel):
    kind: Literal["heading", "paragraph", "list_item", "table", "page_break", "code"]
    text: str                       # NFC-normalized; list_item keeps the numbering shown in the source ("5.1", "a)")
    level: int | None = None        # heading 1..6; list nesting
    number: str | None = None       # the rendered sequence number, if any
    rows: list[list[str]] | None = None   # table: the first row is the column header if recognized; a merged cell is written once in its first cell (see cell_spans)
    cell_spans: list[tuple[int, int, int, int]] | None = None  # table: (row, col, rowspan, colspan) of each merged cell, only those with rowspan > 1 or colspan > 1; None if the library returns no spans (recorded in ADR-008)
    page: int | None = None         # PDF: start page (real page number, from 1); MD: None
    page_end: int | None = None     # PDF: end page, = page unless it spans pages (multi-page tables); MD: None
    row_pages: list[int] | None = None    # PDF table: the page of each row in rows, same length as rows
    char_start: int | None = None   # offset on the canonical Markdown, set by render; None for elements not rendered (role ∉ {content, figure_text})
    char_end: int | None = None
    row_spans: list[tuple[int, int]] | None = None  # table: [char_start, char_end) of each row in the canonical Markdown, set by render
    role: Literal["content", "header", "footer", "boilerplate", "figure_text"] = "content"  # figure_text: PDF text-layer text inside image regions that Docling does not emit (diagrams), rendered as content; text inside image regions in the top 15%/bottom 10% of the page keeps role header/footer

class StructuredDocument(BaseModel):
    file_type: Literal["PDF", "MD"]
    elements: list[DocElement]      # in reading order; tables in place within the body
    page_count: int | None
    frontmatter: dict | None        # MD

def render(doc: StructuredDocument) -> RenderedDocument: ...   # docproc.render: markdown, per-element offsets, page_index
```

**Canonical Markdown (owner decision 2026-10-21).** `extracted_documents.markdown` is the string `docproc.render` produces from elements with `role = content` or `figure_text` **after** normalization and cleaning. It is the single version used for chunks, `index_text`, citations, metadata suggestions, the citation viewer (FR-14) and the FR-31 view. Rules:
- The renderer is SOPilot code, deterministic, with a `normalizer_version`. A Markdown string exported by the PDF library itself (if any) is **not** used as the source of offsets. The library only provides the element tree through the adapter `extract/pdf.py`, the only place that depends on the library.
- Rendering: heading → `#` by level; a paragraph → one block, with hard line breaks inside the PDF joined by spaces; list items keep the source numbering (`5.1`, `a)`); tables → GFM tables, line breaks inside a cell replaced by spaces, a merged cell written once in its first cell with the others left empty, `|` inside cells escaped; blocks separated by exactly one blank line.
- Offsets `[char_start, char_end)` are counted in **Unicode code points** (Python string indexes) on `markdown`. Test invariant: for every content element, `markdown[char_start:char_end]` equals exactly that element's rendered text. The public API also returns UTF-16 offsets (`charStart16`, `charEnd16`) so the browser slices strings correctly when there are characters outside the BMP.
- Tables: `row_spans[i]` is the span of row `rows[i]` in the GFM table (from the first `|` to the last `|`, excluding the newline); the `|---|` separator line belongs to no row. Invariant: `row_spans` increases and lies within the table's `[char_start, char_end)`. These are the offsets used by `PROCEDURE_STEP` chunks and by tables split by rows (§5.4).
- Merged cells (owner decision 2026-10-21): the canonical Markdown still writes the value once in the first cell (display and offsets unchanged), but `cell_spans` says which rows/columns that cell covers, so the chunker repeats the value down each row when building `PROCEDURE_STEP` chunks (§5.4). Whether Docling (ADR-008) returns merged-cell spans is a `V2-20` confirmation item (not yet measured); without spans, `cell_spans = None`, the chunker does not guess values for empty cells, and the limitation is recorded in ADR-008 §6.
- A table spanning several pages is **one** element (the adapter joins consecutive table parts with the same column header), `page` is the first page, `page_end` the last, `row_pages` gives each row's page. Other elements have `page_end = page`.
- `page_index` (PDF): a consecutive, non-overlapping list of `{page, charStart, charEnd}` by element page; multi-page tables are split at row boundaries per `row_pages`; pages without content elements do not appear. The view uses it to insert "Page N" markers.
- Input Markdown is parsed then rendered again, so the canonical Markdown may differ in format from the original (for example `*` becomes `-`, Setext headings become `#`). The original file can still be downloaded. Identical content in PDF and MD is not promised to produce identical Markdown.
- No LLM is called in any extraction, normalization or rendering step.
- Coordinates (bbox) are not part of the MVP contract: no column is stored, no acceptance criterion, no UI uses them. The viewer only jumps to PDF pages.
- Changing `normalizer_version` invalidates old offsets: the active versions must be re-ingested (the admin command `python -m sopilot_ai.admin reindex`, not automatic in the MVP). The same command is used when changing the embedding model or the BM25 tokenizer (§3.3, §6.3).

Rules per format (V2-20; PDF uses Docling per ADR-008, confirmed against the §11 Q8 criteria):
- **PDF and MD only.** DOCX is deferred until after the MVP (owner decision 2026-10-20), TXT dropped from the MVP (owner decision 2026-10-21): core-api rejects them with `415` and creates no job. The worker still checks the PDF/MD allowlist before parsing (`UNSUPPORTED_TYPE`).
- **PDF with a text layer:** use the structure of **one** library (headings/paragraphs/lists/tables/reading order/page numbers) directly as `DocElement`s; no plain-text extraction followed by rebuilding structure, no fallback to a second library. OCR is **off** in the library configuration, with a test proving an image page yields 0 characters. Page numbers kept; reading order correct for multi-column pages; tables keep rows/columns. A document with almost no text (share of pages with text < 10% or a total < 200 characters) → `NO_TEXT_LAYER`; some pages without text → still processed, with the warning `PAGES_WITHOUT_TEXT` (§5.3a).
- **MD:** a pure-Python CommonMark + GFM parser (tables, lists); embedded HTML is kept as text; frontmatter is removed from the content and stored in `frontmatter`; Hugo shortcodes `{{< ... >}}` are removed (the V2-06 GitLab corpus). A file that is not valid UTF-8 → `INVALID_ENCODING` (core-api already blocks it; this is the second layer).

### 5.3 Boilerplate and metadata (V2-21)

- Repeated headers/footers: a line appearing on ≥ 40% of pages (owner decision 2026-11-04, changed from 60%: form appendices use a different header, so the main header covers only 41–57% of pages; on the V2-19 corpus boilerplate leakage was 19.8% at 60% and 8.1% at 40%, with no extra real wrongful removals) in the same top/bottom region of the page (after replacing page numbers with `#`) → `role = header|footer`, removed from content. **Applied only when the PDF has at least `SOPILOT_HEADER_FOOTER_MIN_PAGES` pages (default 3, a starting value fixed on the V2-19 corpus)**: with 1–2 pages every top/bottom line reaches ≥ 60%, so the rule would delete the title and the last paragraph. The document's first `heading` element is never marked `header`.
- VI/EN boilerplate blocks recognized by rules: national motto/heading lines, number/reference code, distribution list, signature block, Prepared/Reviewed/Approved tables, revision-history tables. Marked `role = boilerplate`, stored in `extracted_documents.boilerplate`.
- Metadata extracted from the boilerplate before removal: `docCode` (document code), `revisionLabel` (issue number), `effectiveDate`, `approvedBy`. Sent to core-api in the `READY` callback.
- Real content is never deleted: V2-21 reports the rate of boilerplate leaking into content and the rate of content wrongly removed on the V2-19 corpus.
- Removed boilerplate blocks are stored in `boilerplate` as `[{kind, page, text}]` so the FR-31 view can list them; they never enter `markdown`, chunks or the index.

### 5.3a Extraction warnings (FR-31)

Generated only on a concrete signal; there is no confidence score. Stored in `extracted_documents.warnings`, codes sent to core-api in the `READY` callback (`warningCodes`).

| Code | Condition | Data |
|---|---|---|
| `PAGES_WITHOUT_TEXT` | A PDF with a text layer has pages with < `SOPILOT_PAGE_MIN_CHARS` (default 20) characters | `pages` |
| `UNMAPPED_GLYPHS` | The extracted text contains `U+FFFD`, `(cid:n)` strings or Private Use characters | `pages`, `count` |
| `NO_HEADINGS_DETECTED` | A document longer than one page (PDF) or longer than `chunking.max_tokens` (MD) without any `heading` element | — |
| `BOILERPLATE_REMOVED` | Some blocks were marked `header`/`footer`/`boilerplate` (informational) | `count` |
| `CONVERTER_WARNING` | The ADR-008 library returns structured warnings for a page/element (only if the library has such an API) | `pages`, `kind` |

Warnings never cause `FAILED` and never block `READY`.

### 5.4 Document families and chunks (V2-22)

Heading recognition in priority order: Markdown headings (`#`) → numbering patterns (`1.`, `5.1`, `I.`, `Điều n`, `Chương n`, `Article n`) at the start of a short line → heuristics (uppercase lines, bold). A sentence ending with a period and longer than 120 characters is never a heading (prevents the "căn cứ ⏎ Điều 5 Luật Doanh nghiệp." bug).

| Family | Recognition | Chunk unit |
|---|---|---|
| `ISO_PROCEDURE` | Has Purpose/Scope/Procedure sections (Mục đích/Phạm vi/Nội dung) or a table with Responsibility + Step/Description columns | Sections by heading; **each row of the procedure table is a `PROCEDURE_STEP` chunk**, with content like `Bước: … \| Trách nhiệm: … \| Mô tả: … \| Biểu mẫu: …`; vertically merged cells (`cell_spans`, §5.2) are **repeated down each row** they cover, so steps 3 and 4 under one merged "Trách nhiệm" (Responsibility) cell still carry the right person |
| `LEGAL_ARTICLES` | ≥ 3 headings of the form `Điều n` / `Article n` | One chunk per article; long articles split by clause (Khoản) |
| `MARKDOWN` | MD files or `#` headings | Sections by heading |
| `PROSE` | None of the above | Paragraphs; merged up to `target_tokens`, split by sentence, never cut mid-sentence |

General rules:
- Tokens are counted with the active embedding model's tokenizer, passed to the chunker as a `docproc.tokens.Tokenizer` (§1.1), **not** with `tiktoken` (AUDIT-v2 §4.2). Chunks ≤ `max_tokens` including the heading-path prefix.
- A section < `min_tokens` is merged with the next sibling under the same parent; a section > `max_tokens` is split by paragraph, then by sentence. Splits happen on Unicode character boundaries, not bytes.
- `index_text` = `"{title} [{docCode}] › {section_path joined by ' › '}\n{content}"`; the ` [{docCode}]` part exists only when V2-21 extracted a code (`extracted_meta.docCode`), otherwise the prefix stays `"{title} › …"`. The prefix is in both the vector and the lexical index (V2-22). Why the code (owner decision 2026-10-21): the code sits in the header/footer and is separated from the content in §5.3; without it, a question like "QT-MH-01 bước 2 ai duyệt?" does not match lexically, and two documents with the same title but different codes cannot be told apart. Only `docCode` is added, **not** `revisionLabel` or `effectiveDate`: those change with each issue and would change the `content_sha256` of every chunk and void the embedding cache (§5.5), while users rarely ask by issue. The chunker takes `title` and `doc_code` as parameters and does not read metadata itself.
- An ordinary table (not a procedure table) longer than `max_tokens` is split by rows, repeating the column-header row in each part.
- Chunks carry `page_start/page_end` (PDF) and `char_start/char_end` on the canonical Markdown (every format) for viewer highlighting (FR-14). An ordinary chunk is a substring of `markdown`; a `PROCEDURE_STEP` chunk has content like `Bước: … | Trách nhiệm: …`, so it is not a substring; its offsets are the source row's `row_spans[i]` and `page_start = page_end = row_pages[i]`. A table chunk split by rows takes its offsets from the `row_spans` of its first to last row, and its pages from `row_pages`.

### 5.5 Embedding and cache

- Embed in batches of 16, on the threadpool. Before embedding, look up `rag.embedding_cache` by `(model, revision, sha256(index_text))`, the hash of exactly the string being embedded; embed only what is missing, then write the cache. No promised cache-hit rate. The `markdown` hash is never used to skip a whole version: skipping is decided only by the file's SHA-256 in core-api (FR-07).
- Record `embedding_provider/model/dim/revision` with the active provider's real values; no constant like the old `EMBEDDING_MODEL_NAME = "BGE_M3"`.
- An empty `revision` in the `eval` profile is a startup error; in the `local` profile it is allowed with a warning and recorded as `revision = "unpinned"`.

### 5.6 Activating a version (replacement, FR-07)

One transaction, once all vectors exist:
1. `INSERT` the new version's chunks, chunk_terms and extracted_documents (`extracted_documents` is written only here, so the FR-31 view never sees a version that is not active).
2. `UPDATE rag.document_access SET active_version_id = :new WHERE document_id = :doc AND deleted_at IS NULL`. No row (the document was deleted in the meantime) → rollback, job `CANCELLED`.
3. `DELETE FROM rag.chunks WHERE document_id = :doc AND version_id <> :new` (chunk_terms deleted by cascade).
4. Job `DONE`; outbox `VERSION_STATUS(READY)`.

While the new version is processing, retrieval keeps using the old one because it filters `version_id = active_version_id`. A `FAILED` new version does not touch the old one.

### 5.7 Background metadata suggestions (FR-28, V2-25)

- After step 8, if `suggest.enabled`, create `suggestion_jobs`. The worker processes suggestion jobs **after** ingest jobs, so suggestions are not on the path to `READY`.
- Input only from `extracted_documents` (the cleaned structure and canonical Markdown): title (first heading or file name), the heading outline, at most 3 representative passages, ceiling `SOPILOT_SUGGEST_MAX_INPUT_TOKENS=1500`. The file is never downloaded or parsed again.
- Rules first: title, language, `docCode`/`revisionLabel`/`effectiveDate` from §5.3.
- One `small_task` call with structured output `{description, category_id | null, proposed_category_name | null, tags[]}`; `category_id` must be in the payload's category list, otherwise it is dropped. Timeout `SOPILOT_SUGGEST_TIMEOUT=20s`, at most 1 retry; on failure only the rule results are sent with `method = RULES_FALLBACK`.
- Cached by the §3.5 key; never shared between workspaces.
- Sent to core-api through the `SUGGESTIONS_READY` outbox → `PUT /internal/documents/{id}/suggestions`. Suggestions contain no visibility or departments.
- Per-job measurements (`t_ready`, `t_suggest`, `llm_ms`, tokens in/out, fallback) for V2-25's p50/p95 report.
---

## 6. Retrieval (FR-10, FR-25)

### 6.1 The shared access filter

Every retrieval branch uses the same condition, fully parameterized (fix A3: no f-strings):

```sql
-- :wrole, :wdept from the token; :model, :rev are the active embedding. RLS already limits workspace_id.
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

The condition `workspace_id = :wid` is also written explicitly in the application layer in every query, next to RLS (two layers, ADR-005). The function `access_filter.allowed_cte()` is the only place that generates this SQL; the FR-29 tests call it directly.

### 6.2 Dense

```sql
SET LOCAL hnsw.iterative_scan = relaxed_order;   -- pgvector ≥ 0.8: keep scanning when the filter removes many candidates
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

The filter sits in `WHERE`/`JOIN`, so it applies **before** `LIMIT` (FR-25). At MVP scale (≤ 50 documents per workspace) Postgres usually chooses a filtered sequential scan, with exact results; HNSW only matters with more data.

### 6.3 Lexical (BM25 in SQL)

The tokenizer is identical to the harness's `eval/sopilot_eval/retrievers.py::tokenize`: lowercase, NFC, `\w+`, unigrams + bigrams (`a_b`), Vietnamese diacritics kept, **plus diacritic-free terms** (owner decision 2026-10-21, D11): for every unigram/bigram with diacritics, add a term with the same `tf` in diacritic-free form prefixed with `~` (NFD, combining marks removed, `đ → d`; `mua_hàng` also yields `~mua_hang`); terms unchanged by removing diacritics (English words, words without diacritics) produce no extra term; `lexical_len` counts only original terms. A query containing Vietnamese characters with diacritics uses the original terms as before; a query with **no** diacritics at all uses both the original terms and the matching `~` terms, so "quy trinh mua hang" matches "quy trình mua hàng" while English still matches on original terms. The index grows by at most about 2× (small at ≤ 50 documents). Because the tokenizer is shared with the harness and changing it forces a `reindex` (§5.2), this was fixed **before** `V2-07`'s official numbers. One module, `sopilot_ai.retrieval.lexical.tokenize`, is shared by ingest (generating `chunk_terms`, `lexical_len`), queries and the eval harness (which imports this module instead of a copy, V2-09). BM25 parameters as in the harness: `k1 = 1.5`, `b = 0.75`, `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`.

```sql
<allowed CTE>,
scope AS (                -- the chunks the asker may read: BM25 statistics are computed only over this set
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

Why a hand-written BM25 instead of `ts_rank` or an extension: (1) the scores match the eval harness, so RQ1 results measured with `eval/` apply to the service (V2-09 requires a match within tolerance); (2) Postgres has no Vietnamese dictionary and `ts_rank` is not BM25 (R2); (3) extensions such as `pg_search` need a custom Postgres image. The statistics `N`, `df`, `avgdl` are computed over the **readable set**, so the asker's scores are not influenced by documents outside their access. The cost is acceptable at MVP scale; if RQ4 or latency measurements show it is slow, the first optimization is a per-workspace statistics table, without changing the formula.

### 6.4 Fusion, rerank and the threshold gate

1. **RRF** over the two filtered lists: `fusion(c) = Σ wᵢ / (rrf_k + rankᵢ(c))`, `rrf_k = 60`, weights `[1.0, 1.0]` (configurable; the old 0.7/0.3 weights are one configuration in RQ1, not the default).
   - **Language-dependent BM25 weight (owner decision 2026-10-21).** For a chunk whose `lang` differs from the question's language (§7.1), that chunk's BM25-branch weight is multiplied by `cross_lingual_bm25_factor`. Reason: when asking in Vietnamese over English documents, BM25 matches only a few isolated words (tool names, "laptop"), so its list is almost random, yet RRF still adds points by rank and can push a wrong chunk above the dense branch's right one. A chunk or question `lang` that is `NULL`/not `vi` or `en` → factor `1.0`. Default `1.0` (no behaviour change); changed only when `V2-07` (RQ1b) shows hybrid losing to dense on the cross-lingual group, with the value chosen on the dev set. Questions are not translated by an LLM.
   - **Document codes in the question (owner decision 2026-10-21).** When the question contains a string matching the code pattern (`qa/doc_code.py`, starting regex `[A-ZĐ]{1,6}(?:[-/][A-Z0-9]{1,8}){1,3}` on the uppercased text, for example `QT-MH-01`), chunks of a version whose `extracted_meta.docCode` matches (compared after uppercasing and removing whitespace) get `retrieval.doc_code_boost` added to their `fusion_score` before `rerank_pool` is taken. Only `extracted_documents` of candidate `version_id`s that passed the access filter are looked up. Starting value `0.02` (about the contribution of rank 1 in one branch), not calibrated: tuned on the V2-28 check set.
2. Take the top `rerank_pool = 25` candidates by `fusion_score`.
3. **Rerank (if on)** runs on those 25 candidates **before** the threshold gate (fix R3) and reorders them by `rerank_score`.
4. **The threshold gate** compares the top candidate's score with the threshold of the running mode (`retrieval.thresholds`, fix R2/R4):

| Mode | Score used by the gate | Reason |
|---|---|---|
| `dense` | `dense_score` (cosine) | A common scale across questions |
| `bm25` | No gate | BM25 has no common scale; this mode is for eval only |
| `hybrid` | `dense_score` (cosine) of the top candidate by `fusion_score`, **always present** (see below) | RRF is rank-based and cannot be calibrated; same as the harness |
| `hybrid_rerank` | `rerank_score` (sigmoid) of the top candidate | The cross-encoder has a common scale |

**`dense_score` is always present (owner decision 2026-10-21, D2/P0-1).** A candidate found only by the lexical branch has no dense score from the dense branch. After RRF, for every candidate in `rerank_pool` missing a `dense_score`, the cosine is computed directly with a query by id (`SELECT id, 1 - (embedding <=> :qvec) FROM rag.chunks WHERE id = ANY(:missing) AND embedding_model = :active AND embedding_revision = :active_rev`, through the same §6.1 access filter). So the gate never compares a `NULL`, and `retrieval_results.dense_score` is complete for all 25 candidates. The function `fusion.gate_score` is single and imported by `eval/`; a test uses a candidate with only a BM25 score. No extra model call: the question vector already exists.

5. Above the threshold → the top `context_k = 5` chunks are the **hit chunks**, fed into context assembly (§6.4a). All 25 candidates with their four scores are written to `rag.retrieval_results` (`in_context` marks the 5 hit chunks). The frontend receives `rank` and (optionally for display) the gate score, not a `similarity_score` whose scale changes with configuration (R5).

### 6.4a Context assembly: search with small chunks, read by same-section group (owner decision 2026-10-21)

**Problem.** A chunk is a good unit to *search* (one procedure-table row, one clause), but too narrow to *read*. For example, section "5.1 Lập đề nghị mua hàng" (purchase requests) starts with "Applies to orders under 50 million; from 50 million see section 5.3", followed by the step table. The question "How long does the department head take to approve an 80-million order?" hits exactly the `PROCEDURE_STEP` chunk for step 2 ("Approve within 2 working days"), but given only that chunk the LLM does not see the applicability condition and answers wrongly. An SOP's conditions, exceptions and scope usually sit at the start of the section and are not repeated in each step.

**Approach.** Chunks, indexes and the threshold gate are unchanged. After §6.4 step 5, the module `retrieval/context.py` (pure functions, importable by `eval/`) builds the list of sources:

1. **The same-section group** of a hit chunk = the chunks with the same `version_id` and the same `section_path`, by `ordinal`. Fetched with one query for all hit chunks, `JOIN`ed with the §6.1 access filter like every other query (fail closed, even though the chunks are in the same version as an allowed chunk).
2. **Expansion:**
   - The group's total `token_count` ≤ `context.section_max_tokens` → take the whole group (an article with several clauses, a short section with a small step table).
   - Larger → take the hit chunk and its immediate predecessor and successor in the group; if the hit chunk is a `PROCEDURE_STEP` or `TABLE`, also take the group's first `SECTION`/`PROSE` chunk (the section's lead paragraph) if any.
3. **Merging:** windows of the same version that overlap or have adjacent `ordinal`s merge into **one** source; a source's rank is the best rank of the hit chunks in it.
4. **Token ceiling:** add sources by rank up to `context.max_tokens`. If the next source does not fit, shrink it to only its hit chunks; if it still does not fit, stop. The source of the rank-1 hit chunk is always included (chunks are ≤ chunking `max_tokens`, so it always fits).
5. **Rendering:** a source's content = the `content` of its chunks by `ordinal`, separated by a blank line, starting with the `section_path` line; the source's `page` = the smallest `page_start`. `PROCEDURE_STEP` chunks are already in the form `Bước: … | Trách nhiệm: …`, so no column-header row needs repeating.
6. `context.expand = false` → each hit chunk is one source, no merging (the behaviour before the change, used for ablation).

**Citations.** `[n]` points to source n. The `message_citations` row for `[n]` stores the `chunk_id` of the source's highest-ranked hit chunk; `char_start`/`char_end` are the span covering the source's hit chunks (adjacent after step 3); `snippet` is their `content`. The viewer highlights the hit part, not the whole section. `messages.context_sources` records each source's full `hitChunkIds` and `chunkIds` for faithfulness measurement and debugging.

**Not done.** No LLM call to summarize or select passages; no expansion to other sections or documents (a cross-reference "see section 5.3" is answered only if section 5.3 is itself a hit); no change to scores or ranks after the threshold gate. Owner decision 2026-10-21 (D6): **no** exception yet for references within the same document; `V2-19` counts cross-reference frequency on the corpus, and this is revisited only if the count shows it matters (§12a).

**Cost.** One query by `(document_id, version_id)` using `ix_chunks_doc`; no extra model call. The prompt is slightly longer (a 3,000-token ceiling, versus at most about 2,560 with only 5 chunks of 512 tokens, and often only a few hundred tokens when the hit chunks are table rows), within the TPM of the `generate` chain (§4.2).

### 6.5 Keeping the eval harness in sync

- `eval/` imports `sopilot_ai.docproc` (chunking), `sopilot_ai.retrieval.lexical` (tokenizer, BM25), `sopilot_ai.retrieval.fusion` (RRF, gate, language-dependent BM25 weight) and `sopilot_ai.retrieval.context` (§6.4a context assembly, from `V2-10`) instead of its own copies. The harness still runs in memory, without a DB or the stack.
- **The same chunker.** The harness's current chunker (`eval/sopilot_eval/corpus.py`, 800/100-character windows) is only for smoke runs and exploratory runs. The official RQ1–RQ3 and RQ5 numbers (`V2-07`) and the calibration of `retrieval.thresholds` run with `chunking: docproc` (384/512 tokens, the tokenizer of the model being measured), because score and rank distributions depend on chunk size. RQ5, comparing different models, counts tokens with each model's tokenizer but keeps the same `target/max`.
- `sopilot_ai.retrieval.lexical` and `fusion` belong to `V2-09`; until they exist, `V2-07` uses the harness's BM25 tokenizer and RRF, which are the originals the service must match (§6.3).
- V2-09 check: same V2-06 corpus, same configuration → the service's top-10 (through the DB, one workspace, OWNER) and the harness's overlap ≥ 95% by mean Jaccard; differences come only from approximate HNSW.

---

## 7. Q&A (FR-11..FR-15)

### 7.1 Steps

**Changed 2026-11-08 (owner decision, [HANDOFF-V2-10](../../04-reports/HANDOFF-V2-10-qa-pipeline-2026-11-08.md)): the pipeline is a chain of steps, a `QueryFrame`, a loose threshold gate.** The QA architecture is unchanged; the three adjustments below change only the organization and the calibration.

- **Step chain and `Decision`.** `qa/pipeline.py` runs a list of steps in exactly the order 1–12 below (quota → input check → PII → guard → rule router → meaningful tokens → rewrite/follow-up → retrieval + gate → context assembly → prompt → generate/stream + canary → citation post-processing → self-refusal detection → number/date check). Each step receives a shared context and returns a `Decision` of `continue | template | refuse | clarify`: `continue` moves to the next step; `template` returns a template answer (`outcome = TEMPLATE`); `refuse` is a refusal (guard: `outcome = REFUSED_GUARD`, no `refusal_reason`; missing evidence: `NO_EVIDENCE`; `OUT_OF_SCOPE` added by `V2-27`); `clarify` is only declared in the type and **no step emits it yet** (reserved for a later ticket; V2-10 has no ask-back branch). `V2-27`'s `OUT_OF_SCOPE` hook sits in the refusal step after the gate (step 8). The number of LLM calls is still at most 2 (rewrite when there is history, and generation).
- **`QueryFrame`.** `qa/query_frame.py` is a pure function that builds a `QueryFrame` **once** after the PII step (masked text, before the guard), collecting: the language (share of characters with diacritics, overridable by the request's `lang`), document codes (reusing `qa/doc_code.py`), dates and amounts, follow-up signals (`qa/followup_rules.yaml`), comparison/multi-part signals (keywords in YAML such as "so sánh", "khác nhau", "khác gì", "vs", "compare", "difference", or ≥ 2 document codes) and the count of meaningful tokens (computed after "strip"). The router, retrieval and prompt read from the `QueryFrame` and do not re-detect. The comparison signal is **only recorded** in `messages.route` (`route.signals.comparison = true`); it does not branch or change retrieval (splitting multi-part questions stays deferred, D9).
- **A loose threshold gate; the LLM refuses by itself.** Keep the placeholder threshold in `config/models.yaml` (`hybrid: 0.45`); the gate blocks only very low scores, is not lowered further and gets no new value from the RQ3 numbers. Reason: cosine is a weak gate (the score ranges of answerable and out-of-corpus questions overlap, [AUDIT-eval-rq1-rq3](../../04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md) §6; V2-07 §6, decided 2026-11-07), so a strict threshold would wrongly refuse valid questions. The rest is left to the generator: a question that passes the gate but whose answer opens with step 6's fixed sentence → `GENERATOR_NOT_FOUND` (D2, step 10). Every question with retrieval records `gate_score`, `threshold` and the refusal kind (`NO_EVIDENCE` | `GENERATOR_NOT_FOUND` | not refused) in `messages.route` for later calibration.

- **Implementation decisions (V2-10 milestone 3, 2026-11-09).**
  - *Quota.* Step 1 reserves atomically (`INSERT … ON CONFLICT … DO UPDATE … WHERE questions < limit`) and refunds when the turn ends with `TEMPLATE`, `REFUSED_GUARD` or `ERROR`. `ANSWERED` and `REFUSED_NO_EVIDENCE` (including `GENERATOR_NOT_FOUND`) still count because they cost embedding or LLM work. With both limits at 0, no table is read or written.
  - *History for the rewrite step* is at most 3 (question, answer) pairs with `outcome = ANSWERED` that are not hidden (§7.5); refused or template turns are not history. A conversation without any `ANSWERED` turn has nothing to rewrite and the question goes on as asked.
  - *The echo check ignores the fixed opening sentence.* The `protected` text the output guard compares against does not contain step 6's opening sentence, because the LLM is told to say exactly that sentence. Otherwise every `GENERATOR_NOT_FOUND` would turn into `REFUSED_GUARD` (found by an integration test in milestone 3).
  - *Written once at the end.* The new conversation (if any), the USER message, the ASSISTANT message, citations, `retrieval_results` and `guard_events` are written in **one** `tenant_tx` after the pipeline finishes; `citations` and `done` are emitted only after the write. If the client disconnects midway: an `ERROR` message is written with `route.aborted = true`, its content being the text the client received (excluding the part the guard was holding back), and the quota is refunded; the LLM stream reader closes its connection in the reader thread after the current read. `tokens_in`/`tokens_out` stay `NULL` because the stream returns no `usage`; `messages.model` is the model that actually answered (`LLMChain`'s `on_start`).
  - *The service is built on the first question* (loading the embedder, checking `/models`), not at startup, so the API still runs without a model or LLM endpoint; missing configuration gives the question a `503`. The conversation title is the first ≤ 60 characters of the PII-masked question, cut at a word boundary.

1. **Quota** (§7.4), skipped when off (default). Exhausted → SSE `error {code: QUOTA_EXCEEDED}`; nothing else is called.
2. **Input check and guard** (FR-13 layer 1):
   - **Validity (D4):** a question that is empty or only whitespace after NFC, or longer than `SOPILOT_MAX_QUESTION_CHARS=1000` characters (code points after NFC), is **refused, not truncated**: SSE `refusal {reason: "INPUT_INVALID"}` with a template stating the limit (too long) or asking for a question (empty), `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, no LLM call, not counted against quotas. No part of an overlong question gets past the guard.
   - **PII masking (D8):** `qa/pii.py` detects by rules: emails; Vietnamese phone numbers (`+84` or `0` followed by 9 digits, allowing spaces, dots, hyphens); citizen ID numbers (CCCD/CMND, 9–12 digits; owner decision 2026-11-08, also masking the common 10–11 lengths) and account numbers (9–16 digits) **only when** they follow a keyword within 20 characters (`cccd`, `cmnd`, `căn cước`, `hộ chiếu`, `passport`, `stk`, `số tài khoản`, `account`), so amounts like `500.000.000` are not masked by mistake. Replaced with `[EMAIL]`, `[PHONE]`, `[ID]`, `[ACCOUNT]`, recorded in `guard_events(INPUT_FLAG)` with `rule_id = pii.email|phone|id|account` and in `messages.checks.pii`. The masked text is the **working text** for every later step (guard, router, rewrite, embed, prompt) and for history turns sent to the rewrite; `messages.content` stores the original.
   - **Guard:** normalization (NFC, diacritics removed, leetspeak `0→o, 1→i, 3→e, 4→a, 5→s, 7→t`). Two-level VI/EN rules, written in `qa/guard_rules.yaml` (not in code):
   - **Block:** demands to reveal the system prompt/hidden rules/API keys; instruction overrides aimed at the instructions/prompt; impersonating the system role (`system:`, `[INST]`, `<|im_start|>`). Returns a fixed refusal, `outcome = REFUSED_GUARD`, records `guard_events(INPUT_BLOCK)`.
   - **Flag:** role play, "skip the step", mentions of another workspace. Still answered, records `guard_events(INPUT_FLAG)`.
   - **Truly harmful content (V2-10):** threats, self-harm, harassment (`harm.threat|self_harm|harassment`) have their own block rules, matching only clear intent (for example "muốn quấy rối đồng nghiệp" (wanting to harass a colleague), not "quy trình xử lý quấy rối" (the harassment-handling procedure)). Returns a fixed sentence (`harm_block`); self-harm returns `self_harm` with a configurable contact (`PipelineContext.support_contact`, its configuration source added at the API milestone), or `self_harm_no_contact` when not configured. `guard_events(INPUT_BLOCK)` stores only the `rule_id`.
   - **The profanity dictionary** in `guard_rules.yaml` (section `abuse`) matches on word boundaries over tokens, not substrings: a list with diacritics, a diacritic-free list only for teencode with no other meaning, and a `standalone_only` list ("cc", "đm", "vl"… which can mean "chứng chỉ", "định mức", "vật liệu") counted only when the question is at most `standalone_max_tokens` tokens and the token is not joined with `-`/`/` (document codes like `QT-VL-02`). Profanity decides nothing by itself: the router strips it and looks at the rest, recording `guard_events(INPUT_FLAG)` `abuse.profanity|abuse.standalone`.
   - The starting rules were ported from `eval/provider_check/check_providers.py::RULE_PATTERNS` and then tuned with V2-10's **own check set** (separate from the set used to write the rules). Block rules are deliberately narrow so they do not block common SOP questions ("quy tắc ăn mặc" (dress code), "quy tắc nội bộ" (internal rules), "tắt bộ lọc spam" (turn off the spam filter)): "ẩn" (hidden) and "an" coincide without diacritics, so the "quy tắc ẩn" (hidden rules) rule compares on the text with diacritics.
3. **Rule router:** greetings/thanks/questions about the bot (VI/EN) → a template, `outcome = TEMPLATE`, no LLM call, not counted against quotas. Questions the rules do not decide go through the **semantic router** (owner decision 2026-10-20, details and thresholds in `V2-27`): it compares the original question's embedding with example sentences in `qa/router_exemplars.yaml` and routes to a template only above the intent's threshold and with enough `margin` over the nearest SOP example; no LLM call, switched by `SOPILOT_SEMANTIC_ROUTER_ENABLED`. The original question's vector is reused for dense retrieval only when there is no history **and** the working text (PII-masked, greeting/profanity tokens stripped per V2-10) equals the original question; otherwise retrieval embeds exactly the search string again (D5). The router's decision is recorded in `messages.route`.
   - **"Strip then judge" (V2-10):** the router strips greeting, thanks and about-the-bot tokens (keywords in `qa/templates.yaml`, compared without diacritics) and profanity tokens from the question. Nothing left → a template by the kind stripped (profanity > about the bot > thanks > greeting); some tokens left but below the meaningful-token threshold → the same rule, and if nothing was stripped then "did not understand the question". Content left → RAG on the stripped question. `refusal_reason = INPUT_INVALID` goes only with the "did not understand the question" template.
   - **Meaningful tokens (D4):** after "strip then judge" (V2-10), a meaningful token is a `\w+` token (lowercase, NFC) present in the `rag.chunk_terms` of the documents the asker may read (the same `scope` CTE as §6.3, so no word outside access leaks) or in `qa/lexicon.yaml` (common VI/EN words, owner approved; diacritic-free matching only for multi-word phrases, since a single word without diacritics easily collides, for example "đúng"/"dùng"). Fewer meaningful tokens than `min_meaningful_tokens` (default 1, in `qa/guard_rules.yaml`) → the "did not understand the question" template, `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, no retrieval.
   - **Extended router (D1, V2-27):** `off_topic` does **not** branch here: it takes effect only after the gate refuses (step 8), because the router does not know what the corpus contains. `action_request`, `personal_data`, `legal_medical` only attach a disclaimer (step 12) and still run RAG. `about_source` (needs history) and `feedback_in_chat` (only when what remains after "strip" is empty) return a template immediately without an LLM call: `about_source` re-lists the previous turn's citations from `message_citations`, `feedback_in_chat` explains how to click 👎.
   - **V2-27 implementation (2026-11-13):** the `semantic_router` step (`conversations/steps.py` `SemanticRouterStep`) comes after `meaningful_tokens` and is in the chain only when `SOPILOT_SEMANTIC_ROUTER_ENABLED=true` (default `false`; when off the chain is exactly as in V2-10). It embeds `text` (the original PII-masked question, not stripped, not rewritten) once; the routing conditions, thresholds and `margin` are in `qa/router.py` and `qa/router_thresholds.yaml`. Example sentences are loaded when building `QAService` (`conversations/factory.py` `build_router`), with vectors read from/written to `rag.embedding_cache` by `(model, revision, sha256("router-exemplar-query:" + sentence))`: the prefix separates the examples' query vectors from ingest's passage vectors; changing the model or revision re-embeds them. `messages.route.semantic = {layer, intent, topIntent, score, margin}`; when routing, `route.layer = "semantic"`, `rule_id = router.<intent>`; `abuse_only` also records `guard_events(INPUT_FLAG, router.abuse)`. `about_source` without readable citations returns the `about_source_none` template. **Not done:** `feedback_in_chat` does not route yet (it goes to RAG as before, recall 0 on `dev`/`test`); waiting for the owner to decide how to detect "the rest is empty" (V2-27, [AUDIT-routing-guard-eval-2026-11-13](../../04-reports/AUDIT-routing-guard-eval-2026-11-13.md)).
4. **Question rewrite** only when the conversation has ≥ 1 earlier turn: send at most the 3 most recent turns (only the cleaned questions and answers, no chunks) to `llm.rewrite` and get a standalone question; the history turns also use the PII-masked text (step 2). Record `messages.rewrite_status` (`OK` | `FAILED`; `NONE` without history). On failure → use the original question, **unless** it has follow-up signals (rules in `qa/followup_rules.yaml`: demonstratives such as "đó", "này", "vậy còn", "thế còn", "it", "that", "what about", or fewer than `SOPILOT_FOLLOWUP_MAX_TOKENS` tokens), in which case it is **not retrieved**: a template asks for the full question, `outcome = TEMPLATE`, `refusal_reason = INPUT_INVALID`, `route.layer = 'followup_rule'` (D5). A question without follow-up signals continues with the original. The rewritten question goes to retrieval and to the generation prompt (steps 5, 6).
5. **Retrieval** (§6) on the working text (the rewritten question if any, otherwise the masked and stripped question). Below the threshold → step 8. Above it → context assembly (§6.4a).
6. **Prompt assembly** (layer 2): a fixed system prompt per `prompt_version`, containing a random canary token generated per request and the rules: use only data inside the tags, answer in the question's language, attach `[n]` to every claim, and when information is missing **start the answer with exactly the fixed opening sentence** for the language ("Không tìm thấy thông tin này trong các tài liệu hiện có." / "I could not find this in the available documents.", D2); keep the applicability conditions and exceptions present in the sources; for situational questions (with the asker's specific facts) list the relevant conditions, say which are met and which lack information, then answer in the form "if … then …"; when the question is about a document code, issue number or effective date, use the source's `code`, `rev`, `effective`. The system prompt has a line "Today is {YYYY-MM-DD}" in the `SOPILOT_TIMEZONE` timezone (default `Asia/Ho_Chi_Minh`) to understand "last week", "current". Changing the prompt changes `prompt_version`. Each §6.4a source is wrapped in `<source n="1" title="…" page="3" code="QT-MH-01" rev="03" effective="2026-03-01">…</source>` (D3): `code`, `rev`, `effective` come from `extracted_documents.extracted_meta` (`docCode`, `revisionLabel`, `effectiveDate`) of the source's `version_id`, in the `rag` tables (no reading of `core`); missing attributes are omitted; values are escaped like content. These fields go only into the prompt, **not** into `index_text` (keeping the embedding cache, §5.4). `<`, `>`, `&` are escaped in content. The question is in its own `user` message, not joined into the system prompt, and **without conversation history** (D5): history is used only by step 4 to clarify the question. The `user` message contains `Câu hỏi:` (Question:) with the rewritten question (when step 4 succeeded) or the masked question, plus `Câu gốc:` (Original question:) when the two differ, so the LLM can cross-check if the rewrite drifted.
7. **Generation and streaming** (layer 3): SSE `delta` emits text but **holds back** the last `max(len(canary), 40) + 32` characters not yet emitted (40 is the echo window; a 23-character canary gives 72). On every new delta, check whether the buffer contains the canary or a run of ≥ 40 consecutive characters of the system prompt. If so → stop the stream, emit `replace` with the fixed refusal, `outcome = REFUSED_GUARD`, `guard_events(OUTPUT_CANARY | OUTPUT_PROMPT_ECHO)`.
8. **Refusal for missing evidence** (FR-12): a fixed answer in the question's language + at most 3 "closest documents" (titles of the documents containing the top candidates, already access-filtered so nothing outside access leaks), `outcome = REFUSED_NO_EVIDENCE`, `refusal_reason = NO_EVIDENCE`. The generator is not called. If the router classified the question `off_topic` above its threshold (V2-27, considered only at this step, D1), then `refusal_reason = OUT_OF_SCOPE`: the same refusal but **without** "closest documents". The router never changes a "let through" decision of the gate.
9. **Citation post-processing** (FR-11): find `[n]` in the final text; an `n` matching no source in the prompt → removed from the text. Each valid `n` is stored in `message_citations` per the §6.4a citation rules (the snippet is the `content` of the source's hit chunks). Record `messages.checks.citationCount` = the number of remaining valid `[n]`.
10. **Detecting the LLM's own refusal (D2):** if the final text (after `strip`, case-insensitive, leading punctuation removed) starts with step 6's fixed opening sentence, then `outcome = REFUSED_NO_EVIDENCE`, `refusal_reason = GENERATOR_NOT_FOUND`, and no citations are stored. Deterministic string matching; unit tests for both languages.
11. **Number and date check (V2-10):** `qa/checks.py` (pure functions) extracts numbers, dates and amounts from `finalText`, normalizes them (thousands separators removed, `dd/mm/yyyy` to ISO) and compares them with the content of the sources sent in the prompt. A value not in the sources → `done.warnings: [{code: "NUMBER_NOT_IN_SOURCES", values: […]}]` and `messages.checks.numberWarnings`. **Flag only, never edit or delete text** (it has already been streamed); numbers written in words are not detected, so they are not reported.
12. **Disclaimers (V2-27):** questions the router tagged `action_request`, `personal_data` or `legal_medical` are still answered; after generation, one more `delta` with a fixed disclaimer in the question's language (from `qa/templates.yaml`) is emitted before `citations`, included in `finalText` and recorded in `messages.checks.disclaimers`. The router blocks nothing.

The question's language is detected with a light rule (the share of Vietnamese characters with diacritics) and can be overridden by `lang` in the request.

### 7.2 SSE

`POST /ai/v1/conversations/{conversationId}/messages` with `Accept: text/event-stream`. Body `{ "content": "…", "lang": "vi" | "en" | null }`. `conversationId = "new"` creates a new conversation.

| Event | Data | When |
|---|---|---|
| `meta` | `{conversationId, messageId, mode, lang}` | First |
| `delta` | `{text}` | Each text fragment |
| `replace` | `{text, reason: "GUARD"}` | A canary/echo is detected midway |
| `refusal` | `{text, reason: "NO_EVIDENCE" \| "OUT_OF_SCOPE" \| "INPUT_INVALID" \| "GUARD", nearestDocuments: [{documentId, title}]}` | A refusal, instead of `delta`. `nearestDocuments` exists (possibly empty) only for `NO_EVIDENCE`; other reasons carry no documents |
| `citations` | `[{n, documentId, versionId, title, page, charStart, charEnd, snippet}]` | After generation finishes |
| `done` | `{finalText, outcome, refusalReason, warnings: [{code, values}], usage: {questionsLeftToday}}` (`usage` is `null` when quotas are off; `refusalReason` is `null` when not refused; `warnings` is empty when there are no flags, §7.1 step 11) | Last; the frontend replaces the streamed text with `finalText` (invalid `[n]` removed) |
| `error` | `{code, message}` | `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR` |

**Outcome → events (implemented in milestone 3).**

| Outcome | Events |
|---|---|
| `ANSWERED` | `delta`…, `citations` (if any), `done` |
| A non-refusal template (greeting, thanks, about the bot, profanity only) | one `delta` then `done`; `outcome = TEMPLATE`, `refusalReason = null` |
| `INPUT_INVALID` (empty, too long, not understood, unclear follow-up) | `refusal`, `done` |
| Input guard | `refusal {reason: "GUARD"}`, `done` (`REFUSED_GUARD`) |
| Output guard (canary, echo) | the `delta`… already emitted, then `replace`, `done` (`REFUSED_GUARD`) |
| `NO_EVIDENCE` | `refusal` with `nearestDocuments`, `done` |
| `GENERATOR_NOT_FOUND` | the model's sentence streamed as `delta`; only `done`, no `citations` |
| `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR` | only `error` (no `done`); the turn is still recorded (`outcome` is `QUOTA_EXCEEDED` or `ERROR`) |

The body `content` is at most 20,000 characters (more gives `422`); from 1,001 to 20,000 characters the "too long" template is returned (D4). A `conversationId` that is neither `new` nor a UUID, or that does not belong to the caller, is `404`.

Headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`. A `: ping` comment every 15 s so proxies do not cut the connection.

### 7.3 Citation viewer (FR-14) and "Nội dung hệ thống nhận diện" (FR-31)

`GET /ai/v1/documents/{documentId}/versions/{versionId}/content` returns from `extracted_documents`, only when the document passes the §6.1 filter and `versionId` is the active version (`active_version_id`); otherwise `404` (not distinguishing "does not exist", "outside access" and "not READY yet"):

```json
{ "documentId": "…", "versionId": "…", "fileType": "PDF", "normalizerVersion": "1",
  "markdown": "# Quy trình mua hàng\n\n…",
  "pages": [ {"page": 1, "charStart": 0, "charEnd": 812, "charStart16": 0, "charEnd16": 812} ],
  "warnings": [ {"code": "PAGES_WITHOUT_TEXT", "pages": [3, 7]} ],
  "removedBlocks": [ {"kind": "footer", "page": 1, "text": "QT-MH-01 | Lần ban hành 03 | Trang 1/7"} ] }
```

- The FR-31 view and the citation viewer share this response. The original PDF is opened by the frontend with core-api's pre-signed URL (`/api/v1/documents/{id}/download-url`) and jumps to `page`; MD shows `markdown` and highlights `[charStart16, charEnd16)`.
- There is an endpoint only for the active version; there is no way to read a processing or `FAILED` version (owner decision 2026-10-21: the view opens only at `READY`). The frontend gets `currentVersion` and `latestVersion` from core-api to label versions.
- `removedBlocks` is limited to 200 entries; `markdown` is returned verbatim and the frontend renders it without executing HTML.

### 7.4 Quotas and provider limits (FR-09)

Commercial quotas are paused (owner decision 2026-10-20, PRD-V2 §8.10): the two variables below default to `0` = unlimited, and `usage_counters` and `system_usage` are neither read nor written. The tables stay in the migrations so quotas can be re-enabled without a schema change.

- **Per user:** `SOPILOT_QUOTA_QUESTIONS_PER_USER_DAY` (reference `20` per PRD FR-09 when enabled). `usage_counters` is incremented in the transaction at the start of the request, **before** the LLM call; `TEMPLATE` and `REFUSED_GUARD` turns do not count.
- **System-wide:** `SOPILOT_QUOTA_QUESTIONS_SYSTEM_DAY` (reference `400` when enabled) through `rag.system_usage`.
- The per-provider limiters below are **always on**, because they are technical free-tier limits, not commercial quotas.
- **Per provider:** in-memory token buckets for RPM and TPM of each `(provider, model)` from `models.yaml` (one API process, so no Redis needed). The prompt's tokens are estimated before the call; an empty bucket → treated as `429` and the next model in `chain` is used. The whole chain exhausted → `error LLM_UNAVAILABLE`, refunding the user's quota turn if quotas are on.
- **No model switch midway (owner decision 2026-10-21, P1-5).** Moving to the next model is allowed only **before** the first `delta` is emitted. Errors after that (disconnects, `5xx`, an empty bucket) → `error LLM_UNAVAILABLE`, `outcome = ERROR`, the quota turn refunded; no rerun on another model, because the emitted text would be duplicated.
- **Per-model context ceiling.** Each `chain` entry has `context_max_tokens` (§4.2). Switching to a model whose ceiling is below `context.max_tokens` reassembles the context with that ceiling (dropping low-ranked sources first, keeping the rank-1 source) before calling. The prompt token estimate uses the model's own tokenizer if `models.yaml` declares `tokenizer`, otherwise a rough character-based estimate; it is used only for budgeting, never for chunking (chunking uses the embedding's tokenizer, §5.4).

### 7.5 Conversations (FR-15) and history after losing access

| Method & path | Notes |
|---|---|
| `GET /ai/v1/conversations` | The `sub`'s conversations in `wid`, newest first |
| `GET /ai/v1/conversations/{id}` | Messages + citations; `404` if not one's own |
| `PATCH /ai/v1/conversations/{id}` | Rename |
| `DELETE /ai/v1/conversations/{id}` | Soft delete |
| `POST /ai/v1/conversations/{id}/messages` | §7.2 |

Every query has `workspace_id = :wid AND user_id = :sub` (besides RLS). When a conversation is reread, each answer is checked with the current §6.1 filter against **every document it was generated from**: every `documentId` in `messages.context_sources` (sources sent in the prompt) together with `message_citations.document_id`. If **any** document in that set can no longer be read (visibility changed, department changed, deleted), the whole answer and its passages are replaced with `{hidden: true, reason: "ACCESS_REVOKED" | "DOCUMENT_DELETED"}`; the question is still shown (PRD §8.8). The reason is `DOCUMENT_DELETED` when a document in the set is deleted or has no access row, otherwise `ACCESS_REVOKED`; "readable" uses exactly the predicate of `allowed_cte()` (`cited_access_cte()` in `access_filter.py`). Question rewriting (§7.1 step 4) uses only turns that are not hidden.

**Hiding by context, not only by citations (owner decision 2026-11-09, V2-10 milestone 3).** The earlier version checked only `message_citations`, so answers without valid `[n]` (`ANSWERED` with `checks.citationCount = 0`, `GENERATOR_NOT_FOUND`, an `ERROR` midway) stayed visible after access was lost even though their text came from the sources, and such an `ANSWERED` turn still entered the rewrite history. ADR-007 §4.4 counts "the LLM context" as a form of reading, so every source in the context decides hiding. Accepted trade-off: over-hiding when a revoked document was only in the context but not actually used by the answer; the hidden state is recomputed on each read, so the answer reappears when access is granted again. Citations are still merged into the checked set (fail closed), even though each citation already points to a context source.

**Citations to an old version (owner decision 2026-10-21, D10).** core-api deletes the old version when a new one exists, so `/content` (§7.3) serves only the active version and returns `404` for an old `version_id`. When a conversation is reread, each citation carries `isCurrentVersion` (comparing the citation's `version_id` with `rag.document_access.active_version_id`). A citation that is no longer current still shows the stored `snippet` (`message_citations.snippet`); the frontend labels it "Old version" and does not open the viewer. The MVP keeps no `extracted_documents` of old versions.

### 7.6 Feedback and knowledge gaps (FR-16, FR-17)

Owner decision 2026-10-20 (TECH-V2-core-api §11 Q1, ADR-004 §4.1): FR-16/FR-17 live in ai-service.

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

- `PUT /ai/v1/messages/{id}/feedback` `{vote, comment}`: only the conversation's creator, only `ASSISTANT` messages.
- `GET /ai/v1/knowledge-gaps?status=open|resolved`: OWNER, ADMIN; includes (owner decision 2026-10-21, D2) questions whose `refusal_reason` is `NO_EVIDENCE` or `GENERATOR_NOT_FOUND`, downvoted answers, and `ANSWERED` questions with `checks.citationCount = 0`; with the question, time and feedback. **Excludes** `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE` and `REFUSED_GUARD`. No asker name (keeping FR-15 conversation privacy). The question shown to admins is the **PII-masked** version (§7.1 step 2, recomputed with `qa/pii.py` at response time, no second copy stored); askers still see their own question verbatim.
- `POST /ai/v1/knowledge-gaps/{messageId}/resolve`: OWNER, ADMIN.

---

## 8. Internal API on the ai-service side

The contract is defined in TECH-V2-core-api §8. On the ai-service side:
- Every `/internal/**` endpoint checks `Idempotency-Key`: already in `processed_requests` → return the successful response again without redoing the work. The key is written in the same transaction as the change.
- `POST /internal/ingestions`: `UPSERT rag.document_access` only when `accessRevision` is greater than the stored one (or none exists); `INSERT ingestion_jobs ... ON CONFLICT (version_id) DO UPDATE SET status = 'QUEUED', attempts = 0, failure_code = NULL, request_attempt = EXCLUDED.request_attempt, lease_until = NULL WHERE ingestion_jobs.status = 'FAILED' AND EXCLUDED.request_attempt > ingestion_jobs.request_attempt`; `NOTIFY rag_jobs`. That is: resending the same request (same `attempt`) creates no new job; a user retry (`attempt` incremented, TECH-V2-core-api §5.5) puts a `FAILED` job back in the queue; running or `DONE` jobs are not touched. (Changed 2026-10-21: the earlier version used `DO NOTHING`, so retries would never run.)
- `PUT /internal/document-access/{documentId}`: updates if `accessRevision` is newer; returns `{applied}`. Chunks are not touched (FR-26: changing visibility does not re-embed).
- `DELETE /internal/documents/{documentId}`: set `document_access.deleted_at` (retrieval drops the document immediately), cancel pending jobs, delete chunks, `extracted_documents`, `suggestion_jobs`, then delete the `document_access` row. `message_citations` are kept so history shows the `DOCUMENT_DELETED` reason.
- Sending to core-api: outbox `rag.outbox_events`, with a dispatcher like core-api's (immediate push after commit + a scan every 5 s, backoff, `DEAD` after 20 attempts, no retry on `4xx`).

---

## 9. Test strategy

| Layer | Content | Tools |
|---|---|---|
| `docproc` unit | Fixtures: two-column PDFs, tables in the body, merged cells, repeated headers/footers; MD (frontmatter, GFM tables, embedded HTML, shortcodes); DOCX/TXT rejected; ISO SOPs with procedure tables; Điều/Khoản (article/clause) texts with an in-sentence reference to "Điều 5"; `section_path` is ancestors; no splitting inside characters; chunks ≤ `max_tokens` by the model's tokenizer | pytest |
| Canonical Markdown and offsets | The invariant `markdown[char_start:char_end]` = the element's rendered text, for every element of every fixture and every V2-19 corpus file; chunk offsets inside `markdown`; `row_spans` increasing, inside the table, `markdown[row_spans[i]]` containing exactly the cells of `rows[i]`; multi-page tables with `page_end > page`; `page_index` consecutive, non-overlapping, pages in `1..page_count`; UTF-16 offsets correct for strings with non-BMP characters; rendering the same input twice gives the same string; NFC text; no boilerplate element in `markdown` | pytest (property tests over fixtures) |
| Warnings | Each §5.3a code has a fixture that produces it and a clean fixture that does not; OCR off: an image-only page yields 0 characters | pytest |
| Extraction quality | Metrics on the V2-19 corpus (heading recall, leaked boilerplate, wrongly removed content) | A script in `eval/`, not run in CI |
| Retrieval unit | SQL BM25 and harness BM25 give the same scores (tolerance 1e-4) on a small corpus; RRF; the language-dependent BM25 weight (`1.0` gives plain RRF results, `lang` NULL is not reduced); the threshold gate per mode; §6.4a context assembly (small groups taken whole, large groups ±1 plus the lead paragraph for `PROCEDURE_STEP`, adjacent windows merged, token ceiling, the rank-1 source always present, `expand = false` keeps the old behaviour, the citation span covers only hit chunks); invalid `[n]` citations removed; a canary detected even when split across two deltas | pytest |
| Integration | Testcontainers Postgres + pgvector with the real `sopilot_ai_app` role: RLS, an expired job lease is reclaimed, transient errors are retried after `run_after` without sending `FAILED`, deterministic errors are `FAILED` on the first attempt, replacing a version does not interrupt retrieval, an old `accessRevision` is ignored, idempotency; retrying a `FAILED` job with a new `attempt` reruns exactly once, resending the same `attempt` creates no job; `/content` returns `404` for an inactive version, `FAILED` and outside access, and returns the old version while the new one is processing | pytest + testcontainers |
| FR-19 (ai-service part) | Two workspaces whose documents contain their own secret strings: Q&A, conversations, the content viewer and retrieval_results never contain the other workspace's string; a reused connection carries no old `app.workspace_id` | CI |
| FR-29 (ai-service part) | Within one workspace: a `DEPARTMENTS` document with a secret string never appears in dense, BM25, rerank, context-assembly expanded chunks, the prompt sent to the LLM (a fake provider records the prompt), citations, history or "closest documents"; cases for department changes (new token), narrowing visibility, deleting documents | CI, fake LLM |
| Guard | V2-10's own check set: false blocks ≤ 2%, 0 canary leaks | CI |
| Input and PII | Empty and > 1000-character questions refused (not truncated); questions without meaningful tokens; a follow-up after a failed rewrite returns a template without retrieval; PII masked correctly and amounts like `500.000.000` not masked; `messages.content` verbatim while the gap list shows the masked version | pytest |
| Outcome | Correct `refusal_reason` for the four cases (§3.4); a fake LLM opening with the fixed sentence (VI/EN) → `GENERATOR_NOT_FOUND`; the gap list excludes `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE`, `REFUSED_GUARD` and includes `ANSWERED` without citations; the `off_topic` router never changes the gate's "let through" decision | pytest, fake LLM |
| Additional retrieval | The `hybrid` gate with a top candidate that has only a BM25 score (harness and service give the same `gate_score`); `~` terms: "quy trinh mua hang" matches "quy trình mua hàng", English questions unchanged; the code `QT-MH-01` recognized and `doc_code_boost` added | pytest |
| Merged cells and boilerplate | `cell_spans` → `PROCEDURE_STEP` repeats merged-cell values down each row; 1–2-page PDFs do not lose their title or last paragraph to the header/footer rule | pytest |
| Prompt | A fake provider records the prompt: `<source>` has `code/rev/effective`, the current-date line is present, **no** history, both the rewritten and the original question; fallback does not switch models after the first `delta`; the number/date check only flags | pytest, fake LLM |
| Contract | The same `services/contracts/` JSON Schema as core-api | CI |

---

## 10. Configuration (environment variables)

| Variable | Default | Notes |
|---|---|---|
| `SOPILOT_DB_URL` | — | Role `sopilot_ai_app` |
| `SOPILOT_CORE_JWKS_URL`, `SOPILOT_CORE_BASE_URL` | `http://core-api:8080/.well-known/jwks.json`, `http://core-api:8080` | |
| `SOPILOT_INTERNAL_TOKEN` | — | Shared with core-api |
| `SOPILOT_S3_ENDPOINT`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_AI_ACCESS_KEY`, `SOPILOT_S3_AI_SECRET_KEY` | — | Read-only credential |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | — | Only in `.env` |
| `SOPILOT_MODELS_CONFIG` | `config/models.yaml` | |
| `EMBEDDING_REVISION`, `RERANK_REVISION`, `RERANK_ENABLED` | —, —, `false` | |
| `SOPILOT_LLM_BASE_URL`, `SOPILOT_LLM_MODEL`, `SOPILOT_LLM_API_KEY` | —, —, — | The Modal endpoint (OpenAI-compatible); the model id comes from `GET /models`. Missing → a startup error (no default) |
| `SOPILOT_LLM_RPM`, `SOPILOT_LLM_TPM`, `SOPILOT_LLM_CONTEXT_MAX_TOKENS` | `60`, `200000`, empty | Placeholders, measured on the endpoint; an empty ceiling = not declared |
| `SOPILOT_QUOTA_QUESTIONS_PER_USER_DAY`, `SOPILOT_QUOTA_QUESTIONS_SYSTEM_DAY` | `0`, `0` | FR-09, `0` = off (research phase) |
| `SOPILOT_INGEST_MAX_ATTEMPTS`, `SOPILOT_SUGGEST_TIMEOUT`, `SOPILOT_SUGGEST_MAX_INPUT_TOKENS` | `3`, `20s`, `1500` | |
| `SOPILOT_MAX_QUESTION_CHARS` | `1000` | §7.1 step 2: longer is refused, not truncated (D4); code points after NFC |
| `SOPILOT_FOLLOWUP_MAX_TOKENS` | `4` | §7.1 step 4: questions shorter than this count as having a follow-up signal; starting value, not measured, tuned by V2-27 |
| `SOPILOT_TIMEZONE` | `Asia/Ho_Chi_Minh` | Timezone of the "Today is …" line in the system prompt (§7.1 step 6) |
| `SOPILOT_HEADER_FOOTER_MIN_PAGES` | `3` | §5.3; starting value, fixed on the V2-19 corpus |
| `SOPILOT_PAGE_MIN_CHARS` | `20` | Threshold for the `PAGES_WITHOUT_TEXT` warning (§5.3a); starting value, not calibrated |
| `SOPILOT_PDF_ARTIFACTS_PATH` | `/models/pdf` (volume) | The PDF library's models (if any), downloaded in advance, never during processing |
| `HF_HOME` | `/models` (volume) | Models downloaded once, not again on each start |

The authoritative list is `services/ai-service/.env.example` and `src/sopilot_ai/config.py`. `GEMINI_API_KEY` is a leftover of the pre-2026-11-01 provider plan; `GROQ_API_KEY` is still used by metadata suggestions (ADR-006 §4.4).

---

## 11. Open questions (owner decision 2026-10-20)

The owner approved everything as proposed below.

| # | Question | Decision |
|---|---|---|
| Q1 | Which service holds feedback and knowledge gaps? | ai-service (§7.6); see TECH-V2-core-api §11 Q1. |
| Q2 | Hand-written BM25 in SQL or an extension? | Hand-written (§6.3), to match the harness and avoid a custom Postgres image. |
| Q3 | Rerank: local only, or also a free API provider (for example Pinecone bge-reranker-v2-m3) for weak machines? | Local for eval (ADR-006); the interface already allows adding a provider, done only if local rerank is measured too slow for demos. |
| Q4 | Default chunk size | `target 384 / max 512` tokens by the bge-m3 tokenizer; V2-07 may change it after measuring, and the harness and service configurations must be identical. |
| Q5 | Worker in the same container as the API or a separate one? | The same image, two processes (two compose services sharing the image), so embedding does not block the API and RAM can be limited separately. |
| Q6 | The default refusal threshold before V2-07 | A placeholder (§4.2); no refusal metric is published before calibration on the dev set. |
| Q7 | Does the FR-31 view open right after convert/clean or only at `READY`? (owner decision 2026-10-21) | Only at `READY`. Opening early would need writing `extracted_documents` before embedding, a read path for inactive versions (which would need FR-19/FR-29 tests), cleanup on failure and another UI state; an estimated 1–2 extra days while the remaining wait for embedding is small. Reconsidered when `t_ready` measurements show a need. |
| Q8 | Which PDF library? (owner decision 2026-10-21, [ADR-008](../decisions/adr-008-pdf-extraction-docling.md)) | **Docling** (MIT), ADR `approved`, **no spike measurements yet**; PyMuPDF 2.x (AGPL-3.0 or commercial) not used. `V2-20` confirms Docling against the criteria below and records the results in ADR-008 §6; if a hard constraint fails, it stops and asks the owner. Hard constraints: offline on CPU, OCR can be disabled, page numbers per element, Vietnamese NFC, license (AGPL needs owner confirmation). Comparison: headings/tables per V2-19 document family, time and peak RAM per page on the owner's machine, maintenance effort. 2-day timebox; only one library in the runtime. Details: [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) §6. |

### 11a. Decisions from the end-to-end audit by query type (owner decision 2026-10-21)

The owner approved everything as the audit proposed; no decision breaks the constraints "one generation call, no LLM classifier, CPU, access filtering before `LIMIT`".

| # | Question | Decision | Applied in |
|---|---|---|---|
| D1 | Does `off_topic` branch before retrieval or only label after the gate refuses? | After the gate: only when the gate has refused is `OUT_OF_SCOPE` assigned; the router never changes a "let through" decision. The router does not know what the corpus contains, so it must not block early | §7.1 steps 3, 8; V2-27 |
| D2 | Add `refusal_reason` and a fixed opening sentence when the LLM refuses by itself? | Yes | §3.4, §7.1 steps 6, 10; §7.6; V2-10, V2-13 |
| D3 | Add `code`, `rev`, `effective` to `<source>` and today's date to the prompt? | Yes; `index_text` unchanged; the `DOC_INFO` chunk deferred (§12a) | §7.1 step 6; V2-10 |
| D4 | Questions > 1000 characters: refuse or truncate? | Refuse; empty questions are refused too | §7.1 step 2; V2-10 |
| D5 | A follow-up after a failed rewrite: a template asking back instead of running RAG? | Yes. The generation prompt gets the rewritten question plus the original and no history; re-embed when the working text differs from the original question | §7.1 steps 3–6; V2-10, V2-27 |
| D6 | Open a §6.4a exception for references within the same document? | Not yet; `V2-19` first counts cross-reference frequency | §6.4a, §12a; V2-19 |
| D7 | Add a ticket for a Vietnamese SOP check set (30–40 questions)? | Yes: `V2-28`, `total_tickets` 27 → 28 | PLAN-V2 |
| D8 | PII: where is it masked, which version is stored? | Masked when sending to the LLM, when rewriting and in the gap list; `messages.content` stores the original for the asker | §7.1 step 2, §7.6; V2-10, V2-13 |
| D9 | Split multi-part questions (N retrievals, one generation) in V2? | Deferred (P2), only if the "multi-passage" measurements of `V2-07`/`V2-10` are poor | §12a |
| D10 | Citations to an old version? | Show only the passage with an "Old version" label; old-version Markdown is not kept | §7.5; V2-15 |
| D11 | Diacritic-free BM25 terms: decided before or after `V2-07`? | Before, so the tokenizer is frozen once | §6.3; V2-07, V2-09 |

---

## 12. Not ported from the old system

- The hard-coded `EMBEDDING_MODEL_NAME = "BGE_M3"`, the 512-token cut with `tiktoken`, `cl100k_base` for Vietnamese (AUDIT-v2 §4.2, AUDIT-ingestion §2.4).
- Three parallel extractors, synchronous tesseract OCR, semantic dedup over 3 windows (AUDIT-ingestion §2.1, §2.5).
- TXT extraction, `preview_extractor.py` re-parsing files for metadata suggestions, Markdown rendering with `rehype-raw` in the frontend.
- Multi-tier intent classification, LLM-based harmful-content filtering, Llama Prompt Guard 2 (FR-13, V2-02).
- Copying `allowed_roles/allowed_departments/allowed_users` into every chunk; `department_id` concatenated with f-strings (A2, A3, ADR-007).
- The 0.15 threshold on a mixed score scale; overwriting `similarity_score` with the rerank score (R2, R4).

## 12a. RAG designs considered and not included in V2 (owner decision 2026-10-21)

Problem characteristics: each workspace has ≤ 50 structured SOP/regulation documents; questions mostly look up steps, roles, deadlines, conditions and exceptions within one document; VI/EN and cross-lingual; citations to page/passage; CPU, free LLMs, at most one generation call and one rewrite. V2 already has light forms of two ideas: the threshold gate followed by refusal is Corrective RAG's "not enough evidence" branch (the fallback is a refusal with the closest documents, no web search); the rule/semantic router skipping retrieval for greetings is a reduced Adaptive RAG (business questions always retrieve).

| Design | Why it is not in V2 | Reconsider when |
|---|---|---|
| GraphRAG, LightRAG, HippoRAG | A small corpus, local lookup questions, no whole-corpus synthesis needed; building a graph costs LLM calls and gets entities wrong easily | Measurements show many questions needing cross-references between SOPs ("per QT-05", "form BM-01"); then try rule-based linking first |
| RAPTOR, summary trees | The document's heading tree already exists and is used in §6.4a; LLM summaries can distort | Overview questions on long documents that §6.4a does not cover |
| Iterative, multi-hop, agentic RAG, Self-RAG | Breaks the single-generation constraint and free quotas, hard to reproduce; Self-RAG needs a specially trained model | — |
| HyDE, multi-query, LLM question translation | An extra LLM call; multilingual `bge-m3` already handles cross-lingual in the dense branch; the BM25 branch is handled by the §6.4 weight | RQ1b shows dense is also weak cross-lingually |
| LLM-based contextual retrieval | The `title [docCode] › section_path` prefix (§5.4) is the deterministic version of the same idea | After `V2-07`, per PLAN-V2 |
| Per-document long context | Citation mapping to passages must be kept; no measurements yet | After the §6.4a ablation, try it for short documents when the hit chunks concentrate in one document |
| Multimodal/visual RAG, SQL RAG | Out of scope: no OCR, no live tabular data. Known risk: the "Content" part of ISO SOPs drawn as shape-based flowcharts may be extracted in the wrong reading order; `V2-19` should include flowchart files to measure it | After the MVP |
| Rule-based splitting of multi-part and comparison questions (at most 3 sub-queries, RRF merge, one generation) | Risk of lower recall if split wrongly; no measurements yet (D9) | The "multi-passage" measurements of `V2-07`/`V2-10` are poor |
| Asking back on ambiguous questions (top hits spread over ≥ 3 documents with close scores, short question) | Needs score-distribution measurements before setting the condition | After `V2-07`, once measured |
| Rule-based expansion of references within the same document ("per section 5.3", "Article 12") | Breaks §6.4a's "Not done", adds tokens (D6) | `V2-19`'s cross-reference count on the corpus shows it matters |
| A `DOC_INFO` document-card chunk (code, issue, effective date, approver, outline) | Changes the `chunk_type` CHECK and the citation-offset convention; `<source code rev effective>` (§7.1 step 6) already answers most questions about codes and validity | The `V2-28` check set shows validity/approval questions still fail |
| Per-chunk `lang` (bilingual SOPs); updating the title in `index_text` when a document is renamed; a per-workspace abbreviation dictionary | Meaningful only when the cross-lingual factor ≠ 1, or needs measuring first. Known limitation: `index_text` keeps the title at ingest time (§5.4); renaming a document does not update the index until `reindex` | After `V2-07`, when there is a real need |
| Using `wdept` or the asker's seniority to interpret the question; LLM question translation | The token carries only UUIDs, ai-service does not read `core`, and implicit filtering easily goes too far | — |
