# Dependency Analysis Guide

When decomposing plans for SOPilot, tickets must be ordered based on structural dependencies. Proper dependency analysis minimizes blocking and ensures parallel development when possible.

## Microservice Dependency Patterns

### 1. Database and Schema
**Rule:** Database schema changes (`CREATE TABLE`, `ALTER TABLE`) have the highest priority.
- No application logic can be implemented before the underlying data structures exist.
- **Ownership:** Only the service that "owns" the domain should migrate the database. E.g., `user-service` owns the `user_db` schema.

### 2. Event-Driven Workflows (RabbitMQ)
**Rule:** Producers before Consumers (usually).
- It's easier to verify a consumer if the producer is already emitting events (or at least if the contract/DTO is merged).
- If parallelizing, create a shared DTO/Contract ticket first that both producer and consumer tickets depend on.

### 3. API Gateway Routing (NestJS)
**Rule:** Backend services before Gateway.
- The Gateway simply routes traffic. Implement the actual Spring Boot / FastAPI endpoints first, then add the Gateway routes.
- The Frontend should depend on the Gateway ticket.

### 4. Frontend vs. Backend
**Rule:** API Contracts before UI.
- The frontend Next.js application relies on the Gateway APIs.
- The UI can be built with mocked data, but integration requires the backend to be done.
- Standard flow: DB → Backend Service → Gateway → Frontend.

## How to Order Tickets

1. **Phase 1: Foundation (DB & Interfaces)**
   - Database migrations.
   - Core entity models.
   - Event contracts (DTOs).

2. **Phase 2: Core Logic (Backend)**
   - Repository, Service, and Controller layers in Spring Boot or FastAPI.
   - RabbitMQ Producers and Consumers.

3. **Phase 3: Exposure (Gateway & Auth)**
   - Adding routes to the NestJS Gateway.
   - Securing endpoints (Auth service integrations).

4. **Phase 4: Consumption (Frontend & External)**
   - Next.js UI implementation.
   - API client updates.
