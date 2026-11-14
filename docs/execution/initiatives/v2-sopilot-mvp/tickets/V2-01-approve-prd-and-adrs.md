---
id: V2-01
title: "Approve PRD-V2, ADR-004/005/006/007 and settle open questions"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: docs
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-03, V2-04, V2-08]
branch: "docs/docs-approve-v2"
assignee: owner
---

# TICKET V2-01: Approve PRD-V2, ADR-004/005/006

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
Per the agent instructions at the time, no PLAN is made while the PRD is not `approved`. This ticket moves four `draft` documents to `approved` (or edits them as the owner wants) and settles the open questions of PRD §8.

## 2. Acceptance criteria
- [x] The owner decides each open question of PRD §8 and records the result in the PRD: Java 17 or 21; LLM provider; object storage when running locally; whether there is a public demo workspace.
- [x] Since the current scope is local only: record that B1/B2 (deployment) are out of scope and B3 is optional.
- [x] PRD-V2, ADR-004, ADR-005, ADR-006, ADR-007 have `status: approved`; ADR-001, ADR-002, ADR-003 and PRD-M1 become `superseded`.
- [x] PLAN-V2 becomes `approved`.

## 3. Guide
- **Files:** `docs/product/prd-v2-sopilot-mvp.md`, `docs/architecture/decisions/adr-00{1,2,3,4,5,6,7}-*.md`, `docs/execution/initiatives/v2-sopilot-mvp/PLAN.md`
- **Action:** MODIFY. Update the `status`/`updated` frontmatter, PRD §8, and the `superseded_by` links.
- This is the owner's work; the agent only prepares a comparison of the options.

## 4. Testing
None. Checked by rereading the frontmatter of the files above.

## 5. Progress (2026-10-19)
- The owner settled open questions 1–6 of PRD-V2 §8 as proposed (Java 21; local only; pinned MinIO; LLM Gemini Flash-Lite + Groq `gpt-oss-*` subject to V2-02; no public demo workspace). FR-08 and the corpus limits were added per AUDIT-ingestion-sop-data; `V2-19` to `V2-22` added.
- The same day, the owner reopened the scope to keep member profiles, flat departments, category/metadata, metadata suggestions and department-based document access (ADR-007, `V2-23` to `V2-26`), and settled PRD §8 items 7–9 as proposed. The whole document set went back to `draft` for re-approval.
- 2026-10-20: the owner approved PRD-V2, ADR-004/005/006/007 and PLAN-V2 after running V2-02 (Groq passed; Prompt Guard rejected, the guard moved to four layers without LLM calls; Gemini 3.1 Flash Lite still had to be retried because of a 503). ADR-001/002/003 and PRD-M1 became `superseded`.
