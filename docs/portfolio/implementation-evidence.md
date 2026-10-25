# SOPilot: implementation evidence and status

Part of the portfolio set: [README](../../README.md) → [engineering case study](engineering-case-study.md) → this document → source, tests and ADRs.

This is the canonical capability inventory. It records what the repository source supports, what tests and evaluation artifacts exist, and what is still open. It does **not** report test results, benchmark results or deployment status, because no code was run while writing it.

The repository is private. Links below are repository-relative and can be followed only by someone with access to the source.

## How to read this document

**Status vocabulary**

| Status | Meaning |
|---|---|
| Implemented | Source supports the described capability. Runtime correctness may still be unverified. |
| Partial | Some required behavior exists; the missing pieces are named. |
| Planned | A design or ticket exists; no implementation was found. |
| Unclear | Evidence is insufficient or contradictory. |

**Evidence labels used in the "Verification" column**

| Label | Meaning |
|---|---|
| Source inspected | I read the cited code during this task. |
| Tests present, not run | Test files exist. They were not executed, so no pass/fail claim is made. |
| Historical result | A repository document reports a result from an earlier run. It was not reproduced here. |
| Reproduced | Re-run during this task. **Nothing in this document carries this label.** |

Two scopes appear below. **V1** is the eight-service system (gateway, five Spring Boot services, two FastAPI services) that [AGENTS.md](../../AGENTS.md) marks as frozen. **V2** is the redesign described in [ADR-004](../02-architecture/adr/ADR-004-two-service-architecture.md); it is in progress and mostly not implemented.

## Capability inventory: V1 (frozen)

| Capability | Status | Source | Tests / artifacts | Verification | Gap or caveat |
|---|---|---|---|---|---|
| Document upload and versioning | Implemented | [`DocumentManagementService.upload`, `uploadNewVersion`](../../services/knowledge-service/src/main/java/com/poliwise/knowledge/service/DocumentManagementService.java); [`StorageService`](../../services/knowledge-service/src/main/java/com/poliwise/knowledge/service/StorageService.java) | [`DocumentManagementServiceTest`](../../services/knowledge-service/src/test/java/com/poliwise/knowledge/service/DocumentManagementServiceTest.java) | Source inspected. Tests present, not run. | The test class I read covers `checkDuplicate`; I saw no test of upload ordering. The object-storage write happens before the database commit and is not undone if the transaction rolls back (see [case study](engineering-case-study.md#1-upload-to-searchable-chunks-consistency-at-the-boundaries)). |
| Event publication after upload | Partial | [`DocumentEventPublisher`](../../services/knowledge-service/src/main/java/com/poliwise/knowledge/event/DocumentEventPublisher.java) | None found | Source inspected. | Publish failures are logged and swallowed. No outbox or retry was found. In `upload()` the publish call sits inside the `@Transactional` method, so it can fire before the commit. |
| Synchronous confirm-and-ingest | Implemented | `confirmMetadataSync`, `triggerAndPollIngestion`, `pollIngestionResult` in `DocumentManagementService` | None found | Source inspected. | Polls the ingestion job every 2 s for up to 60 s. Deliberately not `@Transactional` (comment in code). If the message is lost, the job row stays `UPLOADED` and the poll times out. |
| Ingestion consumer and pipeline | Implemented | [`consumer.py`](../../services/ingestion-service/src/events/consumer.py); [`pipeline.py`](../../services/ingestion-service/src/services/pipeline.py) | [`test_deduplication.py`](../../services/ingestion-service/tests/ingestion_tests/test_deduplication.py), [`test_ingestion_flow.py`](../../services/ingestion-service/tests/ingestion_tests/test_ingestion_flow.py) | Source inspected. Tests present, not run. | `pipeline.process` catches every exception and returns `FAILED`, so the consumer acknowledges the message even on failure; the dead-letter queue argument is configured but is not reached by pipeline failures. The bucket allow-list (`poliwise-documents`, `docs`) disagrees with the compose bucket name (recorded in [CLAUDE.md](../../CLAUDE.md) as known drift). |
| Three-layer duplicate detection | Implemented | [`deduplicator.py`](../../services/ingestion-service/src/services/deduplicator.py): file SHA-256, extracted-text hash, semantic fingerprint | `test_deduplication.py` (covers all three layers and the pipeline outcomes) | Source inspected. Tests present, not run. | The semantic layer fingerprints weighted text samples (the code comments mention a "middle 4000 chars" sample), not the whole document; one test name (`test_fingerprint_uses_only_first_4000_chars`) may no longer match that logic. Thresholds are in code and tests; none were tuned against a labelled set that I found. |
| Chunking and embedding | Implemented | [`chunker.py`](../../services/ingestion-service/src/services/chunker.py) (`ParentChildChunker`), [`embedding_service.py`](../../services/ingestion-service/src/services/embedding_service.py) | None specific found | Source inspected. | `pipeline.py` writes `embedding_model = "BGE_M3"` for every chunk regardless of configured model (drift noted in CLAUDE.md). No chunk-quality evaluation exists for this V1 chunker. |
| Atomic chunk swap in the index | Implemented | `mark_not_latest`, `bulk_insert` and `update_status("READY")` share one session and one `commit()` in `pipeline.py` | None found | Source inspected. | Atomic within PostgreSQL only. The job-completion update and the earlier `update_progress` calls are separate writes. |
| Hybrid retrieval (dense + lexical, rank fusion) | Partial | [`hybrid_search.py`](../../services/ai-qa-service/src/services/retrieval/hybrid_search.py); [`chunk_repo.py`](../../services/ai-qa-service/src/db/repositories/chunk_repo.py) | [`test_retrieval.py`](../../services/ai-qa-service/tests/unit/test_retrieval.py) (one RRF test with a loose assertion) | Source inspected. Tests present, not run. | The lexical side is PostgreSQL `ts_rank` over a `simple` `tsvector`, not BM25. Fusion weights are fixed (0.7 / 0.3, k = 60). The 0.15 threshold is applied to each chunk's original score (cosine similarity or max-normalised `ts_rank`), not to the fused score, so it mixes scales (also recorded in CLAUDE.md). |
| Reranking | Partial | [`reranker.py`](../../services/ai-qa-service/src/services/retrieval/reranker.py); branch in [`pipeline_orchestrator.py`](../../services/ai-qa-service/src/services/pipeline/pipeline_orchestrator.py) | None found | Source inspected. | Not on the active path: [`chat.py`](../../services/ai-qa-service/src/api/routes/chat.py) builds `PipelineOrchestrator()` without a `reranker_service`, so `USE_RERANKER` has no effect. |
| Permission-aware retrieval | Implemented | Access predicate in both queries of `chunk_repo.py`; JWT verification in [`dependencies/__init__.py`](../../services/ai-qa-service/src/api/dependencies/__init__.py) | None found for the SQL predicate | Source inspected. | Filter uses `access_level`, `allowed_roles`, `allowed_departments`, `allowed_users` stored on each chunk plus `status = 'PUBLISHED'` and expiry. Those columns are written at ingestion; I found no code that updates them on existing chunks when a document's visibility changes. Not traced through metadata-service. No authorization test found. |
| Document and category filters on chat | Partial | `RetrievalFilters` in `chunk_repo.py`; construction in `pipeline_orchestrator.py` | None found | Source inspected. | The orchestrator builds filters only if the request has a `context` attribute; `ChatRequest` in `chat.py` defines none, so these filters appear unreachable from the HTTP API. |
| Multi-stage query pipeline (toxic filter, intent, query refinement, gap detection) | Partial | [`pipeline_orchestrator.py`](../../services/ai-qa-service/src/services/pipeline/pipeline_orchestrator.py), `layer1_toxic_filter.py`, `layer2_intent_classifier.py`, `query_refiner.py`, `knowledge_gap.py` | Ad-hoc scripts at `services/ai-qa-service/test_*.py`; [`test_pipeline_e2e.py`](../../services/ai-qa-service/tests/integration/test_pipeline_e2e.py) | Source inspected. Tests present, not run. | The answer path imports `build_sources` from `src.api.routes.chat`; I found no definition of that name anywhere under `services/ai-qa-service/src`. If that line is reached, it would fail at runtime. Not executed to confirm. Retired Groq model IDs are also recorded in CLAUDE.md. |
| Gateway authentication and role guards | Implemented | [`proxy.controller.ts`](../../services/api-gateway/src/proxy/proxy.controller.ts), `common/guards` | [`proxy.controller.spec.ts`](../../services/api-gateway/src/proxy/proxy.controller.spec.ts), [`jwt-auth.service.spec.ts`](../../services/api-gateway/src/auth/services/jwt-auth.service.spec.ts) | Source inspected (controller guards). Tests present, not run. | Roles are coarse (`USER`, `MANAGER`, `ADMIN`). Document-level visibility is not decided here. Known mismatch: gateway exposes `PUT users/roster/:id` that user-service does not implement (CLAUDE.md). |
| Google sign-in and roster admission | Unclear | `auth-service` (`GoogleTokenVerifierService`, controllers) and `user-service` roster classes | [`GoogleAdmissionTest`](../../services/auth-service/src/test/java/com/poliwise/auth/service/GoogleAdmissionTest.java), [`GoogleRosterAdmissionTest`](../../services/user-service/src/test/java/com/poliwise/user/service/GoogleRosterAdmissionTest.java) | Listing level only. Tests present, not run. | I did not read these implementations. Design: [ADR-003](../02-architecture/adr/ADR-003-google-identity-and-roster-admission.md), now `superseded`. Historical: [AUDIT-google-admission](../04-reports/AUDIT-google-admission-2026-10-15.md). |
| Web frontend | Unclear | `frontend/web/app/*` (admin, documents, analytics, sessions, login) | None (build and lint only, per AGENTS.md) | Directory listing only. | Not inspected, not run in a browser. No screenshots exist in this package. |
| Feedback and unanswered-question loop | Unclear | Publish side in `knowledge_gap.py`; `feedback-service` | `feedback-service` tests concern report export | Publish side inspected. | Consumer side and admin screen were not traced end to end. |

## Capability inventory: V2 (in progress)

| Capability | Status | Source | Tests / artifacts | Verification | Gap or caveat |
|---|---|---|---|---|---|
| `core-api` and `ai-service` services | Planned | Design only: [ADR-004](../02-architecture/adr/ADR-004-two-service-architecture.md), [TECH-V2-core-api](../02-architecture/designs/TECH-V2-core-api.md), [TECH-V2-ai-service](../02-architecture/designs/TECH-V2-ai-service.md) | None | `services/` listing: neither `core-api` nor `ai-service` exists. | The V2 tickets that create them ([V2-09](../03-plans/tickets/V2-09-ai-service-ingest-retrieval.md), [V2-11](../03-plans/tickets/V2-11-core-api-identity-workspace.md), [V2-20](../03-plans/tickets/V2-20-structured-extraction.md)) are not complete according to [PLAN-V2](../03-plans/PLAN-V2-sopilot-mvp.md). |
| Database-backed outbox, `SKIP LOCKED` worker, RLS tenant isolation | Planned | TECH-V2 documents only | None | Searched migrations: only schema/role bootstrap exists. | No tables are created yet; the `rag` and `core` bootstrap files say tables arrive in later migrations. |
| Local V2 infrastructure (PostgreSQL + pgvector, Flyway, MinIO, least-privilege roles) | Partial | [`docker-compose.v2.yml`](../../docker-compose.v2.yml), [`infrastructure/db/`](../../infrastructure/db/README.md), [`core/V001`](../../infrastructure/db/migrations/core/V001__core_bootstrap.sql) | [Acceptance audit](../04-reports/AUDIT-v2-05-v2-08-acceptance-2026-10-25.md) | Source inspected. Historical result: audit reports a temporary-volume run in which both migration chains, role isolation and storage policies passed. Not reproduced. | The audit states startup stability across repeated runs and CI were not checked. Schema bootstrap and helper functions only; no application tables. |
| Retrieval evaluation harness | Implemented | [`eval/sopilot_eval/`](../../eval/README.md): `retrievers.py` (dense, in-memory BM25, hybrid RRF, optional cross-encoder), `metrics.py`, `run.py` | [`eval/tests/`](../../eval/tests/test_eval.py) | Source inspected. Tests present, not run. Historical result: acceptance audit reports 18 and 26 passing tests on 2026-10-25. | Scope in the next section. Part of the harness (dataset, acquisition, extraction, pilot preparation) is untracked in the working tree at the time of writing. |
| Evaluation datasets | Partial | `eval/datasets/` (smoke fixtures, pilot tooling); `datasets/` | [`eval/README.md`](../../eval/README.md) | Documentation read only. Corpus and question files were not opened. | The repository documents describe the pilot sets as draft; no approved gold set or official result exists ([V2-06](../03-plans/tickets/V2-06-multilingual-eval-dataset.md) is `in-progress`). |
| Production use of the evaluated retrieval (real BM25, structure-aware chunks) | Planned | TECH-V2-ai-service §5–§6 | None | The evaluated BM25 lives only in `eval/`; V1 uses `ts_rank`. | Config `chunking.mode: docproc` is documented to fail until [V2-22](../03-plans/tickets/V2-22-structure-aware-chunking.md)/V2-07 land. |
| PDF extraction with Docling | Planned | [ADR-008](../02-architecture/adr/ADR-008-pdf-extraction-docling.md) | None | ADR read. | The ADR and PLAN state there is no measurement yet. V1 uses PyMuPDF with Tesseract (`extractors/pdf.py`). |
| Semantic router, member profiles, metadata suggestion, workspace sessions | Planned | Tickets [V2-23](../03-plans/tickets/V2-23-core-api-member-profiles-departments.md) to [V2-27](../03-plans/tickets/V2-27-semantic-router.md), [V2-29](../03-plans/tickets/V2-29-core-api-workspace-sessions.md) | None | Ticket text only. | Not started in code as far as the repository shows. |

## Evaluation scope

The only evaluation code is the V2 harness in `eval/`. It measures **retrieval over an in-memory index**, not the V1 or V2 application.

| Property | Value |
|---|---|
| What is scored | Ranking of chunks against expected documents or pages: recall@k, MRR, nDCG@10, plus a refusal-threshold sweep on top-1 score. |
| What is not scored | Generated answers, citation faithfulness, end-to-end latency, the PostgreSQL query path, permission filtering. |
| Retrievers | Dense (embedder choice per config), BM25 (own implementation with Vietnamese unigram + bigram tokens), hybrid RRF. Optional cross-encoder rerank. |
| Relevance label | Document or page match, tagged `document_page_proxy` in each run's `run.json`; not span-level gold. |
| Chunking | Fixed-size character splitter, tagged `character_exploratory_only`. The shared structure-aware chunker is not implemented. |
| Refusal sweep | A retrieval-level proxy for "should the system decline". Answer-level refusal needs the LLM layer, which the harness does not run. |
| Datasets | Synthetic smoke fixture (3 chunks) used only to exercise the harness; real pilot sets are draft. This document does not describe their contents. |
| Result files | Two runs under `eval/results/`, both on the smoke dataset (one with the offline hash embedder, one recorded with a sentence-transformers provider). `eval/README.md` says never to report smoke numbers; they are not quoted here. |

Interpretation limits: the harness README itself marks the hash-embedder and smoke numbers as harness validation only; no official RQ result exists; the acceptance audit approves the tooling and explicitly not the research results ([audit scope](../04-reports/AUDIT-v2-05-v2-08-acceptance-2026-10-25.md)).

## What was and was not done for this document

- Done: read source, tests, configs, ADRs, plans and audits listed above; compared claims across them.
- Not done: running tests, builds, services, migrations or evaluation; opening `.env`, datasets or results beyond headers; calling external APIs.
- Ticket counts in PLAN-V2 (33 tickets, 5 done, 6 implemented, 1 in review at the time of reading) are not used here as a completion measure.
