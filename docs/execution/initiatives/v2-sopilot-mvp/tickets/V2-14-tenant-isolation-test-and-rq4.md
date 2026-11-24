---
id: V2-14
title: "FR-19 tenant isolation tests in CI and RQ4"
type: test
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-12]
blocks: [V2-17, V2-18]
branch: "test/tests-tenant-isolation"
assignee: pair
---

# TICKET V2-14: Tenant isolation and RQ4

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
The biggest risk of the old system (A1, A2). Automated evidence of zero leaks is needed.

## 2. Acceptance criteria
- [x] Tests create ≥ 3 workspaces, each with documents containing its own "secret string"; prove that no question, document API, conversation, feedback or audit returns another workspace's data. (The document, member, department and audit APIs and the conversation/feedback tables at DB level are covered; Q&A and conversations through the API moved to V2-10, feedback through the API to V2-13, all running in `tenant-isolation.yml`)
- [x] Tests that a missing/fake `workspace_id` in the token and direct DB queries with the application role are blocked by RLS.
- [x] A GitHub Actions workflow runs these tests on every PR. (A green run of all 4 jobs on PR #5, 2026-11-07; department authorization within a workspace is a separate suite in V2-26)
- [x] RQ4: measure retrieval latency with application filtering versus application + RLS on the same data, recording p50/p95 in the report.

## 3. Guide
- **Files:** `tests/tenant-isolation/` (CREATE), `.github/workflows/tenant-isolation.yml`, `eval/` extended for RQ4.

## 4. Testing
This ticket is itself the test. Evidence: a green CI log and one run with the filter deliberately removed to confirm the tests **fail** on a leak (proving the tests are not vacuous).

## 5. Implementation evidence (2026-11-06, accepted 2026-11-09)

The owner accepted on 2026-11-09 and set `done`; [AUDIT-v2-14](../../../../quality/test-reports/audit-v2-14-tenant-isolation-rq4-2026-11-06.md) became `final`. Isolation through the Q&A/conversation/feedback APIs is a criterion of V2-10 and V2-13, because those APIs did not exist yet. Recheck at acceptance: `cd tests/tenant-isolation && uv run pytest -q` → 31 green; `ISOLATION_MUTATION=disable-rls uv run pytest -q` → 23 fail, 8 green (as recorded); `TenantIsolationApiIT` 8 and `TenantIsolationIT` 9 green in `./mvnw -B verify`; the `Tenant isolation (FR-19)` workflow green on PR #5 and on `develop` (run 42506269294, 2026-11-08).

Details and measurements: [AUDIT-v2-14](../../../../quality/test-reports/audit-v2-14-tenant-isolation-rq4-2026-11-06.md).

- **Code:** `tests/tenant-isolation/` (`isolation.py`, `conftest.py`, `test_db_isolation.py`, README), `services/core-api/src/test/java/com/sopilot/core/tenancy/TenantIsolationApiIT.java`, `.github/workflows/tenant-isolation.yml` (4 jobs: database, negative-control, core-api, ai-service), `eval/rq4_rls_latency.py`.
- **Commands and results:** `cd tests/tenant-isolation && uv run pytest` → 31 green; `ISOLATION_MUTATION=disable-rls uv run pytest` → 23 fail (as required: "with the filter deliberately removed the tests must fail"); `./mvnw verify -Dit.test=TenantIsolationApiIT` → 8 green; a manual mutation removing the `workspace_id` filter + disabling RLS → tests fail, then the code was restored; `uv run pytest tests/integration/test_retrieval.py` (ai-service) → 12 green (one failure first, then three green runs).
- **RQ4:** RLS adds +0.5% to +2% at p50, with p95 indistinguishable from noise, at 10,000 and 30,000 synthetic chunks; the top-10 is identical for 600/600 queries.
- **CI (2026-11-07):** [PR #5](https://github.com/N-Tien-L/SOPilot/pull/5), jobs `database`, `negative-control`, `core-api`, `ai-service` all green. The first run's `ai-service` job was red because `test_hybrid_candidates_always_have_dense_score` (V2-09) was flaky: `candidate_pool=1` with equal RRF weights made two candidates tie, and the tie order depended on random UUIDs. The test was fixed with `rrf_weights=(2.0, 1.0)` (commit `262d7fc`); production code unchanged. The old failure was not reproduced outside CI, so the cause rests on reading the code (`fusion.order`, `tie_key=str`), not on a run.
- **Not checked:** Q&A/conversations/feedback through the API; RQ4 on real data and at scales above 30,000 chunks.
