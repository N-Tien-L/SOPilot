---
id: V2-26
title: "Department-based document authorization tests (FR-29) in CI"
type: test
status: done
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-23, V2-24]
blocks: [V2-17]
branch: "test/tests-department-authorization"
assignee: pair
---

# TICKET V2-26: Department authorization tests

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under `.agent/context/` are as they were at the time.

## 1. Context & goal
PRD-V2 FR-29, ADR-007 §4.4–4.5. A second test layer, independent of workspace isolation (V2-14/FR-19): within **one workspace**, department-restricted documents never leak to people outside those departments.

## 2. Acceptance criteria
- [x] Test data: one workspace, departments A and B, members in A, in B, without a department, `SUSPENDED`, plus an OWNER and an ADMIN; documents `WORKSPACE`, `DEPARTMENTS[A]`, `DEPARTMENTS[A,B]`, each with its own title and secret string.
- [x] Every **read** cell of the ADR-007 §4.4 matrix is checked through each channel:
  - core-api: list, search, detail, download URL; out-of-access documents return `404`.
  - ai-service: dense, BM25, rerank, chunks expanded during context assembly, the context sent to the LLM (a mocked LLM records the prompt), citations, content view (`GET /ai/v1/documents/{id}/versions/{versionId}/content`), "closest documents" in the `NO_EVIDENCE` refusal, conversation history on reopening and the history sent to the question-rewrite step.
  - Caches: only `rag.embedding_cache` exists (keyed by chunk content hash, vectors only, ADR-007 §4.5); it is enough to confirm the table has no text column. There is no answer or retrieval-result cache yet, so no cell to check.
- [x] The matrix's write rows only check that MEMBERs are refused; department-based write rights belong to ADR-009/V2-36.
- [x] Change cases, each with an expected result:
  - Moving A → B: after refresh, the new token carries `wdept = B` and reads only B's documents; the old access token keeps the old rights until it expires (≤ 15 minutes, ADR-007 §5).
  - Suspension: no new token can be issued; suspension through the API revokes the refresh chain immediately, so refresh returns `401 UNAUTHENTICATED`; when the status changes without the chain being revoked, refresh returns `403 MEMBERSHIP_SUSPENDED` and revokes the chain; the access token held stays usable until it expires (≤ 15 minutes, ADR-007 §5). The test records this gap and does not treat it as a bug.
  - Archiving department A: documents keep `visibility` and `department_ids`; members still in A can still read (ADR-007 §4.3).
  - Deleting department A with documents: `409 DEPARTMENT_IN_USE`.
  - Narrowing a document from `WORKSPACE` to `DEPARTMENTS[A]`: once ai-service receives `ACCESS_UPDATED`, B members and people without a department no longer see the document on any channel.
  - Narrowing before ai-service **has received** the update: the old scope stays in effect in ai-service until the outbox delivers (ADR-007 §5). This is a known gap, not fail-closed; the test records the behaviour.
  - Fail-closed: a document without a `rag.document_access` row, deleted, or without an activated version is readable by nobody, including the OWNER.
- [x] No answer returns the name or content of an out-of-access document; the number of chunks in the context does not drop because of filtering after top-k (filtering happens before `LIMIT`).
- [x] A negative check: disabling the department condition in the filter must turn the suite red.
- [x] Runs in GitHub Actions together with FR-19 on every PR.

## 3. Guide
- Reuse V2-14's test framework; keep the FR-29 suite separate from FR-19 so a failure points to the broken layer.
- Two suites run independently like V2-14, without running both services together:
  - core-api: `services/core-api/src/test/java/com/sopilot/core/tenancy/` (pattern `TenantIsolationApiIT`), Testcontainers, simulated ai-service.
  - ai-service: `services/ai-service/tests/integration/` (pattern `test_qa_isolation.py`), real Postgres, mocked providers and LLM, tokens signed with a test key.
- The filter points to target: core-api TECH-V2-core-api §5.6; ai-service `sopilot_ai/retrieval/access_filter.py` (`allowed_cte`, `cited_access_cte`), TECH-V2-ai-service §7.5.
- Token lag and access-sync lag: ADR-007 §5, TECH-V2-document-access-sync §7.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Integration (core-api) | The core part of FR-29 on real Postgres, simulated ai-service | `./scripts/run-tests.ps1 -Scope core-api -Type all` |
| Integration (ai-service) | Retrieval, LLM context, citations, history, mocked LLM | `./scripts/run-tests.ps1 -Scope ai-service -Type integration` |
| CI | Both suites run in `tenant-isolation.yml` on every PR | GitHub Actions |

## 5. Implementation results
2026-11-10, branch `test/tests-department-authorization`. Only tests and one CI job were added; no product code changed. Both suites run independently like V2-14, with no harness running both services together.

**Files**
- `services/core-api/src/test/java/com/sopilot/core/tenancy/DepartmentAuthorizationIT.java`: 81 runs (parameterized by cell, so a failure points to the exact `actor x document` cell).
- `services/ai-service/tests/integration/test_department_authorization.py`: 60 runs.
- `.github/workflows/tenant-isolation.yml`: a new `department-authorization` job (running both suites); the FR-19 jobs unchanged.

**The read matrix.** Five people (OWNER, ADMIN, MEMBER in A, MEMBER in B, MEMBER without a department) × three documents (`WORKSPACE`, `DEPARTMENTS[A]`, `DEPARTMENTS[A,B]`), each with its own title and secret string. Out-of-access cells check that the title, secret, `documentId` and `versionId` are absent from the whole response, not just counts.
- core-api: detail, download URL, list, `?q=` search (title match), the result set exactly equal to the readable set; out of access always `404`. Write rows: a MEMBER gets `403` on PATCH, PUT `/visibility`, DELETE, retry and upload, even with a random id (existence not revealed), and the document is unchanged.
- ai-service: dense, BM25, hybrid, rerank (the reranker records every passage it receives), the context-assembly SQL (`load_chunks`, `load_sections`, `load_version_info`) and `BuildContextStep` with stale hits, the prompt sent to the LLM, the answer stream, citations, stored turns (`context_sources`, `message_citations`, `retrieval_results`), reopening conversations, `nearestDocuments` of `NO_EVIDENCE`, the content endpoint.
- Not applicable: `SUSPENDED` members in ai-service (ai-service only verifies the token; the gap is recorded in core-api).

**Change cases** (core-api: `DepartmentAuthorizationIT`; ai-service: `test_department_authorization.py`)
| Case | Observed result |
|---|---|
| Moving A → B | Before refresh the old token (`wdept = A`) still reads A-only documents (the gap; `exp - iat` ≤ 900 s is checked). After refresh `wdept = B`: A-only documents become `404`, `[A,B]` documents stay readable. |
| Suspension | Setting `SUSPENDED` directly in the DB: refresh returns `403 MEMBERSHIP_SUSPENDED`, the chain is revoked and unusable after unsuspension. Suspension through the API: the chain is revoked immediately, so refresh is `401` (see GAP 1). Both paths: the access token held still reads until it expires; issuing new tokens fails with `MEMBERSHIP_SUSPENDED`. |
| Archiving department A | Documents keep `visibility` and `department_ids`; A members read, B and people without a department still get `404`; no `ACCESS_UPDATED` is emitted. |
| Deleting a referenced department | `409 DEPARTMENT_IN_USE` (details `documents` / members), documents intact. |
| Narrowing `WORKSPACE` → `DEPARTMENTS[A]` | core-api: B and people without a department get `404` immediately on every channel; one `ACCESS_UPDATED` with `accessRevision = 2` and `departmentIds = [A]`. ai-service: after `PUT /internal/document-access` every channel is closed. |
| Narrowing, not yet received by ai-service | The old scope stays in effect on every channel until the update arrives (the known gap, not fail-closed); the test asserts this behaviour and then checks it closes after the `PUT`. |
| An old or equal revision | `applied: false` with revisions 2, 1, 0; access is not widened; revision 3 is applied (control). |
| Fail-closed | Missing `rag.document_access` row (chunks still present), inactive version, deleted: nobody reads on any channel, including the OWNER. |
| Reopened conversation / rewrite step | An answer built from a just-narrowed document is hidden `ACCESS_REVOKED`, without `content` or passages; the rewrite step does not receive that turn, only the still-readable ones. |

**Filtering before `LIMIT`.** The forbidden document has 40 sections, the open document 40, `candidate_pool = rerank_pool = context_k = 5`. Control: someone who can read both gets 5 chunks all from the forbidden document (they rank higher). Someone outside the department still gets 5 dense, 5 BM25 and 5 hybrid candidates, all from the open document.

**Caches.** Only `rag.embedding_cache` is used: key `(model, revision, content_sha256)`, no `workspace_id` column, the only text-typed columns are `model` and `revision`, and a row dump contains no secret string or title. No answer or retrieval cache. There is also `rag.suggestion_cache` (V2-25, not yet written by anyone); a test asserts the table is empty and turns red when V2-25 starts writing (GAP 2).

**Negative checks** (run locally, files restored, `git diff` of the files empty)
| Suite | Temporary change | Tests red |
|---|---|---|
| core-api | `DocumentRepository.VISIBLE`: `dd.department_id = ?::uuid` → `(… OR true)` | 8 / 81 |
| core-api | `VISIBLE`: the department branch always true (`?::uuid IS NOT NULL OR true OR EXISTS …`) | 18 / 81 |
| ai-service | `access_filter._READABLE`: the department condition → `OR true` | 27 / 60 |
| ai-service | `_READABLE`: the department branch removed | 23 / 60 |

**GAPs and design questions**
1. The suspension criterion said "refresh returns `403 MEMBERSHIP_SUSPENDED`". Through the API (`MemberService.java:116`) the refresh chain is revoked at suspension time, so refresh gets `401` (`RefreshTokenService.java:76`); `403` appears only when the status changes without the chain being revoked (`RefreshTokenService.java:89`; the `SessionWorkspaceIT` test does the same). Safer than the documents described. **Resolved 2026-11-10:** the owner accepted both codes and the documents were updated to match the source (TECH-V2-core-api §5.1 and the permission table, `services/core-api/README.md`, `.agent/context/authorization/v2-core-identity.md`); ADR-007 only says `SUSPENDED` blocks token issuance, so it is unchanged.
2. `rag.suggestion_cache` (V2-25) is keyed by `workspace_id` and `cache_key`, without `wdept`; its results come from document content. When V2-25 writes this table, decide who may see suggestions for department-restricted documents.
3. Two known gaps, asserted by tests rather than treated as bugs: an old token after a department change or suspension stays valid up to 15 minutes; ai-service keeps the old scope until it receives `ACCESS_UPDATED`.
4. core-api's `?q=` searches titles (`ILIKE`), not content; content search lives in ai-service.

**GitHub Actions:** the `department-authorization` job is green on PR #12 ([run](https://github.com/N-Tien-L/SOPilot/actions/runs/42851584792/job/129953412037)): `DepartmentAuthorizationIT` 81/81, `test_department_authorization.py` 60 passed; the FR-19 jobs (`database`, `negative-control`, `core-api`, `ai-service`) are green too.

**Not checked:** the negative checks are not automated in CI (as the FR-19 `negative-control` job does for RLS); core-api and ai-service have not run together.
