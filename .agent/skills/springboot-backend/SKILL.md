---
name: springboot-backend
description: Standards and patterns for building SOPilot Spring Boot microservices.
version: 1.0.0
author: SOPilot Team
---

# Spring Boot Backend Skill

This skill provides instructions for developing Java 17 + Spring Boot 3 microservices within the SOPilot ecosystem (Java packages keep the legacy `com.poliwise.*` names).

## When to use this skill
- When creating or modifying backend services in `services/*-service`.
- When adding new database entities or repositories.
- When implementing RabbitMQ event producers or consumers.

## Core Instructions

### 1. Package Structure
Follow the standard layout:
- `config`: Configuration beans and security.
- `controller`: REST endpoints (versioned `/api/v1/...`).
- `service`: Business logic (Interfaces + Impls).
- `repository`: JPA repositories.
- `entity`: Database models.
- `dto`: Request/Response data transfer objects.
- `mapper`: MapStruct or manual mappers between entities and DTOs.

### 2. Database Ownership
- Only modify tables in the schema owned by the service.
- Use UUIDs for primary and foreign keys.
- Audit fields (`createdAt`, `updatedAt`) should be handled automatically via JPA auditing.

### 3. API Design
- Use proper HTTP verbs (GET, POST, PUT, DELETE).
- Return consistent error shapes.
- Use `@Valid` for request validation.

### 4. Integration
- **Events**: Use RabbitMQ for cross-service notifications.
- **Security**: Rely on the API Gateway for JWT validation; services should expect a validated principal or internal security context.

## References
- `.agent/context/database.md` - Schema ownership details.
- `CLAUDE.md` - General service rules.
