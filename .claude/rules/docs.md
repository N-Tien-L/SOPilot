---
paths:
  - "docs/**"
---

# Documentation (`docs/`)

Conventions: `docs/README.md` ("Conventions"). Templates: `docs/templates/`. Workflow: skill `project-docs`.

- English. `author: "Owner"`. Never an AI name, tool or invented role as author.
- Kind is decided by folder. Use only the statuses listed for that kind. Tickets use `in_progress` (underscore).
- Never change an existing id, and never renumber TECH/ADR sections: code and immutable migrations cite them (`TECH-V2-ai-service §7.5`). Add new sections at the end.
- One source of truth per fact. Link to the ADR, design, service README or code; do not paste it.
- Separate implemented from planned. Never mark a design as implemented, or a ticket as `done`, without evidence. `approved`/`done`/`final` are the owner's call.
- `docs/archive/**` is read-only history. Do not edit it except to fix a link broken by a move.
- Before finishing: `./scripts/docs/check-docs.ps1` must print `docs check passed`.
