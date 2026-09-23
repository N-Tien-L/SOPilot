---
title: System Architecture Overview
description: High-level architecture of the Poliwise AI-powered Enterprise Knowledge Platform
type: architecture
version: 1.0
---

# System Architecture Overview

## Purpose

This document provides AI agents with a comprehensive understanding of the Poliwise system architecture, component interactions, and design patterns. Use this as the primary reference when implementing features or making architectural decisions.

## When to Use

Consult this document before:
- Implementing new features
- Making architectural decisions
- Understanding service boundaries
- Debugging cross-service issues

## System Essence

**Poliwise** is an AI-powered Enterprise Knowledge Platform designed for enterprises. It enables employees to ask natural-language questions about company policies, HR procedures, and internal documents, receiving AI-generated answers with source citations.

**Key Characteristics:**
- Microservices architecture with API Gateway
- Event-driven asynchronous communication via RabbitMQ
- Single PostgreSQL database with schema-per-service separation
- AI/ML workloads in Python (FastAPI) separate from business logic (Spring Boot)
- English language-first design

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | Next.js (App Router) | 16.1.6 | React-based web UI |
| | React | 19.2.3 | UI framework |
| | TypeScript | 5.x (strict) | Type safety |
| | Zustand | 5.x | State management |
| | Tailwind CSS | 4.x | Styling |
| **API Gateway** | NestJS | 11.x | Single entry point |
| | TypeScript | 5.7.x | Language |
| **Microservices** | Spring Boot | 3.4.3 | Business logic |
| | Java | 17 | Runtime |
| | Spring Cloud | 2024.0.3 | Service communication |
| **AI Services** | Python FastAPI | 0.115+ | ML/ML workloads |
| | HuggingFace TEI | 1.5.x | Model serving |
| **Database** | PostgreSQL | 16-alpine | Primary data store |
| | pgvector | latest | Vector embeddings |
| **Message Queue** | RabbitMQ | 3.13-management | Event bus |
| **Infrastructure** | Docker Compose | v2 | Container orchestration |
| **Document Editor** | OnlyOffice DS | 8.1.0 | Collaborative document editing |

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Client (Browser)                       │
│            Next.js 16 (App Router) + React 19              │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP (port 3001)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (NestJS) :3000               │
│   JWT validation, RBAC, rate limiting, proxy, tracing     │
└───────┬────────────┬────────────┬────────────┬────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
 ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
 │ Auth    │ │ User    │ │Kgnl·   │ │Meta·    │ ...
 │ Service │ │ Service │ │Service  │ │Service  │
 │ 8081    │ │ 8082    │ │ 8083    │ │ 8084    │
 └─────────┘ └─────────┘ └─────────┘ └─────────┘
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
┌───────────────────────────────────────────────────────────┐
│            PostgreSQL 16 (single DB, multi-schema)         │
│  core│public│knowledge│metadata│conversation│analytics   │
└───────────────────────────────────────────────────────────┘
        │            │            │
        │            │            └──────────────┐
        │            │                         │
        ▼            ▼                         ▼
┌─────────────┐ ┌─────────────┐   ┌──────────────────────────┐
│Embedding    │ │Ingestion    │   │      AI Q&A Service      │
│Service      │ │Service      │   │      (FastAPI) :8086     │
│:8001        │ │:8088        │   │                          │
│BGE-M3 ONNX  │ │Extraction,  │   │  Query → LLM → Response  │
│             │ │Chunking,    │   │                          │
└─────────────┘ │Embedding    │   └──────────────────────────┘
                │             │              ▲
                └─────────────┘              │
                       │                    │
                       └────────────────────┘
                              RabbitMQ (events)
```

## Database Schema Strategy

The system uses a **single PostgreSQL database** separated into **5 logical schemas** to maintain domain boundaries and enforce service autonomy.

| Schema | Owner Service | Primary Purpose | Tables |
|--------|--------------|-----------------|--------|
| `core` | `auth-service` | User authentication, roles, permissions | `users`, `departments`, `user_profiles`, `refresh_tokens`, `login_history` |
| `public` (default) | `user-service` | User profiles, department data | `user_profiles` (duplicate from core), `departments` (duplicate from core) |
| `knowledge` | `knowledge-service` & `ingestion-service` | Document storage, chunks, embeddings | `documents`, `document_versions`, `chunks`, `processing_jobs`, `embedding_cache` |
| `metadata` | `metadata-service` | Document metadata, categories, access rules | `document_metadata`, `categories`, `tags`, `document_tags`, `document_access_rules` |
| `conversation` | `ai-qa-service` | Chat history, messages, citations | `conversations`, `messages`, `unanswered_questions` |
| `analytics` | `feedback-service` | Feedback, usage logs, statistics | `feedbacks`, `usage_stats`, `audit_logs`, `daily_aggregates`, `popular_questions`, etc. |

### AI Service Ownership Details

- **`ai-qa-service`** (port 8086):
  - Owns: `conversation` schema (writes), `analytics` schema (writes)
  - Reads: `knowledge` schema (chunks), `metadata` schema (document metadata)
  
- **`ingestion-service`** (port 8088):
  - Owns: `knowledge` schema writes (chunks, documents, processing_jobs)
  - Reads: `metadata` schema (access rules)

- **`embedding-service`** (port 8001):
  - Standalone model server (BGE-M3)
  - No database ownership
  - Called by `ingestion-service`

## Data Flow Patterns

### 1. Authentication Flow

```
Client → Gateway (/auth/*) → auth-service (JWT, sessions) → Postgres (core)
```

- Client sends credentials to `/api/v1/auth/login`
- Gateway forwards to `auth-service:8081`
- Service validates, creates JWT + refresh token
- Returns tokens to client
- All subsequent requests include `Authorization: Bearer <token>`

### 2. User Query (AI Q&A)

```
Client (with JWT) → Gateway (/api/v1/ai/*) → ai-qa-service → hybrid search on knowledge.chunks → LLM → answer
```

1. Client sends query with JWT
2. Gateway validates JWT, injects headers: `X-User-Id`, `X-Role`, `X-Department-Id`, `X-Trace-ID`
3. AI service receives query, calls embedding service for query vector
4. Performs hybrid search (dense + sparse) on `knowledge.chunks` with ACL filters
5. Retrieves top-k chunks, reranks with BGE-Reranker
6. Builds context, calls LLM (OpenRouter or Lightning AI)
7. Streams response back via SSE
8. Saves conversation to `conversation` schema

### 3. Document Ingestion Pipeline

```
Admin upload → Gateway → knowledge-service (save file + DB) → RabbitMQ → ingestion-service (processing) → knowledge.chunks
```

Steps:
1. Admin uploads document via UI
2. Gateway validates JWT (Admin role), forwards to `knowledge-service:8083`
3. Knowledge service:
   - Uploads file to MinIO
   - Creates `knowledge.documents` record
   - Creates `knowledge.document_versions` record
   - Creates `knowledge.processing_jobs` record (status: PENDING)
   - Fetches metadata from `metadata-service` (access rules, categories)
   - Publishes `ingestion.requested` event to RabbitMQ with full payload
4. Ingestion service (Python) consumes event:
   - Downloads file from MinIO
   - Extracts text (PyMuPDF, python-docx, pytesseract, markdown)
   - Standardizes (Markdown heading detection)
   - Chunks (parent-child strategy)
   - Generates embeddings (BGE-M3 via LitServe)
   - Inserts chunks into `knowledge.chunks` with flattened ACL fields
   - Updates `knowledge.documents` with extraction metadata
   - Marks job COMPLETED
   - Publishes `document.uploaded` event

### 4. Permission Update Flow (Background Sync)

```
Admin updates permissions in UI → metadata-service updates document_access_rules → publishes event → ingestion-service updates knowledge.chunks ACLs
```

1. Admin modifies document permissions via UI
2. Metadata service updates `metadata.document_access_rules`
3. Publishes `document.permissions.changed` event (or similar)
4. Ingestion service (or a dedicated sync service) consumes event:
   - Recalculates flattened ACL arrays from `metadata.document_access_rules`
   - Executes `UPDATE knowledge.chunks SET allowed_roles = ..., allowed_departments = ... WHERE document_id = X`
5. Eventual consistency: chunks reflect new permissions within seconds

## Important Invariants

These rules **MUST** be followed at all times:

1. **API Gateway is Global**: Every client request must pass through the gateway. Services are never exposed directly to clients.

2. **Database Schema Boundaries**: Each service owns exactly one schema. **NO CROSS-SCHEMA SQL JOINS**. Use HTTP/RPC or events for cross-service data.

3. **Event-Driven Communication**: All asynchronous service communication uses RabbitMQ via the `poliwise.events` exchange.

4. **JWT Propagation**: Gateway always injects `X-User-Id`, `X-Role`, `X-Department-Id`, `X-Trace-ID` headers to downstream calls. Services trust these headers as authoritative.

5. **AI Read-Optimized ACL**: `knowledge.chunks` stores flattened `allowed_roles`, `allowed_departments`, `access_level` for fast filtering during vector search. This is an eventually consistent duplicate of the source-of-truth `metadata.document_access_rules`.

6. **Stateless Services**: No session affinity. Services must be horizontally scalable.

7. **Soft Deletes**: Tables with `deleted_at` column MUST always include `WHERE deleted_at IS NULL` in queries unless explicitly fetching deleted records.

8. **Vector Search Syntax**: Always use the `<=>` operator (cosine similarity) for `pgvector`. Never use regular operators on embedding columns.

9. **Knowledge.chunks Immutability**: `knowledge.chunks` is append-only with `is_latest` flag. Never UPDATE or DELETE chunks directly. Use soft invalidation:
   ```sql
   UPDATE knowledge.chunks SET is_latest = false WHERE document_id = :id AND is_latest = true;
   ```
   Then insert new versioned chunks.

10. **MinIO for File Storage**: Original files are never deleted from MinIO. Keep for re-processing and audit trail.

## Service Map Reference

| Service | Port | Technology | Primary Responsibility | Schema Ownership |
|---------|------|------------|----------------------|------------------|
| `frontend/web` | 3001 | Next.js | Web UI | — |
| `api-gateway` | 3000 | NestJS | JWT validation, RBAC, proxy, rate limiting, circuit breaking, tracing | — |
| `auth-service` | 8081 | Spring Boot | Login, JWT lifecycle, refresh tokens, login history | `core` |
| `user-service` | 8082 | Spring Boot | User profiles, departments, account status | `public` |
| `knowledge-service` | 8083 | Spring Boot | Document storage, file management, processing job tracking, OnlyOffice editing | `knowledge` (reads only) |
| `metadata-service` | 8084 | Spring Boot | Document metadata, categories, tags, access rules | `metadata` |
| `feedback-service` | 8085 | Spring Boot | Feedback, usage stats, analytics, audit logs | `analytics` |
| `ai-qa-service` | 8086 | FastAPI | Query processing, retrieval orchestration, LLM generation, conversation management | `conversation`, `analytics` (reads `knowledge`, `metadata`) |
| `ingestion-service` | 8088 | FastAPI | Document extraction, chunking, embedding generation, vector indexing | `knowledge` (writes) |
| `embedding-service` | 8001 | HuggingFace TEI | BGE-M3 embedding model serving | — |

## Cross-Service Communication Rules

### Synchronous (HTTP via API Gateway)

All service-to-service HTTP calls **must**:
- Go through the API Gateway (except AI service internal calls for performance)
- Include the original user context headers (`X-User-Id`, `X-Role`, `X-Department-Id`, `X-Trace-ID`)
- Use the service's configured base URL from environment

Example:
```typescript
// Inside any service (Node.js)
const response = await axios.get(`${USER_SERVICE_URL}/api/v1/users/me`, {
  headers: {
    'X-User-Id': userId,
    'X-Role': userRole,
    'X-Department-Id': departmentId,
    'X-Trace-ID': traceId
  }
});
```

### Asynchronous (RabbitMQ Events)

All events go through the `poliwise.events` topic exchange.

**Event Contract Standard:**
```json
{
  "event_type": "document.uploaded",
  "timestamp": "2024-01-15T10:30:00Z",
  "payload": {
    // Event-specific fields
  }
}
```

See `contexts/service-boundaries/events.md` for complete event catalog.

## Configuration & Environment

All services use environment variables for configuration. Common patterns:

### Database
```env
DATABASE_URL=postgresql+asyncpg://poliwise:poliwise_secure_password@postgres:5432/poliwise
DATABASE_SCHEMA=knowledge  # or core, metadata, conversation, analytics
```

### RabbitMQ
```env
RABBITMQ_URL=amqp://poliwise:poliwise_secure_password@rabbitmq:5672
RABBITMQ_EXCHANGE=poliwise.events
```

### Service URLs (for calling other services)
```env
AUTH_SERVICE_URL=http://localhost:8081
USER_SERVICE_URL=http://localhost:8082
KNOWLEDGE_SERVICE_URL=http://localhost:8083
METADATA_SERVICE_URL=http://localhost:8084
FEEDBACK_SERVICE_URL=http://localhost:8085
AI_QA_SERVICE_URL=http://localhost:8086
INGESTION_SERVICE_URL=http://localhost:8088
```

### JWT
```env
JWT_SECRET=your-256-bit-secret-key-here
JWT_EXPIRY=900  # 15 minutes
JWT_REFRESH_EXPIRY=604800  # 7 days
```

### AI/ML Specific
```env
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_URL=http://localhost:8001
RERANKER_URL=http://localhost:8002
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-...
LLM_MODEL=qwen/qwen-2.5-7b-instruct
```

## Critical Implementation Guidelines

### When Adding a New Feature

1. **Determine service ownership**: Consult the Service Map above. Which service should own this data/functionality?
2. **Check database boundaries**: Does it need a new table? Add to the correct schema.
3. **Define API contracts**: If cross-service, document endpoints or events needed.
4. **Update this document**: Keep architecture docs current.

### Prohibited Patterns (Anti-Patterns)

- ❌ Direct service-to-service HTTP calls bypassing gateway (except AI services)
- ❌ Cross-schema SQL joins
- ❌ Modifying another service's tables
- ❌ Implementing ingestion logic in `knowledge-service` (belongs to `ingestion-service`)
- ❌ Putting business logic in API Gateway (beyond routing/guards)
- ❌ Hardcoding service URLs (use environment variables)
- ❌ Bypassing JWT validation (always use gateway or auth guard)

## Deployment Topology

```
┌─────────────┐
│   Client    │ (Browser / Mobile)
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────┐
│  Load Balancer  │ (nginx, HAProxy, or cloud LB)
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│  API Gateway     │ (multiple instances, port 3000)
│  NestJS           │
└────────┬─────────┘
         │
    ┌────┴────┬────┬────┬────┬────┬────┐
    ▼         ▼    ▼    ▼    ▼    ▼    ▼
┌─────┐ ┌─────┐ ... ┌────────────┐
│Auth │ │User │     │   AI       │
│8081 │ │8082 │     │  Services  │
└─────┘ └─────┘     └────────────┘
         │                   │
         └───────────────────┘ (internal network)
                │
                ▼
        ┌──────────────┐
        │ PostgreSQL   │ (single instance or cluster)
        │ 16 + pgvector│
        └──────────────┘
                │
                ▼
        ┌──────────────┐
        │  RabbitMQ    │
        │  3.13+       │
        └──────────────┘
```

**Network Rules:**
- Gateway is the only public-facing service
- All other services communicate on internal Docker network
- Database and RabbitMQ are firewalled from external access
- Services discover each other via Docker DNS (`service-name:port`)

## Scaling Considerations

| Service | Scaling Strategy |Notes |
|---------|-----------------|------|
| `api-gateway` | Horizontal (multiple instances) | Stateless, session-independent |
| `auth-service` | Horizontal | JWT stateless, DB connection pool sizing |
| `user-service` | Horizontal | Read-heavy, consider read replicas |
| `ai-qa-service` | Horizontal + GPU | CPU-bound (LLM) + GPU (embedding/rerank) |
| `ingestion-service` | Limited (2-4 workers) | Resource-intensive, batch processing |
| `embedding-service` | GPU instances | GPU memory bound, batch size tuning |

## References

- **Database Schema**: `contexts/database/schema.md` - complete table definitions
- **Authorization**: `contexts/authorization/dual-strategy.md` - ACL patterns
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md` - ownership matrix
- **AI Architecture**: `contexts/architecture/ai-service-architecture.md` - detailed AI pipeline design
- **Development Plans**: `contexts/development/extraction-plan.md` - implementation roadmap

---

**Last Updated**: 2026-05-05
**Maintained By**: Architecture Team
