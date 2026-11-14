---
id: V2-16
title: "Demo data and a one-command docker compose"
type: feat
status: done
created: 2026-10-17
updated: 2026-11-14
author: "Owner"
scope: platform
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12, V2-21, V2-24, V2-36]
blocks: [V2-17]
branch: "feat/platform-demo-compose"
assignee: pair
---

# TICKET V2-16: Demo data and a one-command run

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
FR-21 and the reproducibility NFR: `docker compose up` brings the system up locally; the research handover runs on the assessor's machine.

## 2. Acceptance criteria
- [x] A script creates a sample workspace with a public SOP set (using the V2-06 corpus), idempotent; the number of documents and storage stay within the default quota of 50 documents/200 MB (PRD-V2 FR-09, owner decision 2026-10-21), or the README states the quota variables to set; at least two departments, sample members and one department-restricted document to demo UC-10.
- [ ] One command brings up: Postgres, object storage, Flyway, core-api, ai-service, frontend (and local embedding if enabled).
- [x] A root README: machine requirements (RAM/CPU), the steps, configuring `.env` from `.env.example`, enabling dev login without Google, running eval.
- [x] LLM guidance: API (Gemini/Groq) or local, and the behaviour without a key (a clear error, no hang).
- [ ] Try on a clean environment (machine or fresh clone); record the time from clone to a working Q&A.
- [ ] Changed 2026-10-21 (audit by query type, P1-7): measure end-to-end TTFT (P50/P95, PRD-V2 NFR target: P95 < 3 s) on the local stack with about 30 questions, **with and without** the question-rewrite step (new conversations and conversations with history); the report records the hardware, the real provider, the number of runs and the spread. If the target is not met, record it; do not change the target in this ticket.

## 2a. Evidence and open items (2026-11-13)
- One-command compose: `docker-compose.v2.yml` adds `core-api`, `ai-service`, `ai-worker` (healthcheck off because the worker has no HTTP), `web`; Dockerfiles `services/core-api/Dockerfile`, `services/ai-service/Dockerfile` (extras `local` + `pdf`). Required variables use `${VAR:?}`, so compose stops and names the missing variable. The stack ran on the owner's machine (Postgres, MinIO, core-api, ai-service healthy).
- Seed `scripts/seed-demo.ps1`: workspace `SOPilot Demo Workspace`, departments "Kỹ thuật" (Engineering) and "Nhân sự" (HR), two invited members who **accepted through dev login** (`engineer@sopilot.local` is the "Kỹ thuật" publisher per ADR-009, `hr@sopilot.local`), 2 workspace-wide SOPs + 1 SOP restricted to "Kỹ thuật" from `eval/datasets/sop-pilot` and `smoke` (files tracked in git), 3 documents, under the 50/200 MB quota. Run on 2026-11-13 on the local stack: the first run created everything, the second `0 uploaded, 3 already present`, exit 0; 3 documents `READY`; the engineer sees 3 documents, HR sees 2 (UC-10). Fixed a Windows PowerShell 5.1 encoding bug (an ISO-8859-1 request body turned the department name into `K? thu?t`); the department created wrongly in an earlier run was renamed through `PATCH /api/v1/departments/{id}`.
- Root README: machine requirements, configuring environment variables from the sample file at the repo root, dev login, LLM (Modal per ADR-006 §4.4, replacing the original ticket's Gemini/Groq) and the behaviour without a key, eval, TTFT measurement. The "4 CPU, 8 GB RAM" requirement is an estimate, not measured on a clean machine.
- TTFT script `scripts/measure-ttft.ps1`: 15 new-conversation questions + 15 follow-ups (with rewrite), client-side TTFT to the first `delta`/`refusal`, P50/P95, spread, hardware, written to `eval/results/ttft/`. **Not run yet** (needs the real, warmed-up Modal endpoint).
- **Still open (owner):** (1) try on a clean machine or fresh clone, recording the time from clone to the first answer; (2) run `scripts/measure-ttft.ps1` with the real provider, recording hardware, number of runs and spread; if P95 < 3 s is not met, record it without changing the target; (3) ask one question through the API on the compose stack and get an answer with citations (§4); (4) the `web` image is still wired to the V1 gateway until `V2-15`, so the "one command brings up the frontend too" criterion is not functionally met.
- **Closure 2026-11-14:** set to `done` by owner decision ([PLAN-V2](../PLAN.md) change log) with three criteria **not met**: the frontend in the one-command stack (functionally depends on `V2-15`), the clean-environment try, and the TTFT measurement. Open items (1)–(3) move to [V2-18](V2-18-research-report-and-handover.md) ("Carried over from closed tickets"); item (4) is covered by `V2-15`.

## 3. Guide
- **Files:** `docker-compose.v2.yml` (completed from V2-08), `scripts/seed-demo.ps1`, `README.md`.

## 4. Testing
`docker compose -f docker-compose.v2.yml up -d`, then ask one question through the UI or API and get an answer with citations. Record the commands and results.
