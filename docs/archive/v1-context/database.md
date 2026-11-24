# Database Ownership & Schema Architecture
> **V1 LEGACY (frozen):** describes the eight-service V1 stack (gateway, RabbitMQ, `init-db`). For V2 work, the V2 tickets and `docs/02-architecture/designs/TECH-V2-*` win over this file until V2-17 rewrites it. Use it to read and port V1 behaviour, not as the V2 contract.

> **Notice:** This project was originally codenamed *Poliwise* and has been unified under the product name **SOPilot**.
> PostgreSQL database is named `sopilot` (user: `sopilot`). The application schemas are strictly partitioned by domain: `core`, `metadata`, `knowledge`, `conversation`, `analytics`.

SOPilot strictly adheres to a **database-per-service (isolated schema)** ownership model within PostgreSQL. Cross-schema references are decoupled via UUID identifiers and event-driven data synchronization.

---

## 1. Ownership Model

| Schema | Owner Service | Port | Primary Entities & Responsibilities |
|---|---|---|---|
| `core` | `auth-service` & `user-service` | 8081 / 8082 | Accounts, Credentials, Refresh Tokens, Blacklists, Login History, Profiles, Departments, Employee Roster |
| `knowledge` | `knowledge-service` | 8083 | Documents, Versions, Chunks, Embeddings, Processing Jobs |
| `metadata` | `metadata-service` | 8084 | Categories, Tags, Document Access Rules, Audit Policies |
| `analytics` | `feedback-service` | 8085 | User Feedback, Daily Aggregates, Unanswered Questions, Audit Logs |
| `conversation` | `ai-qa-service` | 8086 | Chat Sessions, Messages, Citations, Intent Classification Logs |
| *(None)* | `ingestion-service` | 8088 | Stateless processing worker (uses MinIO & RabbitMQ queues) |

---

## 2. Cross-Service Boundaries & Rules

1. **No Cross-Schema Foreign Keys**:
   - Foreign key constraints must NEVER cross schema boundaries.
   - For example, `knowledge.documents` references `created_by` (UUID) but does NOT hold a hard FK against `core.users`.
2. **Document Linkage**:
   - `knowledge-service` owns physical document metadata and storage references.
   - `metadata-service` owns categorization, tags, and RBAC visibility rules.
   - When a document is modified or deleted, an event is emitted on RabbitMQ to synchronize metadata state.
3. **User Identity Propagation**:
   - `auth-service` authenticates credentials and mints JWTs containing `sub` (user UUID), `role`, `departmentId`, and `email`.
   - Downstream services trust validated claims extracted by `api-gateway` and passed via internal request headers (`X-User-Id`, `X-User-Role`, `X-Department-Id`).

---

## 3. Schema Migrations & Modifications

When introducing schema changes:
1. Add new migration scripts under `infrastructure/init-db/`.
2. Update JPA entity models in the corresponding Spring Boot service (or SQLAlchemy/Pydantic models in Python services).
3. Update this document and related context files in `.agent/context/database/`.
4. Ensure API contracts in `api-gateway` and `frontend/web` reflect changed payload shapes.
