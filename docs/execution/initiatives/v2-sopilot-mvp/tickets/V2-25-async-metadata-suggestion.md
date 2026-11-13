---
id: V2-25
title: "ai-service: background metadata suggestions and latency measurement"
type: feat
status: review
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-21, V2-24]
blocks: [V2-33]
branch: "feat/ai-qa-async-metadata-suggestion"
assignee: pair
---

# TICKET V2-25: Background metadata suggestions

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
PRD-V2 FR-28 and the performance NFR. The old code called suggestions **synchronously inside the upload request** (`knowledge-service` `DocumentController` → ingestion `/metadata/suggest`, 30 s timeout), downloaded and re-parsed the file with `preview_extractor.py`, and called Groq `llama-3.3-70b-versatile` (shut down per CLAUDE.md) with `timeout=10`, `max_retries=2`.

## 2. Acceptance criteria
- [x] The suggestion job runs after extraction, not on the path to `READY`; upload returns immediately.
- [x] Reuses `extracted_documents` (the cleaned structure and canonical Markdown, V2-20/V2-21); never downloads or re-parses the file (test: the suggestion job runs even after the S3 object is deleted).
- [x] Rules first: title (first heading or file name), language, document code/issue number/effective date (V2-21).
- [x] One structured-output LLM call for the description, category (only from the workspace's existing categories, or empty with a proposed name) and tags (existing tags preferred). Input: title, heading outline, at most a few representative passages under a configurable token ceiling.
- [x] Configurable timeout, at most one retry; on a provider error store the rule results and mark `fallback`.
- [x] Cache by `(workspace_id, content sha256, prompt_version, model, category list hash)`; never shared between workspaces.
- [x] Suggestions stored separately; applied only to fields whose source is not `USER`; never change visibility or departments.
- [ ] Per-job measurements: `t_upload_ack`, `t_ready`, `t_suggest`, LLM latency, tokens in/out, `fallback`; report p50/p95 on the V2-19 corpus before setting targets.

## 2a. Evidence and known gaps (updated 2026-11-12)
- Done: unit and integration tests (ai-service), `DocumentSuggestionIT` (core-api) including tenant isolation, a version of another document refused without writing, a missing or wrong `X-Internal-Token` returning 401; a worker that loses its lease does not complete and does not re-emit the event.
- **Not measured:** `t_upload_ack`, `t_ready`, p50/p95 on the V2-19 corpus. No numbers yet to set targets.
- **Real run 2026-11-12 (one document, once):** Groq's `GET /models` returned 200 and listed `qwen/qwen3.8-27b`. Uploading `gitlab-meetings.md` through `dev-login`: ingest reached `READY` after about 50 s (embedding `embed_ms=52257`, 6 chunks), then `suggest_done method=LLM attempts=1 cache_hit=False llm_ms=2135`. The description and language were filled with source `SUGGESTED`. One sample, not p50/p95.
- **First measurements 2026-11-12** (`scripts/measure-ingest-latency.ps1`, 5 small Markdown documents loaded in sequence, no fallback): `t_upload_ack` p50 27 ms, p95 34 ms; `t_ready` p50 468 ms, p95 926 ms; `t_suggest` p50 454 ms, p95 940 ms (almost all `llm_ms`). **Not usable as targets:** n = 5 and `t_ready` is skewed by the embedding cache (the two GitLab documents had been embedded before, `embed_cached` = the chunk count; the three smoke documents have only 1 short chunk). Real CPU embedding: an uncached 5-chunk document takes `embed_ms` = 12,864 (the first one after the worker starts takes 52,257, including model loading).
- **Not measured:** p50/p95 on the V2-19 corpus with uncached content. Needs a large enough corpus (at least a few dozen documents) run on an empty cache, or `t_ready` reported with the embedding part separated.
- **Owner decisions 2026-11-12:**
  - Use Groq for suggestions (ADR-006 §4.4).
  - Suggestions run **in the same worker loop, after ingest** (no separate process): measured at about 2 s/job; at worst about 40 s (20 s timeout, one retry), which only delays the next ingest without breaking `READY`. A provider error gives an empty `RULES_FALLBACK` result. Split into a separate process only for bulk imports while Groq is degraded.
  - **A suggested title is not applied automatically**, only stored; the rule is in TECH-V2-core-api (the section on applying suggestions). There is no endpoint yet for users to accept a suggested title.
  - **The suggestion form (owner decision 2026-11-12):** one editable form, pre-filled from the document and `suggestions`, each field with a source label (`fieldSources`). An empty title = keep the file name (the UI drops `title` from the `PATCH`, because the backend refuses an empty title). Requiring description/category/tags is only a UI rule; category is required only when the workspace already has categories.
  - **`doc_code`, `revision_label`, `effective_date` are read-only** in the form, with a note "extracted automatically, may be wrong" (the extractor does not guarantee correctness). Editing them needs a version-level endpoint, later.
  - **A new category:** a "create suggested category" button at the end of the dropdown, OWNER/ADMIN only (`requireManager`): `POST /categories` then `PATCH categoryId`. Publishers only pick existing categories and see the suggested name as text. The one proposing a category name is the suggestion step (AI), not the publisher; meanwhile the category stays empty. A flow where publishers propose, admins approve and notifications go out is a separate ticket.
  - **Several documents suggesting the same idea under different names** (for example "Mua hàng", "Quy trình mua sắm"): the admin groups them by suggested name, enters **one** name (or picks an existing category) and applies it to the whole group. Needs an endpoint listing documents with an unapplied `proposedCategoryName` and a bulk category assignment endpoint (not yet; a separate ticket together with the approval flow).

- **Update 2026-11-13:** moved to `review` (code, migrations `core/V010`, `rag/V004` and tests committed). No code change in this round. The measurement criterion is still open: p50/p95 of `t_upload_ack`, `t_ready`, `t_suggest` on the V2-19 corpus with an empty embedding cache; no targets set. Bulk category assignment for proposal groups and the publisher-proposes/admin-approves flow are later separate tickets, not done here.

## 3. Guide
- Upgrade options (only if the measurements call for them): classifying the category by the nearest embedding instead of the LLM, or a smaller model. Record the choice and the measurements in the report.

## 4. Testing
| Kind | Content | Command |
|---|---|---|
| Unit | Title/language/document-code rules; the category-in-list constraint; `USER` fields not overwritten; fallback on timeout | `uv run pytest tests/unit` |
| Integration | Upload → `READY` without waiting for the LLM (slow mocked LLM); the cache never hits across workspaces | `uv run pytest tests/integration` |
