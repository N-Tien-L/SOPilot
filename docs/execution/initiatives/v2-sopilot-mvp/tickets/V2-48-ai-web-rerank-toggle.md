---
id: V2-48
title: "ai-service + web: per-question reranker on/off toggle next to the chat input"
type: feature
status: done # todo | in_progress | review | done | blocked
created: 2026-11-24
updated: 2026-11-24
author: "Owner"
scope: web
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-35, V2-49, V2-50]
blocks: [V2-18]
blocked_reason: ""
branch: "feat/ai-rerank-toggle"
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/components/ai-service.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
---

# TICKET V2-48: Reranker toggle

> **Scope:** `web` (with a small ai-service change) | **Size:** `M` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `feat/ai-rerank-toggle`

## 1. Context & goal
Rerank is a server configuration (`rerank.enabled` in `config/models.yaml`), fixed when the service starts. For the acceptance demo and for reading the Pipeline Inspector, the owner wants to ask the same question with and without the reranker and see how the candidate order, the scores and the gate change, without restarting the service.

Owner decision 2026-11-24: a toggle next to the chat input. **D1** the choice is per question (request body), never stored as a setting. **D2** the toggle can only turn rerank **off** for a service that has it configured; it cannot load a reranker that is not configured. **D3** when the reranker is skipped, retrieval is the plain `hybrid` mode: same candidates and RRF, the `hybrid` gate threshold, no rerank call.

## 2. Acceptance criteria
- [ ] `POST /ai/v1/conversations/{id}/messages` accepts an optional boolean `rerank`. `false` skips the reranker for that question; `true` or absent keeps the configured behaviour. The reranker is never called when `false`, so no Modal request and no cold start.
- [ ] With `rerank: false` on a service that has a reranker: the SSE `meta` event, the `retrieve_rerank` trace phase (`skipped`, reason `rerank_off_by_request`), the stored `retrieval_mode` and the gate all say `hybrid`; the gate threshold is the `hybrid` one; the hit chunks follow the fusion order.
- [ ] `rerank: true` or absent on a service **without** a reranker behaves exactly as today (`hybrid`, no error).
- [ ] `GET /ai/v1/retrieval/options` (caller must be authenticated) returns `{"rerank": {"available": bool}}` from the configuration alone. It does not build the QA service, so it loads no model.
- [ ] Toggle "Rerank" next to the chat input, on when available; disabled with a short reason when the service has no reranker; the choice survives a page reload (local storage, per browser) and is sent with each question. The Pipeline Inspector shows which mode ran.
- [ ] The eval harness is unchanged and `cd eval; uv run pytest -q` stays green (the default path must rank exactly as before).
- [ ] Tests: ai-service unit for the retriever (skip, default, no reranker) and the endpoint; Vitest for the request body and the stored preference. No new dependency, no migration, no new env var.
- [ ] TECH-V2-ai-service (§7.2 request body, new options route), `docs/architecture/api/http-conventions.md`, `services/ai-service/README.md` updated; `./scripts/docs/check-docs.ps1` passes.
- [ ] Browser check with rerank configured: same question on and off shows different `mode`, rerank scores only when on; viewed at 1280 and 390 px.

## 3. Guide
- `Retriever.mode` is the gate mode of the service (`hybrid_rerank` when a reranker exists). Add a per-call mode and pass the flag from `post_message` through `QAService.answer` and `QAContext` to `RetrieveStep`; the `meta` event is emitted before retrieval, so it must use the per-call mode.
- `RetrievalStats.rerank_enabled` must mean "rerank ran for this question" (the trace labels depend on it).
- Availability: `ModelsConfig.load(app.state.models_config_path).rerank()` (`enabled` and `provider != "none"`). Do not call `get_qa_service`.
- Out of scope: enabling rerank on a service started without it, other retrieval knobs (mode, thresholds, `context_k`), a stored per-user preference on the server.

## 4. Testing
```powershell
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/validate-build.ps1 -Scope web
cd eval; uv run pytest -q
./scripts/docs/check-docs.ps1
```

## 5. Changed files
| Area | Action |
|---|---|
| `services/ai-service/src/sopilot_ai/retrieval/retriever.py`, `conversations/{service,steps,pipeline context}.py`, `api/conversations.py` (+ options route) and tests | MODIFY / CREATE |
| `frontend/web/lib/sse/stream.ts`, `lib/api`, `components/chat/ChatView.tsx` (+ toggle component) and tests | MODIFY / CREATE |
| TECH-V2-ai-service §7.2, `docs/architecture/api/http-conventions.md`, `services/ai-service/README.md` | MODIFY |

## 6. Results
Implemented on the working tree (not committed), 2026-11-24, branch `feat/ai-rerank-toggle`.

**ai-service.** `Retriever.retrieve(..., rerank=)` and `Retriever.mode_for(rerank)`; `MessageIn.rerank` (`false` only turns a configured reranker off for the question); `GET /ai/v1/retrieval/options` reads the configuration only (no service build). With the reranker off for the question the phase `retrieve_rerank` is `skipped` (`rerank_off_by_request`), the gate is the `hybrid` one and `RetrievalStats.rerank_enabled` is false. Review fixes: `rerank_enabled`/`rerank_model` now say "the reranker scored this pool" (an empty pool is not "reranked"); the `retrieve_rerank` phase always ends (`passed`, or `skipped` with `rerank_not_configured` when there is no reranker) and `retrieve_rerank` maps to its own Inspector stage instead of `post_checks`.

**Frontend.** `components/chat/RerankToggle.tsx` (+ `useRerankOptions`) beside the composer; `lib/chat/rerank-preference.ts` (localStorage key `sopilot.chat.rerank`); `buildAnswerBody` in `lib/sse/stream.ts`. The request carries `rerank:false` only when the toggle is off **and** the server reports a reranker (`effectiveRerank`).

**Evidence (output seen by the orchestrator).**
- ai-service: `ruff check src tests` clean; `run-tests.ps1 -Scope ai-service -Type unit` 831 passed, 1 skipped, 15 xfailed (26 in `tests/unit/test_rerank_toggle.py`).
- ai-service full suite incl. integration (Docker), run from `services/ai-service`: 1005 passed, 1 skipped, 15 xfailed.
- eval: `cd eval; uv run pytest -q` 200 passed (the PLAN ticket-count assertion 47 → 48 was updated).
- web: `validate-build.ps1 -Scope web` passed (build, lint, 255 Vitest).
- docs: `check-docs.ps1` passed.
- Review: fresh `v2-reviewer`, no blocker; 4 warnings (Inspector stage and phase never ended, empty pool counted as reranked, UI/request mismatch, missing evidence) fixed or recorded here.

**Not verified.** The browser check (AC9: same question on and off at 1280 and 390 px with a real reranker) and any real Modal rerank call; the tenant-isolation suite (no SQL or tenancy change). The skipped phase is a live event only: a stored trace shows `rerankEnabled: false` and mode `hybrid` on `retrieve_and_gate`, not the skipped phase. Retrying a turn from the UI re-sends with the toggle's current value, not the original one.

**Found on the way.** `MessageIn` also accepts `includeTrace` (from [V2-49](V2-49-ai-service-pipeline-trace.md), always sent by the frontend); TECH §7.2 and `http-conventions.md` do not list it yet. Not changed here.
