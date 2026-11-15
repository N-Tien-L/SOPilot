---
id: V2-41
title: "core-api: out-of-order version status callbacks (409 INVALID_TRANSITION) leave a failed document PROCESSING"
type: fix
status: review
created: 2026-11-16
updated: 2026-11-16
author: "Owner"
scope: knowledge
priority: P1
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-12]
blocks: [V2-18]
branch: "fix/core-ingest-failed-callback"
assignee: pair
refs:
  - docs/architecture/components/core-api.md
  - docs/architecture/components/ai-service.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-31-frontend-document-upload.md
---

# TICKET V2-41: Version status callbacks arriving out of order

> **Scope:** `knowledge` | **Size:** `S` | **Priority:** `P1`
> **Parent plan:** `PLAN-V2-SOPILOT-MVP` | **Branch:** `fix/core-ingest-failed-callback`

## 1. Context & goal
Found by the V2-31 browser run ([V2-31 §5](V2-31-frontend-document-upload.md), "Found outside this ticket"): a corrupt PDF stays `PROCESSING` in core-api although the worker marked its job failed, and the worker log shows `outbox_event_dead ... error='HTTP 409'`.

**Reproduction (2026-11-16, read-only queries on the local stack, nothing changed).** `rag.outbox_events` joined to `core.document_versions` on the `versionId` of each `VERSION_STATUS` event:

1. Versions `01a1ddc6-…` and `01a1ddc7-…` (corrupt files, 2026-11-15 05:56) are `PROCESSING` with no failure code. For each, the `FAILED` event (`CORRUPT_FILE`) was `DELIVERED` (no error) **before** its `PROCESSING` event: FAILED at 05:56:09.819, PROCESSING at 05:56:09.830 (and 05:56:16.751 vs .767). The late `PROCESSING` is accepted because `VersionStatusService.processing` allows `FAILED → PROCESSING` (ai-service's own retry). The version ends `PROCESSING`.
2. The versions of 2026-11-14 17:28–17:32 got the same two events in the right order (PROCESSING 17:32:18.187, FAILED .197) and are `FAILED` with `CORRUPT_FILE`. So the outcome depends only on delivery order.
3. The 409 itself is the mirror case: 12 `PROCESSING` events are `DEAD` with `HTTP 409` because the version was already `READY` (11 versions) or `SUPERSEDED` (1) when the late `PROCESSING` arrived (`processing()` rejects it with `INVALID_TRANSITION`; the dispatcher treats a 4xx as a contract error and drops the event after one attempt). Those documents are fine; the dead events are noise.

**Mismatch with the first report of this bug:** the V2-31 note says the `FAILED` callback gets `409`. The data shows the `FAILED` callback succeeds and it is the late `PROCESSING` that overrides it (or gets the `409` after `READY`). The title above follows the data.

**Probable cause (not yet proven):** the two events for one version are created in separate transactions a few ms apart, and delivery is not ordered per version. `rag.claim_outbox_batch` orders by `next_attempt_at, created_at` with `FOR UPDATE SKIP LOCKED` and leases rows, and the worker calls `dispatch_due` from more than one place, so a later event can be sent first. Confirm by logging claim order for one version before choosing the fix.

Goal: a version never moves backwards because of a stale callback, and a stale callback is not a dead letter.

## 2. Acceptance criteria
- [ ] **Failing test first.** An integration test applies `FAILED` then `PROCESSING` for the same version and attempt, and today ends `PROCESSING`; it must end `FAILED` (core-api `VersionStatusService`, and/or an ai-service dispatcher test if the fix is there).
- [ ] **Stale callbacks are ignored with success, not rejected.** `PROCESSING` for a version already `READY`, `FAILED` (same attempt) or `SUPERSEDED` returns `2xx` and changes nothing (same rule as "an older `attempt` is ignored with success", TECH-V2-core-api §8.2). A real retry must still work: `FAILED → PROCESSING` only when the callback carries a **newer** `attempt`.
- [ ] **No new dead letters** from this race: after a corrupt-file upload and a normal upload on the compose stack, `rag.outbox_events` has no `DEAD` row and the corrupt document shows `FAILED` with its code in the UI.
- [ ] If delivery order is also fixed in ai-service (per-aggregate order in `claim_outbox_batch`), that is a new `rag` migration (skill `flyway-migration`) and a test; if the core-api rule alone is enough, say so and do not touch the outbox.
- [ ] TECH-V2-core-api §8.2 states the rule (append, never renumber); `V2-31` §5 note points here.
- [ ] The 12 existing `DEAD` events and the two stuck versions are left alone by the code change; the owner decides whether to repair them by hand.

## 3. Guide
- Code: `document/VersionStatusService.java` (`processing`, `failed`, `CAN_START`), `ai-service` `ingest/handler.py` (events created), `outbox/dispatcher.py` (4xx is final), `db/repositories/outbox.py` and `rag.claim_outbox_batch`.
- Do not "fix" it by retrying 409: a real contract error must still go dead.
- Not in this ticket: changing the failure messages, the retry button (`POST /retry`), or the frontend (it only reads the status).

## 4. Testing
```powershell
./scripts/run-tests.ps1 -Scope core-api -Type unit      # Mockito stderr warning aborts the wrapper: run ./mvnw directly if so
./scripts/run-tests.ps1 -Scope core-api -Type all       # Docker
./scripts/run-tests.ps1 -Scope ai-service -Type unit
```
Then a corrupt 15-byte `%PDF-` upload on the compose stack, looking at the document status and `rag.outbox_events`.

## 5. Changed files
| Area | Action |
|---|---|
| `services/core-api/.../document/VersionStatusService.java` and tests | MODIFY |
| `services/ai-service/.../outbox`, `infrastructure/db/migrations/rag/` | MODIFY / CREATE only if ordering is fixed there |
| TECH-V2-core-api §8.2, V2-31 §5 | MODIFY |

## 6. Results

Implemented on `fix/core-ingest-failed-callback` (not committed yet, 2026-11-16).

**Reproduction first.** Four new tests in `DocumentLifecycleIT` ran against the unchanged state machine and failed: 4 of 22 (`FAILED` then `PROCESSING` of the same attempt ended `PROCESSING`; `PROCESSING` after `READY` and after `SUPERSEDED` returned `409`; a same-attempt `PROCESSING` restarted a `FAILED` version).

**Change.** `VersionStatusService.processing` ignores a `PROCESSING` callback (`200`, `applied = false`) for `PROCESSING`, `READY`, `SUPERSEDED` and same-attempt `FAILED` versions; `FAILED → PROCESSING` needs a newer `attempt`. Other invalid moves still give `409 INVALID_TRANSITION`, so a real contract error still goes dead. Design: TECH-V2-core-api §8.2.

**Ordering in ai-service.** Not touched: no `rag` migration and no outbox change. The core-api rule makes delivery order irrelevant for the version status. The cause (separate transactions and unordered claim of events of one version) was taken from the ticket's data, not re-confirmed by logging claim order.

**Review.** Fresh `v2-reviewer` (`claude-opus-5-5`): no blockers. Fixed: a test that `READY` for a `SUPERSEDED` version is still `409 INVALID_TRANSITION`, the missing `applied` assertion, the README endpoint row. Left open and out of scope here: the same reversal on the `READY`/`FAILED` paths (a `RETRY_EXHAUSTED` `FAILED` from an expired lease followed by a `READY` of the original worker gives `409` and a dead letter; the reverse order is harmless noise), not checked against `jobs.finish`/`activate_version`; `FAILED → PROCESSING` with a newer attempt does not store the new `attempt` (ai-service never takes that path, core-api's retry goes through `resetForRetry`); the PLAN has no "Owner decision" log entry for the V2-41 counters.

**Evidence.**
- `./mvnw verify` in `services/core-api` (the `run-tests.ps1` wrapper aborts on the Mockito stderr warning): 252 tests, 0 failures, `BUILD SUCCESS`; `DocumentLifecycleIT` 22 tests.

**Not verified.**
- The compose-stack check (corrupt `%PDF-` upload plus a normal upload, no `DEAD` row in `rag.outbox_events`, `FAILED` with its code in the UI) has not been run.
- The ai-service unit suite was not run (no ai-service change).
- The `V2-31` §5 note pointing here was not added: that section exists only on `feat/web-v2-32`.
- The 12 `DEAD` events and the two stuck versions were not touched.
