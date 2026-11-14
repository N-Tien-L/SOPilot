---
id: V2-13
title: "Answer feedback and the knowledge-gap list"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-14
author: "Owner"
scope: ai-qa
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12]
blocks: [V2-15, V2-37]
branch: "feat/ai-qa-v2-feedback-gaps"
assignee: pair
---

# TICKET V2-13: Feedback and knowledge gaps

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
FR-16, FR-17. Replaces feedback-service with a minimal part inside ai-service, with no analytics dashboard. Owner decision 2026-10-20 (TECH-V2-core-api §11 Q1, ADR-004 §4.1): it lives in ai-service because questions, answers and refusal flags are in schema `rag`. Design: TECH-V2-ai-service §7.6.

## 2. Acceptance criteria
- [x] Up/down vote + an optional comment on an answer, one vote per user per answer.
- [x] Admins see refused and downvoted questions and mark them handled; no multi-step review workflow. Changed 2026-10-21 (owner decision D2, TECH-V2-ai-service §7.6): the list contains questions with `refusal_reason` `NO_EVIDENCE` or `GENERATOR_NOT_FOUND`, downvoted answers and `ANSWERED` questions with `checks.citationCount = 0`; it **excludes** `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE`, `REFUSED_GUARD`.
- [x] Changed 2026-10-21 (D8): the questions in the list are the PII-masked version (recomputed with `qa/pii.py` at response time, no second copy stored); tested with a question containing an email and a phone number.
- [x] Filtered by `workspace_id` + RLS; members cannot see the admins' list; the list carries no asker names (FR-15).
- [x] No dashboard, export or trends (out of scope, PRD §5).
- [x] (Moved from V2-14) The tenant-isolation suite covers the feedback API and the knowledge-gap list: ≥ 3 workspaces with "secret strings", never returning another workspace's votes, comments or questions; runs in `tenant-isolation.yml`.

## 2a. Evidence (2026-11-13)
- Code: `services/ai-service/src/sopilot_ai/api/feedback.py`, `feedback/gaps.py` (the criteria are constants and the SQL is generated from them), `feedback/repository.py`. The tables already exist in `rag/V003`; no new migration.
- Votes: `PUT /ai/v1/messages/{id}/feedback` only by the conversation's owner, only on `ASSISTANT` messages, upsert by `(message_id, user_id)` (one vote per person per answer). The list: `GET /ai/v1/knowledge-gaps` (OWNER/ADMIN, MEMBER `403`), `POST .../{id}/resolve` (idempotent, `404` when not a gap).
- Tests: `tests/integration/test_feedback_isolation.py` (15 tests: 3 workspaces with secret strings, MEMBER gets `403`, only the right criteria, email and phone masked, no asker identity, votes/comments/questions not leaking to other workspaces, resolve once), `tests/unit/test_feedback_sql.py` (every subquery filters `workspace_id`). The integration file was added to the ai-service step of `tenant-isolation.yml`.
- No dashboard, export or trends.
- `tenant-isolation.yml` ran on GitHub Actions for PR #14 (jobs `database`, `negative-control`, `department-authorization` passed). Owner review done 2026-11-14 ([PLAN-V2](../PLAN.md) change log).
- **Still open:** the feedback and list UI belong to `V2-15`.

## 3. Guide
- **Files:** `services/ai-service/` (tables `rag.message_feedback`, `rag.knowledge_gap_status`, APIs `/ai/v1/messages/{id}/feedback`, `/ai/v1/knowledge-gaps`); sources: `services/feedback-service`, `services/ai-qa-service/src/services/knowledge_gap.py` (reference only, the old thresholds are not reused).

## 4. Testing
Unit tests for permissions and idempotent votes; integration on real Postgres (`./scripts/run-tests.ps1 -Scope ai-service`, the scope added in V2-08).
