# CLAUDE.md

Working guide for Claude Code in the SOPilot repository. The shared agent handbook is imported below; this file only adds Claude-specific workflow notes and the list of known doc/code drift. Do not copy handbook content here.

@AGENTS.md

## Where guidance lives

- Mandatory rules: [AGENTS.md](AGENTS.md), [.agent/rules/general.md](.agent/rules/general.md), [.agent/rules/safety-guardrails.md](.agent/rules/safety-guardrails.md), and for any `frontend/web` work [.agent/rules/frontend.md](.agent/rules/frontend.md).
- Specs, plans, ticket status, frontmatter and status conventions: [docs/README.md](docs/README.md). `docs/03-plans/` is the progress source.
- Context index: [.agent/context/README.md](.agent/context/README.md) has a task -> file lookup table. Read the relevant context **before** changing:
  - REST endpoints or gateway routing -> `service-boundaries/responsibilities.md`, `service-boundaries/api-contracts.md`
  - RabbitMQ events -> `service-boundaries/events.md`
  - Tables, columns or queries -> `database/schema.md`, `database/tables/<schema>.md`, `database/erd.mmd`
  - Roles, permissions, login/admission -> `authorization/` (start with `rbac-matrix.md`, `dual-strategy.md`, `google-admission.md`)
  - Uploads, versioning, document status, MinIO -> `storage/document-lifecycle.md`, `storage/minio.md`
  - Frontend state/API integration -> `architecture/frontend.md`
- Tickets and handoffs describe in-flight work, not durable conventions.

## Workflow and definition of done

1. Inspect: read the relevant rules/context/skill and the actual code paths.
2. Plan in proportion to the change (multi-service or contract changes need an explicit plan; follow the service -> gateway -> frontend order in AGENTS.md "Spec-Driven Workflow").
3. Implement minimal, convention-matching changes. Commit or push only when the user asks.
4. Verify with the narrowest meaningful checks: targeted tests, then `validate-build.ps1` for each touched scope; `pre-commit-check.ps1` before proposing a commit.
5. Review your own diff (`git diff`) for scope creep, secrets and debug output.

For UI work, a passing build/lint/typecheck is not visual verification. Say whether the page was actually checked in a browser, and if not, say so.

Report: files changed, commands run with their results, what was not verified, and any docs updated.

## Known doc/code drift (verify before relying on docs)

Code and config issues found while normalizing the specs (2026-10-16). They are not fixed; each needs its own ticket.

- **Roster PUT**: the gateway exposes `PUT /api/v1/users/roster/:id` (`proxy.controller.ts`), but user-service `EmployeeRosterController` has no `@PutMapping`.
- **MinIO bucket**: compose sets `MINIO_BUCKET_NAME=sopilot-documents`, but knowledge-service reads `${MINIO_BUCKET:poliwise-documents}` and ingestion `pipeline.py` only allows `poliwise-documents` and `docs`. Verify the effective bucket at runtime before relying on either name.
- **Exchange name**: ai-qa and ingestion `.env.example` (and some ingestion docstrings) say `poliwise.events`; compose and code use `sopilot.events`. User/auth events still use the legacy `poliwise.user.exchange` / `poliwise.auth.exchange`.
- `user-service` `application.properties` defaults `DB_NAME` to `poliwise_user`; the database is `sopilot`.
- Two migrations share the `005_` prefix (`005_analytics.sql`, `005_conversation_flags.sql`).
- `.agent/context/architecture/frontend.md` describes `frontend/web/middleware.ts`, which does not exist.
- The violation-management components listed in `.agent/context/architecture/system-flows.md` are planned only; no code exists.
- **Reranker never runs**: `ai-qa-service/src/api/routes/chat.py` builds `PipelineOrchestrator()` without `reranker_service`, so `USE_RERANKER` has no effect. RRF scores are not written to `similarity_score`, so the 0.15 threshold compares mixed scales (see `docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md` §5).
- **Embedding provenance**: ingestion `embedding_service.py` hard-codes `EMBEDDING_MODEL_NAME = "BGE_M3"` while the default model is `jina-embeddings-v3`.
- **Retired LLMs (checked 2026-10-17)**: Groq lists `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` as shut down 2026-08-16 for free/developer tiers, `qwen/qwen3-32b` on 2026-07-17 and `llama-guard-3-8b` in 2025; `gemini-2.0-flash` is past its 2026-06-01 shutdown date. Groq calls in the current pipeline likely fail.

Report these when they affect your task; do not silently "fix" them as a side effect.
