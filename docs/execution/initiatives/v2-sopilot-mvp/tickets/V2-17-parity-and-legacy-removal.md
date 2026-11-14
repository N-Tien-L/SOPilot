---
id: V2-17
title: "Parity check, remove the 8 old services, update guidance docs"
type: chore
status: todo
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: platform
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-14, V2-15, V2-16, V2-26, V2-31, V2-32, V2-33]
blocks: [V2-18]
branch: "chore/platform-remove-legacy"
assignee: pair
---

# TICKET V2-17: Parity and removing the old code

> Translated from Vietnamese on 2026-11-13; content unchanged. Since the 2026-11-13 docs restructure, the V1 context docs that this ticket rewrites live as an archived snapshot in `docs/archive/v1-context/`, and the V2 context lives in `docs/architecture/`.

## 1. Context & goal
Remove only once V2 reaches parity. Remove in a separate commit so the history is clear.

## 2. Acceptance criteria
- [ ] A parity table: each of UC-01 to UC-11 and every P0 FR passed/not passed with evidence.
- [ ] Safety conditions before removal (record the result of each):
  - No references from the V2 parts to V1: search `auth-service|user-service|knowledge-service|metadata-service|feedback-service|api-gateway|ai-qa-service|ingestion-service|init-db|:3001` in `services/core-api`, `services/ai-service`, `frontend/web`, `eval/`, `scripts/`, `.github/workflows/`, `docker-compose.v2.yml`; every remaining hit has been dealt with.
  - Every part ported per ADR-004 §4.5 has tests in the new service, and they are green.
  - The eval harness (`eval/`) and CI (`.github/workflows/ci.yml`) are green with only the V2 stack.
  - `docker compose -f docker-compose.v2.yml up` from empty volumes runs every demo UC (V2-16) without starting any V1 container.
  - The tag `v1-final` (V2-15) exists and has been pushed to the remote; also an M1 milestone tag/branch if it is a different commit.
- [ ] Remove `auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`, `api-gateway`, `ai-qa-service`, `ingestion-service`, the old `docker-compose.yml`, `docker-compose.dev.yml` and the infrastructure only V1 uses (`infrastructure/init-db/`, `infrastructure/combined_init.sql`, `infrastructure/onlyoffice/`, `infrastructure/seed*` if V2-16 does not reuse them) — only those exact paths, never recursive wildcard deletion (CLAUDE.md). Rename `docker-compose.v2.yml` to `docker-compose.yml` in the same change if the owner agrees.
- [ ] Do not delete the V1 Docker volumes (`sopilot_postgres_data`, `sopilot_minio_data`, ...) in this ticket; only record the cleanup commands for the owner to run when they want (CLAUDE.md: no `down -v`, no prune).
- [ ] Update `CLAUDE.md` (architecture table, commands, the drift section: remove items no longer valid), `.claude/settings.json` (remove the `ask` permissions for V1 paths), `README.md`; delete `.claude/rules/v1-frozen.md`.
- [ ] Update `docs/architecture/` (api, data, domain, components/frontend; the V1 context stays in `docs/archive/v1-context/`) and `scripts/*.ps1` for the new structure.
- [ ] `./scripts/pre-commit-check.ps1` PASS.
- [ ] Keep a git milestone (tag/branch) of M1 before removing.

## 3. Guide
Order: check the safety conditions → confirm the tags → update scripts/docs → remove the services → run pre-commit. Also delete `.claude/rules/v1-frozen.md` and the V1 job in `.github/workflows/ci.yml`. Needs an explicit owner request before committing.

## 4. Testing
`./scripts/pre-commit-check.ps1`, `./scripts/check-services.ps1` (updated for 2 services).
