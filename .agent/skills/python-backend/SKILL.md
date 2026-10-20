---
name: python-backend
description: Standards and patterns for building SOPilot Python FastAPI microservices.
version: 1.0.0
author: SOPilot Team
---

# Python Backend Skill

This skill provides instructions for developing Python 3.12 + FastAPI microservices within the SOPilot ecosystem (ai-qa-service and ingestion-service).

## When to use this skill
- When creating or modifying Python services (`ai-qa-service`, `ingestion-service`).
- When adding new async endpoints or services.
- When implementing RabbitMQ consumers in Python.
- When working with vector embeddings or document processing.

## Core Instructions

### 1. Module Structure
Follow the standard layout:
- `src/api/`: FastAPI routers (versioned `/api/v1/...`).
- `src/services/`: Business logic classes.
- `src/repositories/`: Database access (async SQLAlchemy).
- `src/models/`: SQLAlchemy models.
- `src/schemas/`: Pydantic v2 request/response models.
- `src/config/`: Settings, database connections, external clients.
- `src/events/`: RabbitMQ consumers and publishers.
- `src/utils/`: Shared utilities.

### 2. Async-First
- All I/O MUST be async. 
- Use `async def` for endpoints, `asyncpg` for DB, `aio-pika` for RabbitMQ, `httpx.AsyncClient` for HTTP. 
- Never use blocking calls (`requests`, `psycopg2`, `time.sleep`) in an async context.

### 3. Data Validation
- Use Pydantic v2 `BaseModel` for all request/response schemas.
- Use `Field()` for validation constraints.
- Use `model_validator` for cross-field validation.
- Return consistent error shapes.

### 4. Database Access
- Use async SQLAlchemy with the `asyncpg` driver.
- Implement the Repository pattern (do not write raw queries in services).
- Schema isolation: `ai-qa` owns the `conversation` schema, `ingestion` accesses the `knowledge` schema.
- Use UUIDs for primary keys.

### 5. Error Handling
- Use `HTTPException` with consistent status codes.
- Use `structlog` for structured logging (not `print` or `logging`).
- Define custom exception classes for domain errors.
- Always handle async task failures (no silent `asyncio.create_task` without an error callback).

### 6. Integration
- **RabbitMQ**: Use `aio-pika` with proper connection pooling and channel management. Use the topic exchange `poliwise.events`. Implement retry logic with dead letter exchanges.
- **MinIO**: Use the async-compatible `minio` SDK wrapper or threadpool if needed.

### 7. Code Quality
- Include type hints on all function signatures.
- Use `ruff` for linting and formatting.
- Dependencies are managed via `uv` (`uv add`, `uv sync`). Do not use `requirements.txt` — use `pyproject.toml`.

## References
- `references/async-patterns.md` - Detailed async patterns used in SOPilot.
- `.agent/context/database.md` - Schema ownership details.
- `CLAUDE.md` - General service rules.
