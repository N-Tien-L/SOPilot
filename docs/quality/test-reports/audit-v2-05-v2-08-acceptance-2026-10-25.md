---
id: AUDIT-V2-05-V2-08-ACCEPTANCE-2026-10-25
title: "Acceptance of V2-05 eval tooling and V2-08 local infrastructure"
type: audit
status: final
created: 2026-10-25
updated: 2026-11-13
author: "Owner"
scope: [eval, infra]
verdict: PASSED_WITH_WARNINGS
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-05-eval-harness.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-08-flyway-and-compose.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Context-doc paths under the former agent context folder are as they were at the time.

# Scope settled by the owner

The owner confirmed in chat on 2026-10-25: "ok chốt" (ok, settled), after agreeing to finish the
technical review, check the volume/network configuration and commit separately.

- **V2-05:** acceptance of the retrieval benchmark tooling. Not acceptance of RQ results,
  answer accuracy or SOPilot as a whole. The real dataset, the span-aware scorer,
  the docproc chunker and the official numbers still belong to V2-06/V2-07/V2-22.
- **V2-08:** acceptance of the local infrastructure base. Volume/network separation is checked in
  the base Compose configuration; runtime is checked with a separate project on tmpfs. Using the real
  `.env` or starting on the existing volume is not required to complete this scope.

## Review delta

Codex reviewed the diff and call paths of the splitter, metrics, retriever, embedding cache,
runner, migrations and MinIO init; no blocker remains within the scope above.
This is Codex's technical review together with the owner's scope acceptance; it does not record
an independent peer reviewer or a CI/PR review that has not happened.

- nDCG rewards only new sources and does not score repeated chunks; the threshold has refuse-all.
- The splitter checks for valid windows, the cache distinguishes endpoint/revision and the reranker
  is not reloaded for each configuration. A wrong configuration does not silently change mode.
- No inline credentials are stored in artifacts; the report states the doc/page proxy clearly.
- V002 additively fixes the global PUBLIC EXECUTE; V001 keeps its checksum. Both chains
  use a transaction advisory lock for shared default changes.
- A MinIO attach error is accepted only if the attached policy is verified to be correct; checked by
  running init a second time and that AI has no write/delete rights.

Context updated: the former agent context `database/schema.md`; guidance in
`infrastructure/db/README.md`. No product endpoint/event contract changed.

## Evidence

| Check | Result |
|---|---|
| `eval/.venv/Scripts/python.exe -m pytest -q eval/tests/test_eval.py eval/tests/test_harness_regressions.py --basetemp=eval/.cache/pytest-acceptance-20261025` | 18 passed; depends only on files in the V2-05/V2-08 commit |
| All of `eval/tests` with a new basetemp in the repo | 26 passed; includes the uncommitted data-preparation part |
| `ruff check eval/sopilot_eval eval/tests` | Pass |
| `sopilot_eval.infra_check` from `eval/` | Pass, project `sopilot-v2-readiness-20f4d9cf` |
| Base Compose rendered with an empty env file/random credentials | Project `sopilot-v2`; volumes `sopilot-v2_postgres_data`, `sopilot-v2_minio_data`, not external; network `sopilot-v2-network`; ports bound to loopback only |
| tmpfs runtime | Flyway core/rag, role/schema isolation, RLS read/write for both roles, function grants, S3 core write/delete, AI read-only, anonymous 403, repeated init all pass |

An earlier verification run reported minio-init exit 1; that run's log was not enough to
determine the cause. The runner gained credential-masked diagnostics; the new run
on the project above passed. No claim is made about startup stability over many runs or in CI.

## Commit split and limits

Regression tests were split from the data/PLAN tests so the commit runs on its own on the
tracked baseline. The commit contains only V2-05/V2-08 and the acceptance of the two tickets.
The PLAN was staged selectively from HEAD, updating only the two statuses/counters; the
33-ticket PLAN and the existing spec edits stay in the working tree and are not committed with it.
So the commit snapshot has 27 tickets/4 done/2 review; the working tree currently has
33 tickets/5 done/1 review. `implemented_tickets` is 6 in both.

`.env` was not read; no volume was reset/pruned/deleted or the old one mounted; no migration was applied
to the owner's DB; no push/merge. The next step is the V2-06/V2-19 data,
then V2-20 once a suitable corpus exists.
