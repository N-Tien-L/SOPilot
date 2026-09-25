# SOPilot Database Setup & Schema Management (`infrastructure/init-db/`)

The **SOPilot** platform uses a single PostgreSQL 16 database with the `pgvector` extension (`sopilot`), strictly partitioned into 5 domain schemas:
- `core`: Users, user profiles, authentication, departments, and pre-provisioned employee roster.
- `metadata`: Categories, tags, and document metadata/visibility rules.
- `knowledge`: Documents, text chunks, vector embeddings (pgvector), and processing jobs.
- `conversation`: Q&A chat sessions, messages, and retrieval traces.
- `analytics`: Feedback, audit logs, and unanswered question tracking.

---

## 🏗️ Architecture & Migration Mechanism

Database schemas are managed via **Numbered Additive SQL Scripts** mounted to the PostgreSQL Docker entrypoint (`/docker-entrypoint-initdb.d/`).

When the database container starts with a fresh volume, PostgreSQL executes all `.sql` scripts in alphabetical order:
1. `000_bootstrap.sql`: Creates the 5 schemas and enables extensions (`uuid-ossp`, `pgcrypto`, `vector`, `pg_trgm`).
2. `001_core.sql`: Core identity, credentials, roles, departments, user profiles.
3. `002_metadata.sql`: Categories, tags, document metadata.
4. `003_knowledge.sql`: Documents, chunks, vector embeddings.
5. `004_conversation.sql`: Conversations, chat messages.
6. `005_analytics.sql` & `005_conversation_flags.sql`: Feedbacks, flags, unanswered questions.
7. `006_functions_triggers.sql`: Shared triggers for automatic `updated_at` management.
8. `007_seed_data.sql`: Seed data for system administrator and default departments.
9. `008_ai_indexes.sql`: HNSW / IVFFLAT indexes for fast similarity search.
10. `009_document_locks.sql`: Collaborative document lock management.
11. `010_employee_roster.sql`: Pre-provisioned employee whitelist for Google 1-Click JIT onboarding.

> **Note on Microservice Hibernate Validation:**
> Spring Boot services (`auth-service`, `user-service`, `knowledge-service`, `metadata-service`, `feedback-service`) run with `spring.jpa.hibernate.ddl-auto: validate`. The database schema is the single source of truth; applications validate that entities match the schema without modifying tables.

---

## 🚀 Quick Start & Bootstrap

### 1. Start Infrastructure

```powershell
docker compose up -d postgres rabbitmq minio redis
```

### 2. Verify Database Schemas

```powershell
docker compose exec -T postgres psql -U sopilot -d sopilot -c "\dn"
```

Expected output: `analytics`, `conversation`, `core`, `knowledge`, `metadata`, `public`.

### 3. Verify Tables & Seed Data

```powershell
docker compose exec -T postgres psql -U sopilot -d sopilot -c "SELECT COUNT(*) AS users FROM core.users;"
docker compose exec -T postgres psql -U sopilot -d sopilot -c "SELECT COUNT(*) AS categories FROM metadata.categories;"
docker compose exec -T postgres psql -U sopilot -d sopilot -c "SELECT COUNT(*) AS roster FROM core.employee_roster;"
```

---

## 🔄 Reset & Re-Bootstrap

To cleanly reset the local PostgreSQL volume and re-run all initialization scripts from scratch, use the repository script:

```powershell
./infrastructure/init-db/reset-and-bootstrap.ps1
```

Or run with `-Force` to skip confirmation:

```powershell
./infrastructure/init-db/reset-and-bootstrap.ps1 -Force
```
