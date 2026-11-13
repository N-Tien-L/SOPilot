# ai-service (V2)

FastAPI service (Python >= 3.11, uv, SQLAlchemy async) that owns the Postgres schema `rag`: extraction, chunks, embeddings, retrieval, question answering, conversations, feedback and ingestion jobs. It reads documents from S3 with a read-only user and never writes schema `core`; core-api owns documents and identity. Design: [TECH-V2-ai-service](../../docs/architecture/components/ai-service.md) (cite by section). Contracts and envelopes: [HTTP conventions](../../docs/architecture/api/http-conventions.md). Layering and tenancy rules for contributors: `.claude/rules/ai-service.md`.

Two processes run from the same package: the HTTP API and the ingest worker (`python -m sopilot_ai.worker`). A third entry point, `python -m sopilot_ai.admin`, is an operator command.

## Layout (`src/sopilot_ai/`)

| Package / module | Role |
|---|---|
| `api/` | FastAPI app factory (`app.py`, `create_app`) and routers: `documents`, `conversations`, `feedback`, `internal` |
| `auth/` | Verifies the core-api access token through JWKS (`jwt.py`) |
| `config.py` | Environment settings (`pydantic-settings`, `SOPILOT_*` aliases, secrets as `SecretStr`) |
| `db/` | `engine.py` (`tenant_tx`, `system_tx`) and `repositories/` (SQL) |
| `docproc/` | Pure functions: extract, clean, normalize, render, chunk (PDF via Docling, Markdown) |
| `ingest/` | Job handler and pipeline run by the worker; object-store reader |
| `retrieval/` | Dense + BM25 + RRF fusion, access filter, context assembly |
| `providers/` | Embedding, rerank and LLM adapters; `registry.py` reads `config/models.yaml` |
| `qa/` | Question routing, guard rules, prompt, citations, answer pipeline |
| `conversations/` | Conversation service, events (SSE) and repository |
| `feedback/` | Message feedback and knowledge gaps |
| `suggest/` | Metadata suggestions (LLM with a rules fallback), run by the worker |
| `outbox/` | Dispatcher for callbacks to core-api |
| `quota/` | Question counters (off by default) |
| `worker.py`, `admin.py` | Worker process; operator CLI (`reindex`) |

Other paths: `config/models.yaml` (the only place models, providers, thresholds and chunk sizes are declared; read it there, not here), `tests/`, `Dockerfile`.

## Run

Prerequisites, infrastructure and the environment files are in [local development](../../docs/operations/local-development.md). From this directory, with the ai-service environment loaded into the shell:

```powershell
uv run --extra local --extra pdf uvicorn --app-dir src sopilot_ai.api.app:create_app --factory          # API, port 8000
$env:PYTHONPATH = "src"; uv run --extra local --extra pdf python -m sopilot_ai.worker                    # ingest worker
$env:PYTHONPATH = "src"; uv run python -m sopilot_ai.admin reindex --dry-run   # list stale versions
```

`[tool.uv] package = false`, so the code runs from `src` (`--app-dir src` or `PYTHONPATH=src`). The reindex procedure is [here](../../docs/operations/reindex.md). Optional extras: `dev` (pytest, ruff), `pdf` (Docling), `tokenizer`, `local` (sentence-transformers); the container image installs `local` and `pdf`.

## Configuration

Variable names only; values and the PowerShell loader are in [`.env.example`](.env.example). Defaults are in [`config.py`](src/sopilot_ai/config.py).

| Group | Variables |
|---|---|
| Required | `SOPILOT_DB_URL` (`postgresql://` form, role `sopilot_ai_app`), `SOPILOT_INTERNAL_TOKEN` |
| core-api link | `SOPILOT_CORE_BASE_URL`, `SOPILOT_CORE_JWKS_URL` |
| Object storage (read-only user) | `SOPILOT_S3_ENDPOINT` (host:port, no scheme), `SOPILOT_S3_SECURE`, `SOPILOT_S3_REGION`, `SOPILOT_S3_BUCKET`, `SOPILOT_S3_AI_ACCESS_KEY`, `SOPILOT_S3_AI_SECRET_KEY` |
| Profile and models | `SOPILOT_PROFILE` (`local` or `eval`), `SOPILOT_MODELS_CONFIG`, `EMBEDDING_REVISION`, `RERANK_*`, `SOPILOT_RERANK_BASE_URL`, `SOPILOT_GROQ_BASE_URL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` (expanded in `config/models.yaml`); `HF_HOME` and `HF_HUB_OFFLINE` are read by the Hugging Face libraries, not by this code |
| Answer LLM | `SOPILOT_LLM_BASE_URL`, `SOPILOT_LLM_API_KEY`, `SOPILOT_LLM_MODEL`, `SOPILOT_LLM_RPM`, `SOPILOT_LLM_TPM`, `SOPILOT_LLM_CONTEXT_MAX_TOKENS` (consumed through `config/models.yaml`) |
| Worker | `SOPILOT_INGEST_MAX_ATTEMPTS`, `SOPILOT_INGEST_LEASE_SECONDS`, `SOPILOT_INGEST_BACKOFF_SECONDS`, `SOPILOT_WORKER_POLL_SECONDS`, `SOPILOT_OUTBOX_MAX_ATTEMPTS`, `SOPILOT_OUTBOX_HTTP_TIMEOUT` |
| Question answering | `SOPILOT_QUOTA_QUESTIONS_PER_USER_DAY`, `SOPILOT_QUOTA_QUESTIONS_SYSTEM_DAY` (0 = off), `SOPILOT_MAX_QUESTION_CHARS`, `SOPILOT_FOLLOWUP_MAX_TOKENS`, `SOPILOT_SUPPORT_CONTACT`, `SOPILOT_TIMEZONE`, `SOPILOT_SEMANTIC_ROUTER_ENABLED` |
| Suggestions | `SOPILOT_GROQ_API_KEY`, `SOPILOT_SUGGEST_*` |
| Document processing | `SOPILOT_HEADER_FOOTER_MIN_PAGES`, `SOPILOT_PAGE_MIN_CHARS`, `SOPILOT_PDF_*` |

## Endpoints

Read from the routers in `src/sopilot_ai/api/`. User routes need `Authorization: Bearer <core-api access token>`; `/internal/**` needs the `X-Internal-Token` header and an `Idempotency-Key` header (UUID) on the three write routes. Responses are plain JSON, not the core-api `{data, traceId}` envelope.

| Method and path | Access | Notes |
|---|---|---|
| `GET /health` | Public | `{"status":"ok"}`, or `{"status":"degraded","staleVersions":N}` when chunks use another embedding model, revision or normalizer |
| `GET /ai/v1/documents/{documentId}/versions/{versionId}/content` | Bearer | Canonical Markdown of the **active** version of a document the caller may read; any other version, or a missing, unreadable, not `READY` or deleted document, is `404` |
| `POST /ai/v1/conversations/{id}/messages` | Bearer | Body `{content, lang?}`; answers `text/event-stream`. `{id}` is a conversation UUID or `new`; another user's or workspace's conversation is `404`. Events and error codes: TECH-V2-ai-service §7.2 |
| `GET /ai/v1/conversations` | Bearer | `limit` (1-100, default 50), `offset` |
| `GET /ai/v1/conversations/{id}` | Bearer | An answer from a document no longer readable comes back as `hidden` |
| `PATCH /ai/v1/conversations/{id}` | Bearer | Title |
| `DELETE /ai/v1/conversations/{id}` | Bearer | Soft delete, `204` |
| `PUT /ai/v1/messages/{messageId}/feedback` | Bearer | `{vote: -1\|1, comment?}` → `204`; `404` if not the owner's assistant message |
| `GET /ai/v1/knowledge-gaps` | Bearer, OWNER/ADMIN | `status=open\|resolved`, `limit`, `offset`; MEMBER `403` |
| `POST /ai/v1/knowledge-gaps/{messageId}/resolve` | Bearer, OWNER/ADMIN | `{note?}` |
| `POST /internal/ingestions` | `X-Internal-Token` | `202 {queued}`; writes `document_access` and the job in one transaction |
| `PUT /internal/document-access/{documentId}` | `X-Internal-Token` | `{applied}`; ignored when `accessRevision` is not newer |
| `DELETE /internal/documents/{documentId}?workspaceId=` | `X-Internal-Token` | Idempotent, always `200 {deleted:true}` |

An unconfigured LLM endpoint or embedding model surfaces as `503` on the first question (the providers are built lazily).

## Tests

```powershell
./scripts/run-tests.ps1 -Scope ai-service -Type unit          # no Docker
./scripts/run-tests.ps1 -Scope ai-service -Type integration   # Docker (disposable pgvector Postgres)
./scripts/validate-build.ps1 -Scope ai                        # compileall + ruff
```

`tests/unit/` includes `test_architecture.py`; `tests/integration/` is auto-marked `integration`. The script installs the `pdf` extra, CI only `dev`, so tests marked `pdf` skip in CI. Which suites run where, and where evidence goes: [testing strategy](../../docs/quality/testing-strategy.md). The eval harness (`eval/`) imports `sopilot_ai.retrieval`; a retrieval change must keep it green.
