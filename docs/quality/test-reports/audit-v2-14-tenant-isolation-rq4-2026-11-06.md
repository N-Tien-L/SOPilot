---
id: AUDIT-v2-14-tenant-isolation-rq4-2026-11-06
title: "V2-14: tenant isolation in CI and RQ4 (RLS latency)"
status: final
created: 2026-11-06
updated: 2026-11-13
author: "Owner"
type: audit
scope: tests
verdict: PASSED_WITH_WARNINGS
milestone: "V2: SOPilot MVP"
---

> Translated from Vietnamese on 2026-11-13; content unchanged.

# V2-14: tenant isolation (FR-19) and RQ4

## 1. Tenant isolation

Three layers, all run locally on real Postgres with the real application roles (`sopilot_core_app`, `sopilot_ai_app`, `NOBYPASSRLS`):

| Layer | Where | Result |
|---|---|---|
| Database, every tenant table of `core` and `rag` (discovered from the catalog) | `tests/tenant-isolation/` | 31 tests green |
| core-api API, 3 workspaces with secret strings in documents, departments, members, audit | `TenantIsolationApiIT` | 8 tests green |
| ai-service retrieval (access filtering before `LIMIT`, document deletion) | `test_retrieval.py` | 12 tests green (a first run failed at `test_hybrid_candidates_always_have_dense_score`, three reruns were all green; an existing test, not part of this change, not investigated) |

Found while writing tests: `rag.processed_requests` is a table without `workspace_id` outside the list of global tables. This is the exception recorded in TECH-V2-ai-service §3.5 (it holds only idempotency UUIDs); it was added to `GLOBAL_TABLES` with the reason. From now on a new table without `workspace_id` turns the test red until approved.

### Checking that the tests detect leaks

- `ISOLATION_MUTATION=disable-rls` (RLS disabled on every tenant table): 23 tests fail, 8 green. CI requires this run to be red.
- A manual mutation in the API (2026-11-06): removing `d.workspace_id = ?` from the document list query and disabling RLS on `documents`, `document_versions` → `TenantIsolationApiIT` fails 2 tests with "workspace A leaked a secret of B". The code was restored.
- The `test_detector_*` tests create a table without RLS: the detector reports a leak; with RLS enabled it is silent.

### Not covered

- Q&A, conversations, feedback through the API: the endpoints do not exist yet. Made criteria of V2-10 (Q&A, conversations) and V2-13 (feedback). The tables `rag.conversations`, `messages`, `message_feedback`, `message_citations` are covered at the database layer.
- ~~The workflow has no green run on GitHub yet~~: 4/4 jobs green on PR #5 (2026-11-07) and on `develop` (2026-11-08).

## 2. RQ4: the cost of RLS on the retrieval path

`eval/rq4_rls_latency.py`. Same data, same queries, two interleaved connections (order swapped on each query), 30 warm-up queries discarded. The unit measured is one retrieval transaction: ai-service's `search.dense` then `search.bm25` (the real functions), `pool=50`.

- `app-filter`: a superuser connection (bypassing RLS), with only the application's `workspace_id` + read-access filter.
- `app+rls`: a `sopilot_ai_app` connection, the same SQL, plus the RLS policies on every table touched.

Synthetic data: random 1024-dimension unit vectors, a 3,000-word Zipf vocabulary, 5 workspaces, `pgvector/pgvector:0.8.0-pg16` in Docker Desktop. Measures the database path, **not** retrieval quality.

| Scale | Stage | app-filter p50 / p95 (ms) | app+RLS p50 / p95 (ms) | p50 difference | p95 difference |
|---|---|---:|---:|---:|---:|
| 10,000 chunks (5 x 2,000) | dense | 13.36 / 15.75 | 13.13 / 15.77 | -1.7% | +0.1% |
| | bm25 | 28.17 / 50.66 | 28.86 / 50.63 | +2.5% | -0.1% |
| | total | 44.21 / 66.46 | 45.12 / 65.89 | +2.1% | -0.9% |
| 30,000 chunks (5 x 6,000) | dense | 34.90 / 41.54 | 34.30 / 41.78 | -1.7% | +0.6% |
| | bm25 | 129.75 / 271.21 | 132.49 / 265.33 | +2.1% | -2.2% |
| | total | 168.13 / 308.08 | 169.00 / 296.20 | +0.5% | -3.9% |

The top-10 of the two modes is identical for 300/300 queries at each scale; a workspace without data gets 0 rows.

**Conclusion:** RLS adds about +0.5% to +2% at p50 and is indistinguishable from noise at p95 (negative signs appear in both directions), at both scales. With this data, RLS is not a reason to drop the second protection layer.

**Limits:** synthetic data; one machine, one run per scale (BM25's p95 and p99 have long tails, the difference is below the noise); `retrieval` has no reranker and no LLM yet; absolute numbers depend on the machine, only the two modes are compared. Not measured beyond 30,000 chunks. A first 30,000-chunk run was cancelled because two overlapping runs disturbed the measurement; the numbers above are from the later run, run alone.

Rerun: `cd eval && uv run python rq4_rls_latency.py --workspaces 5 --chunks 6000 --queries 300`. Machine-readable results are in `eval/results/rq4-*/` (this directory is gitignored).

## 3. Acceptance (2026-11-09)

Owner acceptance, V2-14 moved to `done`, verdict `PASSED_WITH_WARNINGS`. Rechecked: `tests/tenant-isolation` 31 green, `ISOLATION_MUTATION=disable-rls` 23 fail / 8 green; `./mvnw -B verify` in core-api 73 unit + 78 integration green (`TenantIsolationApiIT` 8, `TenantIsolationIT` 9). Remaining warnings: (1) isolation through the Q&A/conversation/feedback API waits for V2-10/V2-13; (2) RQ4 only on synthetic data ≤ 30,000 chunks; (3) some write statements of `DocumentRepository` filter only by `id` after locking the row by `workspace_id`; not a leak, but the repeated application filter layer is missing; moved to a V2-24 criterion.
