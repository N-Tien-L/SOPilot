---
id: V2-03
title: "Write TECH-V2-core-api and TECH-V2-ai-service"
type: docs
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: docs
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-09, V2-11, V2-20]
branch: "docs/docs-tech-v2"
assignee: pair
---

# TICKET V2-03: TECH-V2

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
Specify the DDL (with RLS), APIs, sequences and events of the two new services, folding in findings R1–R5, A1–A9 and AUDIT §4.2. Skill at the time: `.agent/skills/design-architecture/SKILL.md` (removed 2026-11-08).

## 2. Acceptance criteria
- [x] `TECH-V2-core-api.md`: DDL for workspaces, memberships, invitations, documents, outbox, audit, quota, feedback; a versioned REST API; the Google login and refresh flows.
- [x] `TECH-V2-ai-service.md`: chunk DDL (with `workspace_id`, `embedding_provider/model/dim/revision`, 4 score columns); the `EmbeddingProvider`, `RerankProvider`, `LLMProvider` interfaces; `models.yaml`; the 2-LLM-call pipeline; the SSE and citation schema; the outbox contract from core-api.
- [x] `TECH-V2-ai-service.md` has an ingestion section per the extended FR-08: the intermediate document structure (V2-20 output), boilerplate and metadata separation (V2-21), document-type recognition and chunking (V2-22), the package location V2-09 imports.
- [x] Per ADR-007: membership DDL with profiles, `departments`, `document_departments`, `documents.visibility`, `categories`, `tags`, metadata field sources; the `wdept` claim; department/profile/metadata APIs; the contract updating `rag.document_access` from core-api; the metadata-suggestion job (V2-25).
- [x] RLS policy: `SET LOCAL app.workspace_id` per transaction, the DB role does not own the tables.
- [x] Rerank runs before the threshold; each mode has its own configurable threshold.
- [x] No straight port of `EMBEDDING_MODEL_NAME = "BGE_M3"` or the 512-token cut with `tiktoken`.
- [x] Frontmatter per `docs/README.md`; the owner approved, both TECH documents became `approved` (2026-10-20).

> **Acceptance 2026-10-20:** the owner approved [TECH-V2-core-api](../../../../architecture/components/core-api.md) and [TECH-V2-ai-service](../../../../architecture/components/ai-service.md), settling §11 as proposed. Q1: feedback/knowledge gaps live in ai-service (ADR-004 §4.1 and V2-13 updated). Q2: replaced by the research-first decision, commercial quotas off by default (PRD-V2 FR-09, §8.10). PRD-V2-ingestion-mvp-scope was approved at the same time and FR-07/FR-30 synchronized into PRD-V2, V2-12, V2-15.

## 3. Guide
- **Files:** `docs/architecture/components/core-api.md`, `ai-service.md` (CREATE; then `TECH-V2-*.md` in `docs/02-architecture/designs/`), following the TECH design template.

## 4. Testing
None. Cross-reviewed against PRD §3 so that every FR has a place in the design.
