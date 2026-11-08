---
paths:
  - "services/auth-service/**"
  - "services/user-service/**"
  - "services/knowledge-service/**"
  - "services/metadata-service/**"
  - "services/feedback-service/**"
  - "services/ai-qa-service/**"
  - "services/ingestion-service/**"
  - "services/api-gateway/**"
  - "infrastructure/init-db/**"
  - "docker-compose.yml"
---

# V1 is frozen (remove this file at V2-17)

These paths are the eight-service V1 stack (codename *Poliwise*: `com.poliwise.*`, `poliwise.*` exchanges). Read them to port behaviour into `core-api`/`ai-service`. Do not extend, fix or refactor them unless a ticket says so. Edits prompt for approval (`permissions.ask`). V2-17 removes them after the parity check.

- Old commands: `./scripts/validate-build.ps1 -Scope auth|user|knowledge|metadata|feedback|ai-qa|ingestion|gateway`, `./scripts/run-tests.ps1 -Scope <name>-service|api-gateway`. CI job "V1 (frozen)" in `ci.yml` keeps them green.
- `infrastructure/init-db/reset-and-bootstrap.ps1` deletes the V1 Postgres volume. Run it only on the user's explicit request (`permissions.ask`).
- `.agent/context/*` files marked "V1 LEGACY" describe this stack, not the V2 contract.

## Known V1 drift (found 2026-10-16/17, not fixed; port carefully)

- Gateway exposes `PUT /api/v1/users/roster/:id`; user-service has no `@PutMapping`.
- MinIO bucket: compose `sopilot-documents` vs knowledge-service default `poliwise-documents`; ingestion allows only `poliwise-documents`/`docs`.
- Exchange: ai-qa/ingestion `.env.example` say `poliwise.events`; code uses `sopilot.events`; user/auth still use `poliwise.user.exchange`/`poliwise.auth.exchange`.
- user-service `DB_NAME` defaults to `poliwise_user`; the database is `sopilot`.
- Two init-db migrations share prefix `005_`.
- ai-qa reranker never runs (`chat.py` builds `PipelineOrchestrator()` without `reranker_service`); RRF scores vs 0.15 threshold mix scales (AUDIT-v2-baseline §5).
- ingestion `EMBEDDING_MODEL_NAME = "BGE_M3"` while the default model is `jina-embeddings-v3`.
- Groq `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, `qwen/qwen3-32b`, `llama-guard-3-8b` and `gemini-2.0-flash` are retired (checked 2026-10-17); V1 Groq calls likely fail.
