---
id: HANDOFF-WAVE1-2026-11-11
title: "Wave 1 handoff (V2-13, V2-25): implementation, tests and points to review"
status: draft
created: 2026-11-11
updated: 2026-11-13
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

> Translated from Vietnamese on 2026-11-13; content unchanged. It describes the state on 2026-11-11: since then V2-13, V2-25, V2-27 and V2-28 moved to `review`, V2-16 to `review` (see the PLAN).

# Wave 1 handoff: V2-13 and V2-25

This report lets another agent (or the project owner) review without the conversation history. The ticket
statuses are **not** changed: both stay `todo` until the project owner reviews the evidence. The changes are in the
working tree, not committed.

## 1. Summary

| Ticket | Status after the session | Notes |
|---|---|---|
| V2-13 feedback and knowledge gaps | Code done, IT green. Added to `tenant-isolation.yml`. | Not marked done. |
| V2-25 background metadata suggestions | Code on both sides (ai-service + core-api), IT green. | Not run for real with a Groq key; p50/p95 not measured. |
| V2-27 semantic router | Not done. | Needs a 300–500-question labelled set reviewed by the project owner. |
| V2-16 demo + one-command compose | Not done. | Needs Dockerfiles and compose changes (rule 8, ask first). |
| V2-28 Vietnamese SOP check set | Blocked. | Assigned to `owner`. |

## 2. Test run results

| Scope | Command | Result |
|---|---|---|
| ai-service lint | `uv run ruff check src tests` | All checks passed |
| ai-service unit | `uv run pytest tests/unit` | 559 passed, 3 skipped, 15 xfailed |
| ai-service integration (Docker pgvector) | `uv run pytest tests/integration` | 134 passed |
| ai-service migration | `./scripts/check-migrations.ps1` | passed (rag V004, core V010 included in the check) |
| ai-service new IT | `test_feedback_isolation.py` (9), `test_suggestions.py` (10) | 19 passed |
| core-api unit | `./mvnw test` | 126 passed, including `ArchitectureTest` |
| core-api new IT | `DocumentSuggestionIT` | 7 passed |
| core-api existing IT | `DocumentLifecycleIT` | 18 passed (after changing `suggest.enabled` to `true`) |
| core-api tenant | `TenantIsolationApiIT`, `TenantIsolationIT` | 17 passed (a case added for `PUT .../suggestions`) |
| docs | `./scripts/check-docs.ps1` | passed |

Not run: the full `./mvnw verify` (every core-api IT). No browser opened (no UI in this wave).

## 3. V2-13: changes

The tables and columns already exist in migration `rag/V003`, so there is no new migration.

- `services/ai-service/src/sopilot_ai/feedback/gaps.py`: the gap criteria as constants. The SQL is generated from here.
- `feedback/repository.py`: SQL for feedback, the list and resolution.
- `api/feedback.py`: three endpoints. Registered in `api/app.py`.
- `tests/integration/test_feedback_isolation.py`: 9 tests.
- `.github/workflows/tenant-isolation.yml`: added `tests/integration/test_feedback_isolation.py` to the ai-service step (at the project owner's request).

Endpoints:
- `PUT /ai/v1/messages/{id}/feedback` `{vote: -1|1, comment?}`: 204. Only the conversation owner, only ASSISTANT messages. One vote per person per answer.
- `GET /ai/v1/knowledge-gaps?status=open|resolved`: OWNER/ADMIN; a MEMBER gets 403. Questions are PII-masked with `qa/pii.py`. No user id and no answer content returned.
- `POST /ai/v1/knowledge-gaps/{id}/resolve`: OWNER/ADMIN; idempotent; 404 if it is not a gap.

Gap criteria: `refusal_reason` in `NO_EVIDENCE`/`GENERATOR_NOT_FOUND`, or `ANSWERED` with `citationCount = 0`, or a -1 vote. Excludes `TEMPLATE`, `REFUSED_GUARD`, `QUOTA_EXCEEDED`, `OUT_OF_SCOPE`, `INPUT_INVALID`.

## 4. V2-25: changes

### 4.1 Flow

1. When ingest finishes, `ingest/handler.py` enqueues the suggestion job in the same transaction that makes the version READY (only when the payload has `suggest.enabled`).
2. The worker (`worker.py`) runs `suggest/runner.py.drain` after each ingest round, then flushes the outbox.
3. Runner: reads the extracted text (not the file on S3); rules take the title; checks the cache; calls the Groq model once, retrying exactly once; on error `RULES_FALLBACK`.
4. The result is written to `rag.suggestion_jobs` and put on the outbox as `SUGGESTIONS_READY`.
5. The dispatcher sends `PUT /internal/documents/{id}/suggestions` to core-api.
6. core-api (`document/SuggestionService.java`) stores the suggestion per version and applies it only when that version is current. Each field changes only when its source is not `USER`.

### 4.2 Model and configuration (at the project owner's request)

- `config/models.yaml`: `providers.groq` (base URL `https://api.groq.com/openai/v1`, key `SOPILOT_GROQ_API_KEY`) and `llm.suggest` with model `qwen/qwen3.8-27b`, `timeout_s` 20, RPM 30, TPM 60,000, `extra_body: {reasoning_format: hidden}`.
- `.env.example`: added `SOPILOT_GROQ_API_KEY=<groq-api-key>` and the commented optional variables. `.env` was not read or edited.
- `providers/llm.py`: `build_chain` reads each task's `timeout_s`. The existing tasks keep 120 s.
- Checked: `build_chain(config, "suggest")` yields `groq`, `qwen/qwen3.8-27b`, `https://api.groq.com/openai/v1`, 30 RPM, 60,000 TPM, a 20 s timeout.

### 4.3 Migrations

- `infrastructure/db/migrations/rag/V004__suggestion_claim.sql`: policy `definer_suggestions` for the owner, function `rag.claim_suggestion_job(lease)` SECURITY DEFINER with `search_path`, REVOKE PUBLIC, GRANT to `sopilot_ai_app`.
- `infrastructure/db/migrations/core/V010__document_suggestions.sql`: table `core.document_suggestions` (key `version_id`, FK to `core.documents`), RLS FORCE, GRANT SELECT/INSERT/UPDATE to `sopilot_core_app`.

### 4.4 Code changes

ai-service:
- New: `suggest/__init__.py`, `suggest/rules.py` (pure), `suggest/llm.py` (pure: prompt, output validation, cache key), `suggest/runner.py` (IO), `db/repositories/suggestions.py`.
- Changed: `ingest/handler.py` (enqueue), `worker.py` (`_suggest_deps`, drain), `providers/llm.py` (timeout), `config/models.yaml`, `.env.example`.
- Tests: `tests/unit/test_suggest.py` (16), `tests/integration/test_suggestions.py` (10).

core-api:
- New: `document/SuggestionService.java`, migration `core/V010`, `DocumentSuggestionIT.java` (7 tests).
- Changed: `document/DocumentRepository.java` (`upsertSuggestion`), `document/InternalDocumentController.java` (PUT), `document/DocumentService.java` (`suggestSpec`, `ingestPayload` takes a `suggest` parameter), `tag/TagService.java` (`names`), `DocumentLifecycleIT.java` (expects `suggest.enabled = true`), `tenancy/TenantIsolationApiIT.java` (a new case for the PUT).

## 5. Decisions to review

1. **Groq for suggestions.** ADR-006 §4.4 and `CLAUDE.md` removed Groq from answer generation and the judge. Suggestions are not answers, so bringing Groq in here is the project owner's decision; the ADR/PLAN docs need a note.
2. **Model id not verified.** `qwen/qwen3.8-27b` comes only from the project owner's request. `GET /models` could not be called without a key. If the id is wrong, every job falls back to `RULES_FALLBACK` and the log records `suggest_model_failed`.
3. **Processing order.** Suggestions run synchronously in the worker loop after ingest. Each job can wait up to about 40 s (two calls of 20 s each). Meanwhile the next ingest has to wait. If this becomes a problem, split it into a separate process.
4. **Tags.** The model may only attach tags that already exist in the workspace; no new tags are created. `proposedCategoryName` is only stored; no category is created.
5. **Title.** The suggested title is the first Markdown heading, and replaces the file name when the title's source is not `USER`. This is new behaviour for users, so the project owner needs to confirm it.
6. **Groq limits.** RPM/TPM set at 30/60,000 are provisional, not measured.
7. **Measurement incomplete.** The ticket requires `t_upload_ack`, `t_ready`, p50/p95. Currently only `t_suggest_ms`, `llm_ms`, `tokens_in/out` (estimated, not real counts), `fallback`, `cache_hit`, `attempts` are recorded. `t_upload_ack` and `t_ready` are not recorded yet.
8. **No direct verification with Groq.** All tests use `ScriptedChain`. One run with a real key is needed before ticking the criteria.

## 6. Not done and why

- **V2-27**: needs a 300–500-question routing label set reviewed by the project owner. Without it, thresholds cannot be set and the ≤ 2% criterion cannot be checked.
- **V2-16**: needs core-api/ai-service Dockerfiles and changes to `docker-compose*.yml`. The project rules require asking first.
- **V2-28**: assigned to `owner`; the 30–40-question set and the source documents need review.

## 7. Proposed next steps

1. The project owner sets `SOPILOT_GROQ_API_KEY` in the local `.env`, then runs `GET /models` to confirm the id, then runs one real document and records the measurements.
2. Decide on the processing order (item 5.3) and the title (item 5.5).
3. Review the evidence before marking V2-13 and V2-25 `done`; update the PLAN.
4. Start V2-16 once the compose changes are approved.
