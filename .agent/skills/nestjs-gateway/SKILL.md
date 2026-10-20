---
name: nestjs-gateway
description: Standards and patterns for building and maintaining the SOPilot NestJS 11 API Gateway.
version: 1.0.0
author: SOPilot Team
---

# NestJS API Gateway Skill

This skill enforces architecture, coding standards, and operational guidelines for the **SOPilot API Gateway** (`services/api-gateway`).

---

## 1. Role & Technology Stack

- **Framework**: NestJS 11 (Node.js 22 LTS, TypeScript 5.7+)
- **Port**: `3001` (Internal/Docker port `3001`, exposed publicly or behind Nginx)
- **Role**: Single client entry point, reverse proxy, authentication & authorization, rate limiting, circuit breaking, and trace logging.
- **Upstream Downstream Topology**:
  - `auth-service` (Spring Boot: `8081`)
  - `user-service` (Spring Boot: `8082`)
  - `knowledge-service` (Spring Boot: `8083`)
  - `metadata-service` (Spring Boot: `8084`)
  - `feedback-service` (Spring Boot: `8085`)
  - `ai-qa-service` (FastAPI: `8086`)
  - `ingestion-service` (FastAPI: `8088`)

---

## 2. Core Architectural Patterns

### A. Authentication & User Propagation
- **JWT Verification**: Handled via `JwtAuthGuard`.
- **Public Endpoints**: Decorated with `@Public()`.
- **RBAC Roles**: `USER`, `MANAGER`, `ADMIN` (Hierarchy: ADMIN > MANAGER > USER).
  - Use `@Roles('ADMIN')` or `@Roles('MANAGER', 'ADMIN')`.
  - Guard: `RolesGuard`.
- **Downstream Header Injection**: The gateway must unpack validated JWT claims and attach internal headers before proxying requests:
  - `X-User-Id`: User UUID (`sub`)
  - `X-User-Role`: Role (`USER` / `MANAGER` / `ADMIN`)
  - `X-Department-Id`: Department UUID
  - `X-Trace-Id`: Distributed trace UUID v4

### B. Standard Reverse Proxying
```typescript
import { Controller, All, Req, Res, UseGuards } from '@nestjs/common';
import { Request, Response } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { RolesGuard } from '../auth/roles.guard';
import { ProxyService } from './proxy.service';

@Controller('api/v1/documents')
@UseGuards(JwtAuthGuard, RolesGuard)
export class DocumentProxyController {
  constructor(private readonly proxyService: ProxyService) {}

  @All('*')
  async proxy(@Req() req: Request, @Res() res: Response) {
    return this.proxyService.forward(req, res, process.env.KNOWLEDGE_SERVICE_URL);
  }
}
```

### C. Standard Response & Error Format
All errors thrown or returned by downstream services must be normalized through a global `HttpExceptionFilter`:
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Document with id ... not found",
    "details": null
  },
  "timestamp": "2026-09-25T08:00:00.000Z",
  "path": "/api/v1/documents/123",
  "traceId": "c39a8c17-1f48-4cb5-8b3a-5928d32b5f63"
}
```

### D. Streaming Support (SSE)
- When proxying `/api/v1/ai/stream`, pass through the Server-Sent Events headers (`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`) without buffering.

---

## 3. Directory Layout (`services/api-gateway/src`)

```text
src/
├── auth/                 # JWT Auth, Roles guard, decorators (@Public, @Roles)
├── common/
│   ├── decorators/       # Custom parameter decorators (e.g., @CurrentUser)
│   ├── filters/          # Global HttpExceptionFilter
│   ├── interceptors/     # LoggingInterceptor, TraceIdInterceptor, TransformInterceptor
│   └── middleware/       # Correlation ID, security headers
├── config/               # Environment & service endpoint configuration
├── health/               # /health endpoint for Docker & K8s probes
├── proxy/                # Forwarding engine with Axios / http-proxy-middleware
├── main.ts               # Application entry point, Swagger, Pipes, Filters
└── app.module.ts         # Root module
```

---

## 4. Development & Verification Commands

From repository root:
```bash
# Start in watch mode
cd services/api-gateway && pnpm run start:dev

# Build production bundle
cd services/api-gateway && pnpm run build

# Run linter
cd services/api-gateway && pnpm run lint

# Run unit tests
cd services/api-gateway && pnpm run test

# Run e2e tests
cd services/api-gateway && pnpm run test:e2e
```

Or run via centralized script:
```powershell
./scripts/run-tests.ps1 -Scope api-gateway -Type unit
./scripts/validate-build.ps1 -Scope gateway
```
