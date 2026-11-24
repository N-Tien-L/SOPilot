---
id: V2-49
title: "ai-service: per-message pipeline trace, token usage and the trace endpoint for the Pipeline Inspector"
type: feature
status: done # todo | in_progress | review | done | blocked
created: 2026-11-24
updated: 2026-11-24
author: "Owner"
scope: ai-qa
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10]
blocks: [V2-18, V2-50, V2-48]
blocked_reason: ""
branch: "feat/ai-rerank-toggle"
refs:
  - docs/architecture/components/ai-service.md
  - docs/architecture/data/rag-schema.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-10-ai-service-qa-pipeline.md
---

# TICKET V2-49: Pipeline trace for the Pipeline Inspector

> **Scope:** `ai-qa` | **Size:** `L` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP`

> **Recorded after the work was done.** The code below was written by another agent session on the working tree without a ticket. This file records what is in the code, the evidence the orchestrator saw on 2026-11-24, and what nobody has checked. It is not an owner-reviewed design.

## 1. Context & goal
Make the question pipeline observable for the acceptance demo and for reading retrieval behaviour: each step reports when it starts and ends, the answer keeps a sanitized trace, and the creator can read it back later. The consumer is the Pipeline Inspector UI (`V2-50`).

## 2. What the code does
- `qa/pipeline.py`: `run_steps(..., on_step_start, on_step_end)` callbacks, with the elapsed time of each step.
- `conversations/events.py`, `service.py`: a new SSE event `step` (stage, status, summary, duration, detail) emitted only when the request sets `includeTrace: true`; the final trace is saved with the turn.
- `conversations/trace.py` (new): `TraceCollector` maps the pipeline steps onto 11 Inspector stages, redacts the per-request canary token before any SSE emit or database write, never stores raw document text or unmasked PII, and `synthesize_legacy_trace` builds a best-effort trace for answers stored before this change. `strip_document_data` removes chunk, source and prompt bodies when the creator no longer may read a cited document.
- `retrieval/retriever.py`: `on_phase` hook and `RetrievalStats` (counts and timings per phase: dense, sparse, RRF, rerank) used by the trace.
- `conversations/repository.py`: `rag.message_traces` insert and `message_trace(...)`; the retrieved chunks are always hydrated live through `allowed_cte()`, so a revoked chunk is never returned. `messages.tokens_in` and `tokens_out` are now filled (they were `NULL`).
- `providers/llm.py`: `stream_options.include_usage` and an `on_usage` callback to read the token counts.
- `api/conversations.py`: `GET /ai/v1/conversations/{conversationId}/messages/{messageId}/trace`, creator only; another user's or workspace's message is `404`.
- Migration `infrastructure/db/migrations/rag/V005__message_traces.sql`: table `rag.message_traces` (primary key `message_id`, `workspace_id`, `user_id`, `trace jsonb`), RLS `ENABLE` and `FORCE` with the `tenant_isolation` policy.

## 3. Also in this change (not tracing; owner to accept or revert)
Found in the same working tree. They change behaviour and no ticket asked for them:
- `conversations/factory.py` passes `merge_adjacent_sections=False` to the prompt context (`retrieval/context.py` gains the option, default `True` so eval keeps its behaviour): adjacent chunks of different sections are no longer merged into one prompt block.
- `qa/prompt.py`: the Vietnamese rewrite system prompt is rewritten (pronoun replacement rules, a worked example).
- `config/models.yaml`: `RERANK_TIMEOUT_S`, `SOPILOT_LLM_TIMEOUT_S` and `SOPILOT_LLM_REWRITE_TIMEOUT_S` default to 300 s (rerank was 30 s).
- `conversations/factory.py`: the startup model check runs in a background task and is deduplicated per endpoint, so a Modal cold start no longer delays the first question.

## 4. Evidence (output seen by the orchestrator, 2026-11-24)
- `ruff check src tests`: clean.
- `pytest tests/unit` on this layer without the V2-48 toggle: 805 passed, 1 skipped, 15 xfailed (7 new in `tests/unit/test_pipeline_trace.py`).
- `pytest tests/integration/test_qa_api.py`: 26 passed, including `test_pipeline_trace_streams_steps_persists_and_enforces_access_isolation` (Docker).
- `./scripts/check-migrations.ps1`: passed (V005 is additive).

## 5. Not verified
- No owner review of the code or of section 3.
- `tests/tenant-isolation` (Docker) was not run and has no case for `rag.message_traces`; its isolation is covered only by the integration test above and the RLS policy in V005.
- The `merge_adjacent_sections=False` and prompt changes have no eval run: `cd eval; uv run pytest -q` passes, but no benchmark was re-run.
- TECH-V2-ai-service §7 and `http-conventions.md` do not describe the request field `includeTrace`, the `step` event or the trace route yet (only the table in `rag-schema.md` was added). Documented design and code disagree here; the code is the reference.

## 6. Results
Review-ready on the working tree, 2026-11-24. Docs updated: `docs/architecture/data/rag-schema.md` (table `message_traces`).
