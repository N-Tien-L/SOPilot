# System Architecture & Technical Specifications
> **V1 LEGACY (frozen):** describes the eight-service V1 stack (gateway, RabbitMQ, `init-db`). For V2 work, the V2 tickets and `docs/02-architecture/designs/TECH-V2-*` win over this file until V2-17 rewrites it. Use it to read and port V1 behaviour, not as the V2 contract.

This document outlines the architectural blueprints, communication patterns, and technical design for the Poliwise platform.

---

## 1. High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                      Client Browser / Web                       │
│                      Next.js 16 (Port 3000)                     │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTP / WebSocket
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API Gateway (NestJS)                      │
│                  Port 3001 | Auth, RBAC, Proxy                  │
└──────────────┬─────────────────────────────┬────────────────────┘
               │ Internal HTTP (JWT/Headers) │ Internal HTTP
       ┌───────┴───────────────┐     ┌───────┴────────────────────┐
       ▼                       ▼     ▼                            ▼
┌──────────────┐        ┌──────────────┐┌────────────────┐ ┌──────────────┐
│ auth-service │        │ user-service ││knowledge-serv. │ │metadata-serv.│
│  Port 8081   │        │  Port 8082   ││   Port 8083    │ │  Port 8084   │
└──────┬───────┘        └──────┬───────┘└────────┬───────┘ └──────┬───────┘
       │                       │                 │                │
       └───────────────────┬───┴─────────────────┴────────────────┘
                           ▼
               ┌───────────────────────┐
               │    RabbitMQ (5672)    │ ◄─── Document / User Events
               └───────────┬───────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                                       ▼
┌──────────────┐                       ┌──────────────┐
│feedback-serv.│                       │ai-qa-service │
│  Port 8085   │                       │  Port 8086   │
└──────────────┘                       └───────┬──────┘
                                               │
                                               ▼
                                       ┌──────────────┐
                                       │ingestion-serv│ (Embeddings, OCR, Chunks)
                                       │  Port 8088   │
                                       └──────────────┘
```

---

## 2. Component Specifications

### 2.1 API Gateway (`services/api-gateway`)
- **Technology**: NestJS 11, TypeScript, `@nestjs/jwt`, `@nestjs/passport`, `http-proxy-middleware`.
- **Core Functionality**:
  - Validates bearer tokens issued by `auth-service`.
  - Enforces RBAC permissions through `@Roles(...)` decorators and `RolesGuard`.
  - Injects authenticated user headers (`X-User-Id`, `X-User-Role`, `X-Department-Id`) before proxying.
  - Normalizes responses and standardizes error formats across all microservices.

### 2.2 Spring Boot Microservices (`services/*-service`)
- **Technology**: Spring Boot 3.4.x, Java 17, Spring Data JPA, Hibernate, PostgreSQL, Flyway.
- **Inter-service Communication**:
  - Synchronous: Spring Cloud OpenFeign for internal direct queries.
  - Asynchronous: Spring AMQP for event-driven workflows over RabbitMQ exchanges and queues.
- **Resilience**: Resilience4j circuit breakers and retry policies for downstream dependencies.

### 2.3 AI & Ingestion Pipeline (`services/ai-qa-service`, `services/ingestion-service`)
- **Technology**: FastAPI, Python 3.11+, PyTorch, HuggingFace Transformers, pgvector.
- **RAG Execution Flow**:
  1. *Input Guard*: Toxic prompt filtering, prompt-injection defense.
  2. *Intent Classifier*: Route queries to FAQ, policy search, or general conversation.
  3. *Hybrid Retrieval*: Combines sparse keyword search (BM25/Postgres text search) with dense vector search (BGE-M3 embeddings in pgvector) using Reciprocal Rank Fusion (RRF).
  4. *Reranker*: Cross-encoder reranking on top candidates.
  5. *Generation*: LLM answer synthesis with strict citation anchors.

---

## 3. Detailed References

For in-depth domain specifications, consult the authoritative documentation in the project `.agent/context/` directory:
- `.agent/context/architecture/`: Detailed system sequence diagrams and architectural decision records (ADRs).
- `.agent/context/service-boundaries/`: Formal service boundary contracts and communication protocols.
- `.agent/context/authorization/`: Detailed RBAC matrix and token claims specification.
- `.agent/context/patterns/`: Monorepo design patterns, error handling, and transaction boundaries.

