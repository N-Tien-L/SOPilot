---
id: V2-33
title: "Frontend: members, departments and document metadata"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-13
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-15, V2-23, V2-24, V2-25, V2-30, V2-36]
blocks: [V2-17]
branch: "feat/web-v2-33"
assignee: pair
---

# TICKET V2-33: Frontend: members, departments and document metadata

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
Scope split from V2-15 (XL) on 2026-10-24; the approved PRD/TECH requirements are unchanged. Use the frontend-delivery skill and `.claude/rules/frontend.md` when implementing. FR-04/FR-22 to FR-29.

## 2. Acceptance criteria
- [ ] Members: profile (full name, employee code, job title, department), suspend/unsuspend; flat departments and categories: create, rename, archive, delete when allowed. Hide departments in a single-member workspace.
- [ ] Documents: edit metadata, choose the `WORKSPACE`/`DEPARTMENTS` scope, view and accept/edit metadata suggestions; the suggestion status does not block other actions.
  - The suggestion form follows the owner decision of 2026-11-12 in V2-25 §2a: one editable form, `doc_code`/revision/effective date read-only, the create-suggested-category button only for OWNER/ADMIN.
- [ ] UI to create/revoke/accept invitation links; OWNER/ADMIN actions by permission, with API errors shown in context.
- [ ] Browser check of admin/member permissions, suspended status, suggestions running/failed and changed read access.

## 3. Guide
1. Declare types in `frontend/web/types` and the API client in `frontend/web/lib/api.ts` per TECH-V2-core-api/ai-service.
2. Implement in `frontend/web/app/` and `frontend/web/components/`, using the V2-15 shell.
3. Record browser evidence per acceptance criterion; update the frontend README.
- Update the related contracts in `.agent/context/` along with the change; V2-17 only consolidates and removes V1 descriptions.

## 4. Testing
- Browser: profiles/departments/flat categories, invitations, last OWNER, editing document access, metadata suggestions not blocking upload/chat.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit.
