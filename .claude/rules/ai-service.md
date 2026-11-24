---
paths:
  - "services/ai-service/**"
  - "eval/**"
---

# ai-service (FastAPI, Python ≥ 3.11, uv)

Design source: `docs/architecture/components/ai-service.md`. Tables: `docs/architecture/data/rag-schema.md`. PDF library: Docling (ADR-008).

## Structure (`src/sopilot_ai/`)

| Package | Role | May import |
|---|---|---|
| `docproc/` | extract → clean → normalize → render → chunk. Pure functions over text | stdlib, numpy, markdown-it, own modules. **No** DB/HTTP/S3/FastAPI |
| `retrieval/` | dense + BM25 + RRF fusion, `access_filter` | `db.engine` helpers, `providers` |
| `providers/` | embedding/rerank adapters, `registry` (reads `config/models.yaml`) | no `api`/`ingest` |
| `db/` | `engine.py` (`tenant_tx`, `system_tx`), `repositories/*` (SQL) | sqlalchemy |
| `api/` | FastAPI routers; app factory `uvicorn --app-dir src sopilot_ai.api.app:create_app --factory` | everything |
| `ingest/`, `worker.py`, `outbox/`, `admin.py` | job worker (`python -m sopilot_ai.worker`), outbox to core-api, admin CLI (`python -m sopilot_ai.admin reindex`); both need `PYTHONPATH=src` (`[tool.uv] package = false`) | everything |

Enforced by `tests/unit/test_architecture.py`: `docproc` purity, no upward imports, tenant binding only in `db/engine.py`, `rag.document_access` read only through `access_filter`.

## Tenancy and data access

- Any SQL on a table with `workspace_id` runs in `async with tenant_tx(engine, workspace_id, user_id)`. `system_tx` is only for SECURITY DEFINER helpers and the non-RLS tables (`embedding_cache`, `processed_requests`, `system_usage`).
- Retrieval reads documents only through `allowed_cte()` + `access_params(principal)`. It adds `workspace_id = :wid` next to RLS and fails closed. Never write a second access filter.
- SQL is `sqlalchemy.text(...)` with bound parameters. Module-level `text(f"...")` may only interpolate code constants such as `allowed_cte()`, never request data. This is why ruff `S608` stays off: its 6 hits are these constants.
- The principal comes from the core-api access token (`auth/jwt.py`, JWKS). `/internal/**` checks `X-Internal-Token` with `hmac.compare_digest`.

## Models and config

- Models, providers, thresholds and chunk sizes are declared **only** in `config/models.yaml` (`${VAR:default}` expansion). Never hard-code a model id in Python.
- Settings: `config.py` (`pydantic-settings`, env aliases `SOPILOT_*`, secrets as `SecretStr`). New settings need an `.env.example` entry with a dummy value.
- The LLM answer pipeline (V2-10, `qa/`, `conversations/`, `providers/llm.py`) is done. The answer model is one OpenAI-compatible Modal endpoint (`providers.modal`, `SOPILOT_LLM_*` in `services/ai-service/.env`); the container is `infrastructure/modal/serve_vllm.py`. Warm it before a run: a cold start takes minutes and the client times out after 120 s.
- Log with `structlog` (`log.info("event_name", key=value)`). `print()` fails ruff `T20`.

## Tests

- `tests/unit/`: no Docker and no model download. Use `tests/fakes.py` (`FakeEmbedder`, `Words` tokenizer) instead of real models. `tests/integration/`: auto-marked `integration`, starts a disposable pgvector Postgres with the real `rag` migrations (Docker). `pytestmark = pytest.mark.pdf` tests need `--extra pdf` and skip without it.
- `asyncio_mode = "auto"`: write `async def test_...` without `@pytest.mark.asyncio`.
- Names are behaviour sentences: `test_numbered_sentence_is_a_body_line_not_a_heading`.
- Commands: `./scripts/validate-build.ps1 -Scope ai` (compileall + ruff); `./scripts/run-tests.ps1 -Scope ai-service -Type unit|integration|all` (installs `--extra dev --extra pdf`); CI runs `uv sync --extra dev; uv run ruff check; uv run pytest tests/unit` (PDF tests skip there).
- `eval/` is a separate uv project (`cd eval; uv run pytest -q`). It imports `sopilot_ai.retrieval` so harness and service rank identically. A retrieval change must keep `eval` tests green. See `eval/README.md` before reporting numbers.
