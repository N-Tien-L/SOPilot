---
id: PRD-V2-SOPILOT-MVP
title: "SOPilot V2 MVP: multi-tenant document Q&A workspace with citations"
status: approved
created: 2026-10-16
updated: 2026-11-13
author: "Owner"
milestone: "V2: SOPilot MVP"
priority: P0
refs:
  - docs/research/audit-markdown-normalization-and-preview-2026-10-21.md
  - docs/archive/04-reports/AUDIT-project-progress-2026-10-14.md
  - docs/archive/04-reports/AUDIT-google-admission-2026-10-15.md
  - docs/research/audit-v2-baseline-analysis-2026-10-17.md
  - docs/research/audit-ingestion-sop-data-2026-10-19.md
  - docs/architecture/decisions/adr-007-departments-member-profiles-document-access.md
  - docs/architecture/decisions/adr-009-department-publishers.md
---

# Product requirements (PRD)

> **Document id:** `PRD-V2-SOPILOT-MVP` | **Milestone:** `V2: SOPilot MVP` | **Status:** `approved` (owner approval 2026-10-20, V2-01)
>
> On approval this PRD replaced `PRD-M1-jit-onboarding.md` (single organization + roster model). Architecture: [ADR-004](../architecture/decisions/adr-004-two-service-architecture.md). Tenancy and sign-in: [ADR-005](../architecture/decisions/adr-005-workspace-tenancy-and-google-jit.md). Member profiles, departments and document access: [ADR-007](../architecture/decisions/adr-007-departments-member-profiles-document-access.md).
>
> Translated from Vietnamese on 2026-11-13 without changing requirements. FR/UC ids, section numbers and the numbering of the §8 list are stable (code cites §8.8 and §8.10).

---

## 1. Problem Statement & Motivation

### Context and current pain points
- SOPilot is a copy of Poliwise, a system built for **one fixed organization**: an HR-loaded roster, global departments, permissions by department. Schema, JWT and specs have no notion of an organization (tenant). With a second organization, RAG retrieval filters only by role/department, so documents can leak across organizations.
- The new target users are varied: individual users, small teams/startups, large companies. The roster model rejects with 403 everyone not loaded by HR, so it cannot serve the first two groups.
- The system carries many enterprise-operations features (OnlyOffice, version comparison, analytics, export, session management, OTP...) while the core value, **trustworthy Q&A with citations**, has never been measured.
- 8 services + RabbitMQ + Redis + MinIO cannot be hosted for free and exceed what one person can maintain.

### Expected outcomes
1. A complete MVP that really runs, with a target operating cost of **0 USD/month**, good enough for a CV (AI Engineer and Software Engineer) and for the university research submission.
2. Core value: **multilingual** Q&A (at least Vietnamese and English, including asking in one language about documents in another) over the workspace's documents, with answers cited to page/passage, refusing when evidence is missing, and never leaking documents between workspaces.
3. Quality is **measured with numbers** (eval set + ablation), not just demonstrated.

---

## 2. User Personas & Use Cases

| Persona | Role | Main goal |
|---|---|---|
| **Solo user** | An individual with a Gmail account | Upload their own documents and ask questions right away, without anyone's approval |
| **Workspace Owner / Admin** | Team founder, team lead, company IT | Create a workspace, invite members, manage documents, see unanswered questions |
| **Member** | Team member / employee | Ask questions over the workspace's shared documents, check cited sources |
| **Evaluator** | The project author, the research assessor | Run the evaluation, compare retrieval configurations, reproduce results |

Workspace roles: `OWNER`, `ADMIN`, `MEMBER`. There is no longer a system-wide role `USER/MANAGER/ADMIN`. Departments stay flat, belong to a workspace, and are used to limit read access to documents (ADR-007); a department is not a role.

### Use Case Scenarios
1. **UC-01: First sign-in (solo)**
   - **Actor:** Solo user. **Precondition:** a Google account with a verified email.
   - **Main flow:** click "Sign in with Google" → the backend verifies the ID token → creates the user by `(issuer, sub)` → creates a personal workspace with role `OWNER` → opens the chat page.
   - **Postcondition:** the user has exactly one personal workspace; signing in again does not create another.
2. **UC-02: Invite a member**
   - **Actor:** Owner/Admin. **Main flow:** enter email + role → the system creates a single-use invitation link valid for 7 days → the invitee signs in with Google using that exact email → becomes a member.
   - **Exception:** the Google email does not match the invitation → rejected; the invitation stays valid.
3. **UC-03: Self-join by domain (P1)**
   - **Actor:** an Owner using a Google Workspace account (claim `hd = acme.com`). **Main flow:** the owner enables "anyone @acme.com may join" → employees who sign in with `hd = acme.com` see the workspace and join with role `MEMBER`.
4. **UC-04: Upload documents and ask**
   - **Actor:** Owner/Admin uploads; Member asks. **Main flow:** upload a PDF → status "Processing" (`UPLOADED`/`PROCESSING`) → `READY` → (optional) open "Nội dung hệ thống nhận diện" (the recognized-content view) to compare with the original PDF (FR-31) → the member asks → the answer streams with citations `[1]`, `[2]` → clicking a citation opens the document at the right page with the source passage highlighted.
5. **UC-05: A question not covered by the documents**
   - **Main flow:** retrieval scores are below the threshold → the system answers "not found in this workspace's documents" instead of guessing → the question goes to the "unanswered" list for Admins.
6. **UC-06: Run an evaluation**
   - **Actor:** Evaluator. **Main flow:** run the eval command with a gold question set and a list of configurations → receive a metrics report per configuration.
7. **UC-07: Invite staff with a profile**
   - **Actor:** Owner/Admin. **Main flow:** enter email, role, full name, department and (optionally) employee id and job title → the invitation is pending → the invitee signs in with Google using that email → an `ACTIVE` membership carries the entered profile. No staff record has to exist before the invitation.
8. **UC-08: Assign and move departments**
   - **Actor:** Owner/Admin. **Main flow:** pick a member → change department → from the next token issuance (≤ 15 minutes) the member reads only the new department's documents plus workspace-wide documents.
9. **UC-09: Upload and metadata suggestions**
   - **Actor:** Owner/Admin. **Main flow:** upload a file, choose visibility (default: whole workspace) → the document is processed to `READY` without waiting for suggestions → suggested title, description, category, tags and language appear when the background job finishes → the manager accepts or edits them. Suggestions never change visibility.
10. **UC-10: Ask about a department-restricted document**
   - **Actor:** Member. **Main flow:** ask a question whose answer is only in a document restricted to another department → the system answers that no evidence was found, without revealing that document's name or content. When the member is in the right department → the answer comes with citations.
11. **UC-11: Revoke access**
   - **Actor:** Owner/Admin. **Main flow:** suspending a member or moving their department → blocked at the latest when the access token expires (≤ 15 minutes). Narrowing a document's visibility → blocked as soon as ai-service receives the update (synchronous call, outbox retries). Conversation history hides passages and answers based on documents the user can no longer read.
12. **UC-12: Initial corpus load and checking extraction results**
   - **Actor:** Owner/Admin. **Precondition:** the files chosen are versions that may be used (SOPilot has no approval workflow).
   - **Main flow:** select up to 10 PDF/MD files per batch → each file shows "Uploading" then "Processing" → the user may close the dialog and do other work → the document list reports each file as `READY` or failed with a reason → for `READY` files the manager may open "Nội dung hệ thống nhận diện" (FR-31) → next batch.
   - **Exceptions:** a duplicate, scanned, wrongly formatted or over-quota file fails only itself; a failed file is retried or replaced without reloading files that succeeded. If the recognized content is wrong → replace or delete the file; Markdown is not edited inside the system.

---

## 3. Functional Requirements (FR)

### Identity and workspaces
- [ ] **FR-01: Google-only sign-in.** Verify the ID token (RS256 signature via JWKS, `iss`, `aud`, `exp`, `email_verified`). Identity is `(issuer, sub)`; email is only an attribute. The user is created just-in-time on first sign-in. No registration, password or OTP. A dev login (no Google) is enabled only in the `local`/`test` profiles.
- [ ] **FR-02: Automatic personal workspace.** The first sign-in creates a personal workspace, idempotently.
- [ ] **FR-03: Workspace management.** Create, rename, delete (`OWNER` only), list my workspaces, switch the active workspace.
- [ ] **FR-04: Members and invitations.** An invitation carries an initial profile (full name, department, optional employee id and job title) applied on acceptance. Owner/Admin invite by email + role; single-use link, valid 7 days, revocable. Change role, remove a member, leave a workspace. A workspace always keeps at least one `OWNER`. An Admin cannot promote anyone to `OWNER` or remove an `OWNER`.
- [ ] **FR-05 (P1): Join by domain.** Only an owner with an `hd` claim can enable it, and only for a domain equal to their own `hd`. People with a matching `hd` join with role `MEMBER`.

- [ ] **FR-22: Member profiles.** The sign-in account is global; the profile lives on the membership in each workspace: display name, email, employee id (optional, unique within the workspace when present), job title (optional), department (at most one), status `ACTIVE | SUSPENDED`. An unaccepted invitation is a pending state. Lifecycle: invited → `ACTIVE` → `SUSPENDED` (access blocked, data kept, can be reopened), or left/removed from the workspace. Blocking workspace access does not delete the global account. No time tracking, payroll or leave. A personal workspace requires no profile or department, and a missing profile never blocks creating a personal workspace.
- [ ] **FR-23: Flat departments.** Owner/Admin create, rename and deactivate the workspace's departments; no parent/child. A department is deleted outright only when it has no members and no document references it; otherwise it can only be deactivated. Deactivating or deleting never widens access to documents restricted to that department.
- [ ] **FR-24 (P1): Import members from CSV.** Bulk-create invitations with profiles; report errors per row.

### Documents
- [ ] **FR-06: Upload documents.** Only PDFs with a text layer and Markdown (`.md`, UTF-8); at most 20 MB per file. Duplicates are blocked by SHA-256 within a workspace. Only the **publisher** of a document's scope uploads and deletes: the workspace publisher for `WORKSPACE` documents, the owning department's publisher for `DEPARTMENTS` documents; the OWNER can revoke (delete) any document; an ADMIN does not write documents (changed 2026-11-10 by [ADR-009](../architecture/decisions/adr-009-department-publishers.md)). Every member can view and download original files within their read scope. Owner decision 2026-10-20: DOCX is deferred until after the V2 MVP; a DOCX upload is rejected with `415`, creates no job, and tells the user to export a PDF with a text layer. Owner decision 2026-10-21: TXT is dropped from the MVP; `.txt` is rejected with `415` and the user is told to rename it to `.md`. No server-side format conversion, no OCR. Managers are responsible for loading only content they may use; the MVP has no approval workflow and no scheduled effective dates.
- [ ] **FR-07: Document lifecycle.** `UPLOADED → PROCESSING → READY | FAILED`; the UI shows both `UPLOADED` and `PROCESSING` as "Processing". `READY` means technical processing succeeded and the document can be queried; it does not mean a person has checked the content. Retrying a `FAILED` version reprocesses that exact file. When uploading a replacement the manager picks the target document; the system never infers version relationships from names or meaning. A replacement with different bytes is reprocessed as a whole file (no minor/major classification, no incremental per-passage processing, no semantic dedup); the old chunks are deleted after the new version is `READY`; if the new version fails the old one keeps serving. Duplicate rules for replacements (owner decisions 2026-10-20 and 2026-10-21):
  - same SHA-256 as the current `READY` version → no-op, report "File content has not changed", create no version or job;
  - same SHA-256 as the current version of another document in the workspace → report a duplicate, as when creating a new document;
  - the document has a version that is still processing: resubmitting that same file returns the processing version (no new job); a file with different bytes is rejected until the processing version finishes.

  Editing title, description, category or tags creates no ingestion job; changing visibility follows the access-sync mechanism of FR-25/FR-26. Deleting a document deletes the file and all its chunks.
- [ ] **FR-30: Multi-file selection.** The UI allows selecting up to 10 files per batch (a starting product limit, not a measured one), sent as one upload request per file; there is no batch table/job and no all-or-nothing transaction. Each file has its own status and failure reason; a failed, duplicate or over-quota file does not cancel the others. A failed file is retried or replaced on its own, without reloading files that succeeded. The user does not have to stay on the upload screen once files have finished uploading. ZIP/folder import, wiki/Git/Drive/SharePoint sync and a migration dashboard are out of scope (§5).
- [ ] **FR-08: Ingestion.** Structured extraction keeps page numbers and section headings, chunks, embeds, and stores `workspace_id`, `document_id`, `page` and character positions. The queue is durable (no lost jobs when the service restarts); jobs and outbox are idempotent, so resending the same operation does not duplicate a job. Content normalization (owner decision 2026-10-21, [AUDIT-markdown-normalization](../research/audit-markdown-normalization-and-preview-2026-10-21.md)):
  - A PDF is converted directly from the structure returned by **one** conversion library into a shared representation (headings, paragraphs, lists, tables, page numbers); no plain-text extraction followed by rebuilding Markdown; no fallback chain of tools. Input Markdown goes through a parser into the same representation.
  - From the cleaned representation the system renders **one canonical Markdown** shared by chunking, indexing, citations, metadata suggestions and the FR-31 view. Citation character offsets refer to this canonical (post-cleaning) Markdown. Both the structure and the Markdown are stored for reuse, so metadata suggestions never re-parse the file.
  - No LLM rewrites content. Identical content in different formats is not promised to produce identical Markdown.
  - Embedding cache keyed by model + revision + SHA-256 of the exact embedding input; no promised cache-hit rate; the Markdown hash is not used to skip a version automatically.

  Additions from [AUDIT-ingestion-sop-data](../research/audit-ingestion-sop-data-2026-10-19.md):
  - One extractor, producing structured text (headings, lists keeping the numbering shown in the source, tables in place).
  - Separate boilerplate from indexed content: headers/footers repeated on each page, national motto/heading lines, signatures, distribution lists, approval tables, revision-history tables.
  - Extract metadata from the content when present: document code, issue number, effective date.
  - Recognize structure by document type (ISO procedure, Chương/Điều/Khoản (chapter/article/clause), Markdown, non-standard prose); procedure tables (Responsibility/Step/Description/Form) are kept step by step.
  - Each chunk carries its heading path; tokens are counted with the embedding model's tokenizer.
  - PDFs without a text layer (scans) and image files are rejected with a clear message: status `FAILED` with a reason.
- [ ] **FR-25: Document visibility.** Each document is `WORKSPACE` (every `ACTIVE` member) or `DEPARTMENTS` (one or more departments, exactly one of which is the owning department). OWNER/ADMIN read every document. Write access follows the publisher rule (FR-06); switching `WORKSPACE ⇄ DEPARTMENTS` or changing the owning department is OWNER-only; the owning department's publisher can change the list of departments that may read (changed 2026-11-10, ADR-009). A MEMBER reads `WORKSPACE` documents and `DEPARTMENTS` documents that include their department; a MEMBER without a department reads only `WORKSPACE` documents. Read access applies to lists, search, detail, preview, download (pre-signed URL valid ≤ 5 minutes), dense, BM25, rerank, the LLM context, citations, caches and conversation history. Filtering happens **before** top-k selection, so no out-of-scope data reaches the LLM context. There are no per-person ACLs.
- [ ] **FR-26: Document metadata.** System metadata (file name, type, size, SHA-256, page count, status, version, uploader/upload date, detected language, embedding provenance, document code/issue number/effective date extracted from content) is written only by the system. Metadata edited by the document's publisher (ADR-009; before 2026-11-10, by Owner/Admin): title, short description, one category, many tags, language, visibility. Editing title, description, category or tags only updates attributes. Editing visibility only updates the access copy in ai-service, without re-embedding. Editing the language rebuilds the BM25 index only if BM25 is configured per language. No dynamic custom fields.
- [ ] **FR-27: Flat categories and tags.** Categories belong to the workspace, no tree; each document has at most one category. A category is for classification and filtering, not an access mechanism. Tags belong to the workspace and are created when attached.
- [ ] **FR-28: Background metadata suggestions.** They block neither upload nor `READY`. They reuse the extracted text and never download or re-parse the file. Rules first (title from the first heading or file name, language, document code/issue number/effective date); then one LLM call with structured output for description, category (chosen from the existing list, or left empty with a proposed new name) and tags (existing tags preferred). Input is limited to the title, the heading outline and representative passages. There is a timeout and at most one retry; on failure only the rule results are used. Cached by `(workspace_id, content sha256, prompt/model version, category list)`. Suggestions never overwrite fields the user has edited and never change visibility.
- [ ] **FR-09: Quotas.** Configurable through environment variables; `0` = unlimited.
  - **Documents and storage per workspace: 50 documents and 200 MB by default** (owner decision 2026-10-21, replacing the 2026-10-20 decision to disable them by default). Checked in the backend in the same transaction that creates the document, correct under concurrent uploads; a multi-file batch may partly succeed when it hits the quota. Replacing a version does not increase the document count. Raising the quota does not mean the system can handle a corpus of thousands of documents (not measured).
  - **Questions: off by default** (owner decision 2026-10-20, research first). When re-enabled, the reference values are 20 questions/user/day and 400 questions/day system-wide.
  - Technical limits are always on: 20 MB per file (FR-06), per-provider rate limiters (RPM/TPM) and automatic fallback to a backup model on 429.
- [ ] **FR-31: "Nội dung hệ thống nhận diện" (recognized content view).** A read-only view, available when the current version is `READY` (not while processing). It shows the canonical Markdown after conversion and cleaning, exactly the content that was chunked and indexed (FR-08). For PDFs it sits next to the original file in the existing document viewer, with page markers to jump to the matching page; no synchronized scrolling or two-way highlighting is required. It lists (collapsed) the boilerplate blocks removed from the index. It shows quality warnings only when the processor has a concrete signal (for example a page without text, unreadable characters, no headings recognized); there is no confidence score. Checking is optional, does not block the pipeline, has no "checked" state and no editor. FR-25 read access and the correct version apply: while a replacement is processing or has failed, the view shows the version in use with its version number label, and never shows the old version's content under the new version's status. Problems are fixed by replacing or deleting the file. The view does not replace measuring extraction quality on the corpus (V2-19).

### Q&A
- [ ] **FR-10: Hybrid RAG.** Dense (pgvector) + BM25, fused with RRF; rerank is optional and switched by configuration (off by default for free deployment, ADR-006). **Every query must filter by the token's `workspace_id`.**
- [ ] **FR-11: Answers with citations.** Streamed over SSE. Answer in the question's language (multilingual; VI and EN are the verified languages, others are best effort with no quality promise). Every claim carries `[n]`; every `[n]` maps to `document_id`, `page` and a passage. Citations that cannot be mapped are removed from the answer.
- [ ] **FR-12: Grounded refusal.** When evidence is below the configured threshold, answer "not found" with suggestions of the closest documents (if any), and record the question in the unanswered list.
- [ ] **FR-13: Layered guard, no LLM classifier.** The main defense is architectural: read access is filtered in SQL before anything reaches the LLM (FR-19, FR-25), the system prompt contains no secrets, unmappable citations are removed (FR-11), and missing evidence means refusal (FR-12). The guard adds four layers, none of which calls an extra LLM: (1) input: normalization (NFC, diacritics removed, leetspeak), a length limit, VI/EN rules at two levels: the block level (demands to reveal the system prompt/hidden rules, instruction overrides aimed at the instructions/prompt, impersonating the system role) returns a fixed refusal; the flag level (role play, "ignore"...) still answers and only logs; greetings/thanks/questions about the bot and messages containing only profanity are answered from templates, detected by rules and then by a semantic router comparing the question's embedding with example sentences (no LLM call; owner decision 2026-10-20, V2-27); (2) prompt assembly: chunks wrapped in escaped data tags, the question in its own message; (3) output: a canary token in the system prompt, and an answer containing the canary or a long passage of the system prompt is replaced by a refusal; (4) guard flags are logged for Admins. Harmful content relies on the provider's safety filters. There is no LLM node for intent classification or general-knowledge answers. Llama Prompt Guard 2 86M was dropped after the V2-02 test (2026-10-20).
- [ ] **FR-14: Citation viewer.** Clicking `[n]` opens the document at the right page (PDF) or passage (Markdown) and highlights the source passage on the canonical Markdown (FR-08). It shares its display component with FR-31.
- [ ] **FR-15: Conversations.** Listed per workspace, auto-generated titles, rename, delete. Only the creator can see their conversations.

### Feedback and quality
- [ ] **FR-16: Answer feedback.** Upvote/downvote + optional comment.
- [ ] **FR-17: Knowledge-gap list.** Admins see refused and downvoted questions and mark them handled. No multi-step review workflow. **MVP limit (ADR-009 §5):** only OWNER and ADMIN can see it; publishers cannot, and ADMINs have no document write access, so filling a missing document means the ADMIN tells the relevant department's publisher outside the system. Gaps are not routed to publishers by department automatically.
- [ ] **FR-18: Eval harness.** A dataset format (question, expected document/page, reference answer, `answerable` flag). A CLI that runs several configurations (dense, BM25, hybrid, hybrid + rerank) and writes a reproducible Markdown/JSON report.
- [ ] **FR-19: Tenant isolation test suite.** Automated tests create several workspaces whose documents contain their own "secret string" and prove that no question or API returns another workspace's data.
- [ ] **FR-29: Department authorization test suite.** A layer separate from FR-19, inside one workspace: a `DEPARTMENTS` document containing a secret string never appears to members outside those departments through any FR-25 path (API, dense, BM25, rerank, LLM context, citations, history, cache, download URL). It covers moving departments, suspension, deactivating a department, a blocked department deletion, and narrowing a document's visibility.
- [ ] **FR-20: Minimal audit log.** Records: sign-in, member/role/department changes, suspend/unsuspend, document upload/delete, document visibility changes. The Owner can view the workspace's log.
- [ ] **FR-21: Demo data.** A script creates a sample workspace with a public SOP set for demos and eval runs.

---

## 4. Non-Functional Requirements (NFR)
- **Tenant isolation (mandatory):** every business table has `workspace_id`; every query filters on it in the application layer, plus Postgres Row-Level Security as a second line of defense (ADR-005). FR-19 must show **zero leaks**.
- **Security:** short-lived access tokens (≤ 15 minutes), rotating refresh tokens with reuse detection. Losing a membership takes effect at the latest when the access token expires. No logging of tokens/secrets. No internal error details returned to the client.
- **Performance (on free infrastructure):** first token P95 < 3 s while the service is running; ingesting a 20-page PDF < 60 s. Metadata suggestions are not on the path to `READY`. Measured separately: upload response time, upload → `READY`, `READY` → suggestions available, LLM latency p50/p95, fallback rate, suggestion acceptance rate per field. No suggestion-speed target is set before there is a baseline. Cold starts on free tiers are accepted and stated in the report.
- **Cost:** target 0 USD/month. LLM provider quotas are protected by per-provider rate limiters and backup models; the FR-09 question quota is off during the research phase, and the document quota defaults to 50 documents/200 MB per workspace.
- **Extraction quality:** measured on the V2-19 corpus per document family (headings, tables, leaked boilerplate, wrongly removed content); thresholds are set only after a baseline. Perfect extraction is not required; the FR-31 view helps spot errors in individual files and is not evidence of quality.
- **RAG quality (initial targets, revisited after the baseline):** recall@5 ≥ 0.80; citation precision ≥ 0.85; correct refusal rate on unanswerable questions ≥ 0.80.
- **Testing & CI:** unit + integration tests run on GitHub Actions (free); FR-19 runs in CI.
- **Reproducibility:** one `docker compose up` brings up the whole system locally; eval reruns give the same retrieval results for the same data and configuration.

---

## 5. Scope & Boundary

| Area | In scope | Out of scope (cut from V2) |
|---|---|---|
| Identity | Google login, JIT users, workspaces, memberships with member profiles, invitations carrying profiles, suspension, domain join (P1), CSV import (P1), dev login for tests | Registration/passwords, OTP, forgot/change password, HR roster created before sign-in, session management, sign-in history, HRM (time tracking, payroll, leave), deleting the global account |
| Organization | Workspace + 3 roles, flat departments (at most one department per member) | Department trees, several departments per person, document-management rights for department heads (P1) |
| Documents | PDF with a text layer, MD; selecting ≤ 10 files per batch with per-file results (FR-30); upload, replace with a new version, delete, view, download the original, the "Nội dung hệ thống nhận diện" view (FR-31), department-based visibility, flat categories and tags, minimal metadata, background metadata suggestions | TXT (dropped 2026-10-21), DOCX (deferred until after the MVP), automatic format conversion, OCR of images and scanned PDFs, LLM content rewriting, a Markdown editor, approval workflows/"checked" status, scheduled effective dates, OnlyOffice, edit locks, version conflicts, force-push, version comparison/restore, policy comparison, incremental per-passage processing, semantic dedup, inferred version relationships, batch/all-or-nothing transactions, ZIP/folder import, wiki/Git/Drive/SharePoint sync connectors, migration dashboard, tree catalogs, custom fields, per-person ACLs |
| Q&A | Hybrid RAG, rerank, SSE, citations, refusal, one-step guardrail, conversations | Multi-tier intent classification, choosing the LLM model from the UI |
| Analytics | Feedback, knowledge-gap list, minimal audit, eval harness | Analytics dashboards, trends, export, reports, user/document statistics |
| Infrastructure | 2 backend services + Postgres/pgvector + S3 object storage | A separate API gateway, RabbitMQ, Redis, circuit breakers, role-based rate limiting |
| UI | Sign-in, workspace picker, chat + citation viewer, documents, members, knowledge gaps, workspace settings | A system admin page, analytics |

---

## 6. Research questions (the part submitted to the university)
**Feasibility principle:** the goal is a system that *runs* and is *measurable* for the report, not the absolute best configuration. Every configuration in an experiment must run on the owner's machine (CPU, no GPU) for free, and the report states the measured cost (time, RAM). Heavy configurations (rerank, an LLM judge) run only on a fixed subset if needed, and the report says so.

- **RQ1:** On multilingual (VI, EN) SOP documents, how much does hybrid retrieval (dense + BM25, RRF) improve recall@k over dense only or BM25 only? Report by question language.
- **RQ1b (secondary):** When the question and the document are in different languages (cross-lingual), how do dense, BM25 and hybrid differ? (BM25 is word-based and is expected to be weak here; this must be measured, not assumed.)
- **RQ2:** How much does rerank improve citation precision and faithfulness, at what latency cost?
- **RQ3:** How does the refusal threshold trade off wrong answers against wrong refusals?
- **RQ4 (secondary):** How does tenant filtering (application + RLS) affect retrieval latency?
- **RQ5 (proposed):** Which open-source embedding model (bge-m3, Qwen3-Embedding-0.6B, multilingual-e5-large-instruct) retrieves best on the project's multilingual corpus, taking CPU cost into account?

**Limits of the claims (owner decision 2026-10-19):** the RQ1–RQ5 corpus (V2-06) is English Markdown documents with VI and EN questions. The results do not prove quality on Vietnamese documents or on DOCX/PDF. Extraction quality for Vietnamese PDFs with a text layer is measured separately on the V2-19 extraction corpus and is not merged into RQ1–RQ5.

Environment and experiment design: ADR-006 §4.2 (runs on the local machine, independent of provider quotas).

---

## 7. Overall Acceptance Criteria (DoD)
- [ ] UC-01 to UC-12 work through the UI and the API when brought up with `docker compose up` on the local machine (public deployment is out of scope, see §8).
- [ ] FR-19 and FR-29 show zero leaks and run in CI.
- [ ] The eval report (FR-18) answers RQ1–RQ3 with numbers and is stored in `docs/research/`.
- [ ] No costs beyond free APIs; any cost incurred is recorded.
- [ ] The core-api and ai-service designs are approved; the architecture docs (`docs/architecture/`) are updated for the new architecture.

---

## 8. Decisions on the open questions (owner decision 2026-10-19)
1. **Java:** 21 (LTS) for core-api.
2. **Hosting:** local only, with `docker compose up`. Public deployment (B1, B2) is out of scope for V2; B3 (local machine + Cloudflare Tunnel) is the last-resort option. No Oracle (decision 2026-10-17).
3. **Embedding:** `bge-m3` running locally (ADR-006). Jina was dropped on 2026-10-17.
4. **Object storage:** a pinned MinIO version for local and CI. R2/B2 are only needed for deployment, so they are out of scope for V2.
5. **LLM (role split decided 2026-10-19, ADR-006 §4.4):** answers by Gemini 3.1 Flash Lite with Groq `openai/gpt-oss-120b` as backup; metadata suggestions by Groq `openai/gpt-oss-20b`; injection guard by rules (Prompt Guard 2 86M dropped after the V2-02 test on 2026-10-20); eval judge by Groq `openai/gpt-oss-120b`. At most one answer-generating LLM call per question. Groq was called successfully on 2026-10-20; Gemini 3.1 Flash Lite returned 503 (overloaded) during the test and needed a retry. *Superseded 2026-11-01 for generation and the judge (owner decision recorded in the V2 PLAN change log, ADR-006 §4.4 rewritten the same day): Gemini and Groq `gpt-oss-120b` were dropped in favour of small open models self-hosted on Modal; `services/ai-service/config/models.yaml` is the source of the current model ids. This item is kept as history.*
6. **Public demo workspace:** not built, since there is no public deployment. Local demo data per FR-21 (V2-16). ADR-005 needs no amendment.
7. **Departments per member:** at most one; a document may be restricted to several departments. Several departments per person is P1 if a real need appears.
8. **Conversation history after losing access:** hide answers and passages generated from documents the person can no longer read (documents that were in the LLM context, not only cited ones; changed 2026-11-09, [TECH-V2-ai-service §7.5](../architecture/components/ai-service.md)); keep the question and a note on why it is hidden.
9. **Department heads managing their department's documents:** ~~P1. In V2 only OWNER/ADMIN upload, edit, delete and change document visibility.~~ *Changed 2026-11-10 ([ADR-009](../architecture/decisions/adr-009-department-publishers.md)):* in the MVP as publishers. Each department has one publisher who is a member of that department, and each workspace has one publisher for `WORKSPACE` documents; only the OWNER assigns them. The OWNER revokes documents and transfers responsibility, but does not author content when not a publisher; an ADMIN does not write documents. There is no in-system review flow.

**Additional owner decisions 2026-10-20 (V2-03):**

10. **Research first:** commercial constraints are paused; the FR-09 quotas are off by default (unlimited), and the configuration mechanism stays so they can be re-enabled. Whether to allow 20 or 50 questions/day (TECH-V2-core-api Q2) no longer needs a decision. *Changed 2026-10-21 (item 14): the document/storage quota defaults back on at 50/200 MB; the question quota stays off.*
11. **Feedback and knowledge gaps (FR-16, FR-17)** live in ai-service (schema `rag`), amending ADR-004 §4.1.
12. **Ingestion scope:** [PRD-V2-ingestion-mvp-scope](../archive/01-requirements/PRD-V2-ingestion-mvp-scope.md) is approved; FR-30 (multi-file selection) and the no-op on a replacement with the same SHA-256 (FR-07) move into this PRD. On 2026-10-21 all remaining content of that document was merged into FR-06..FR-09 and FR-30 and that document became `superseded`; this PRD is the single source of requirements.
13. **Sign-in:** anyone with a Google account can sign in and gets a personal workspace (UC-01), without an invitation.

**Additional owner decisions 2026-10-21 (Markdown normalization and the extraction view, [AUDIT-markdown-normalization](../research/audit-markdown-normalization-and-preview-2026-10-21.md)):**

14. **Formats and quotas:** the MVP accepts only PDFs with a text layer and Markdown; TXT is dropped, DOCX and OCR stay deferred (FR-06). The document quota defaults to 50 documents/200 MB per workspace, checked in the backend including concurrent uploads (FR-09).
15. **Content pipeline:** one library converts PDFs into a structured representation, Markdown also goes through a parser into the same representation, and one canonical Markdown rendered after cleaning is the shared source (FR-08). The PDF library is **Docling** (ADR-008, owner decision 2026-10-21, not yet tried on the corpus); V2-20 confirms it against the hard constraints in the report above, with no further comparison against PyMuPDF.
16. **The "Nội dung hệ thống nhận diện" view (FR-31) opens only at `READY`:** opening it right after convert/clean would need an extra read path for a not-yet-active version, cleanup on failure and another UI state, while the remaining wait for embedding is small. It can be reconsidered after measuring `t_ready`.
17. **Replacement and dedup:** the rules are in FR-07; a document with a version still processing does not accept a replacement file with different bytes.
