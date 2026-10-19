# Service Type Guide

Quick reference for the different service types in SOPilot.

## Java (Spring Boot)
- **Framework**: Spring Boot 3, Java 17, Maven
- **Structure**: Controller → Service → Repository
- **Key Patterns**:
  - DTO Records for request/response payloads.
  - MapStruct for object mapping between entities and DTOs.
  - Spring ApplicationEvents for asynchronous event publishing.
- **Key Directories**: `src/main/java`, `src/main/resources`, `src/test/java`
- **Testing**: JUnit 5, Mockito, Testcontainers for integration testing.

## Python (FastAPI)
- **Framework**: FastAPI, Python 3.12, uv package manager
- **Structure**: Module-based architecture (routers, dependencies, services).
- **Key Patterns**:
  - Async/await for all IO operations.
  - Pydantic models for validation.
  - Dependency Injection via FastAPI `Depends`.
- **Key Directories**: `src/api`, `src/core`, `src/services`
- **Testing**: Pytest, AsyncMock.

## TypeScript (NestJS)
- **Framework**: NestJS 11, Node.js, pnpm
- **Structure**: Module-based (Controllers, Providers, Modules).
- **Key Patterns**:
  - Guards for authentication/authorization.
  - Interceptors for response transformation/logging.
  - Pipes for validation and transformation (class-validator, class-transformer).
- **Key Directories**: `src/modules`, `src/common`
- **Testing**: Jest, Supertest.

## TypeScript (Next.js)
- **Framework**: Next.js 16, React 19, pnpm
- **Structure**: App Router architecture.
- **Key Patterns**:
  - Server vs Client Components (use `"use client"` sparingly).
  - Zustand for global client state.
  - React Query for data fetching and caching.
- **Key Directories**: `app`, `components`, `lib`, `store`
- **Testing**: Vitest, React Testing Library.
