---
title: API Contracts & Standards
description: Standardized API response formats, error codes, and authentication requirements for all Poliwise services
type: service-boundaries
version: 1.0
---

# API Contracts & Standards

> **V2 core-api contract** (TECH-V2-core-api §5.0, implemented in V2-11): success
> `{"data": ..., "traceId": "..."}`; error `{"error": {"code", "message", "details"}, "traceId"}` with
> fixed messages (never `e.getMessage()`, A8); `X-Trace-Id` accepted (8–64 `[A-Za-z0-9-]`) or generated and
> echoed. Codes so far: `400 VALIDATION_FAILED` (details list field names only), `401 INVALID_GOOGLE_TOKEN`,
> `403 MEMBERSHIP_SUSPENDED`, `404 NOT_FOUND`, `405 METHOD_NOT_ALLOWED`, `415 UNSUPPORTED_MEDIA_TYPE`,
> `500 INTERNAL_ERROR`. Access token: RS256, ≤ 15 min, claims `sub, wid, wrole, wdept, jti, iat, exp`,
> `iss=sopilot-core`, `aud=[sopilot-core, sopilot-ai]`, keys at `/.well-known/jwks.json`.
> **V2-12/V2-23 additions** (all need `Authorization: Bearer`; workspace and role come from the token only, never
> from path or body; another workspace's object is `404`): `GET/POST /api/v1/departments`, `PATCH/DELETE
> /api/v1/departments/{id}` (`409 DEPARTMENT_NAME_TAKEN`, `409 DEPARTMENT_IN_USE` with counts);
> `GET /api/v1/members`, `GET /members/me`, `PATCH /members/{userId}` (profile + department), `POST
> /members/{userId}/suspend|reactivate`, `DELETE /members/{userId}`, `POST /members/leave` (`409 LAST_OWNER`,
> `409 EMPLOYEE_CODE_TAKEN`, `409 DEPARTMENT_ARCHIVED`); `POST /api/v1/documents` (multipart `file`, 20 MB, PDF or
> Markdown only: `415 UNSUPPORTED_TYPE|INVALID_ENCODING`, `413 FILE_TOO_LARGE`, `409 DUPLICATE_DOCUMENT|
> QUOTA_EXCEEDED`), `POST /documents/{id}/versions` (`409 VERSION_IN_PROGRESS|DOCUMENT_UNCHANGED`), `POST
> /documents/{id}/retry` (`409 VERSION_NOT_FAILED`), `GET /documents` (cursor page), `GET /documents/{id}`, `PATCH
> /documents/{id}` (title, description, language), `GET /documents/{id}/download-url|versions`, `DELETE
> /documents/{id}`; `GET /api/v1/audit-logs` (OWNER). `PATCH /internal/documents/{id}/versions/{versionId}/status`
> (header `X-Internal-Token`) is ai-service's callback (TECH-V2-core-api section 8.2). Lists use
> `{"data": [...], "page": {"cursor", "hasMore"}, "traceId"}`.
> **ai-service (V2-09, V2-10; `/ai/v1/**`, same Bearer token, ai-service verifies it through JWKS; another user's or
> workspace's conversation is `404`):** `GET /documents/{id}/versions/{versionId}/content`;
> `POST /conversations/{id|new}/messages` body `{content, lang?}` answers with `text/event-stream`
> (events `meta`, `delta`, `replace`, `refusal`, `citations`, `done`, `error`; TECH-V2-ai-service §7.2; `error` codes
> `QUOTA_EXCEEDED`, `LLM_UNAVAILABLE`, `INTERNAL_ERROR`, fixed text); `GET /conversations`, `GET /conversations/{id}`
> (an answer generated from a document no longer readable, i.e. any source in its LLM context or any citation,
> comes back as `{hidden: true, reason: ACCESS_REVOKED|
> DOCUMENT_DELETED}`), `PATCH /conversations/{id}` (title), `DELETE /conversations/{id}` (soft). These routes use plain
> JSON, not the core-api `{"data", "traceId"}` envelope. `503` when the LLM endpoint or embedding model is not
> configured (the first question builds them).
> **Feedback and knowledge gaps (V2-13, TECH-V2-ai-service §7.6):** `PUT /messages/{id}/feedback` `{vote: -1|1,
> comment?}` → `204` (conversation owner, `ASSISTANT` message only, one vote per user, else `404`);
> `GET /knowledge-gaps?status=open|resolved&limit&offset` (OWNER/ADMIN, MEMBER `403`; PII-masked question, no asker
> identity); `POST /knowledge-gaps/{messageId}/resolve` `{note?}` (OWNER/ADMIN, idempotent, `404` if not a gap).
> Core-api callback `PUT /internal/documents/{id}/suggestions` (V2-25) stores and applies metadata suggestions.
> The rest of this file describes frozen V1 (gateway, `ApiResponse` with `success`).

## Purpose

This document defines the **standardized API contracts** that all Poliwise services must follow. It covers:
- Request/response formats
- Error handling standards
- Authentication requirements per endpoint
- Rate limiting policies
- Pagination conventions
- Health check endpoints

## When to Use

- Designing new service endpoints
- Implementing API clients
- Debugging API issues
- Ensuring consistency across services

---

## Standard Response Format

All successful API responses **must** follow this envelope:

```json
{
  "success": true,
  "data": {
    // Primary response payload
  },
  "message": "Optional human-readable message",
  "timestamp": "2024-01-15T10:30:00Z",
  "traceId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Fields**:
- `success` (boolean): Always `true` for 2xx responses, `false` for 4xx/5xx
- `data` (object|array): Primary payload. For collections, include items array and pagination metadata
- `message` (string|null): Optional success message or warning
- `timestamp` (ISO-8601): Response generation time in UTC
- `traceId` (UUID): Request trace ID for debugging (propagated from gateway)

### Examples

**Single Resource**:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "HR Policy 2024",
    "status": "PUBLISHED"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "traceId": "trace-uuid"
}
```

**Paginated List**:
```json
{
  "success": true,
  "data": {
    "items": [
      { "id": "...", "title": "..." },
      { "id": "...", "title": "..." }
    ],
    "total": 150,
    "page": 1,
    "pageSize": 20,
    "totalPages": 8
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "traceId": "trace-uuid"
}
```

---

## Error Response Format

All error responses **must** follow this format:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "message": "must be valid email address" },
      { "field": "password", "message": "must be at least 8 characters" }
    ],
    "traceId": "trace-uuid",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Fields**:
- `success`: Always `false`
- `error.code`: Machine-readable error code (defined below)
- `error.message`: Human-readable description
- `error.details` (optional): Array of field-level errors
- `error.traceId`: Request trace ID
- `error.timestamp`: When error occurred

### Standard Error Codes

| Code | HTTP Status | Description | When to Use |
|------|-------------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT token | Token expired, malformed, or absent on protected route |
| `FORBIDDEN` | 403 | Insufficient permissions | User lacks required role or permission |
| `VALIDATION_ERROR` | 400 | Request body validation failed | DTO validation errors, missing required fields |
| `NOT_FOUND` | 404 | Resource not found | Document, user, or entity doesn't exist |
| `CONFLICT` | 409 | Resource conflict | Duplicate username/email, business rule violation |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Rate limit exceeded, include `Retry-After` header |
| `SERVICE_UNAVAILABLE` | 503 | Downstream service unavailable | Circuit breaker open, service down |
| `INTERNAL_ERROR` | 500 | Unexpected server error | Unhandled exception, log full stack trace |
| `BAD_GATEWAY` | 502 | Invalid response from downstream | Downstream service returned malformed response |

---

## Authentication & Authorization

### Public Endpoints (No Auth)

These endpoints skip JWT validation entirely:

| Path | Method | Service | Purpose |
|------|--------|---------|---------|
| `/health` | GET | All | Health check |
| `/health/live` | GET | All | Liveness probe |
| `/health/ready` | GET | All | Readiness probe |
| `/api/v1/auth/login` | POST | auth-service | User login |
| `/api/v1/auth/register` | POST | auth-service | User registration |

**Implementation**: Use `@Public()` decorator (NestJS) or `permitAll()` (Spring Security).

### Protected Endpoints (Require JWT)

All other endpoints require valid JWT. Gateway validates token and injects headers:
```
Authorization: Bearer <jwt_token>
X-User-Id: <user_uuid>
X-Role: <USER|MANAGER|ADMIN>
X-Department-Id: <dept_uuid>
X-Trace-ID: <trace_uuid>
```

### Role-Based Access Control

See `.agent/context/authorization/rbac-matrix.md` for complete role matrix.

**Implementation**:
- Use `@Roles('USER', 'MANAGER', 'ADMIN')` decorator on controller methods
- NestJS `RolesGuard` or Spring Security `@PreAuthorize("hasRole('ADMIN')")`

---

## Rate Limiting

### Configuration by Role

| Role | Requests per Minute | Burst | Source |
|------|-------------------|-------|--------|
| `USER` | 100 | 120 | Per user ID |
| `MANAGER` | 200 | 240 | Per user ID |
| `ADMIN` | 500 | 600 | Per user ID |
| Public (IP) | 20 | 30 | Per IP address |

### Implementation (NestJS API Gateway)

```typescript
import { ThrottlerModule } from '@nestjs/throttler';

@Module({
  imports: [
    ThrottlerModule.forRoot([
      {
        ttl: 60000,  // 1 minute window
        limit: 20,   // Public limit (IP-based)
      },
    ]),
    ThrottlerModule.forGuard('user-throttler', [
      {
        ttl: 60000,
        limit: 100,  // Default, overridden per-role
      },
    ]),
  ],
})
export class AppModule {}
```

Per-role override in guard:
```typescript
@Injectable()
export class RoleBasedThrottlerGuard extends ThrottlerGuard {
  async shouldThrottle(request: Request) {
    const user = request.user;
    const limits = {
      USER: 100,
      MANAGER: 200,
      ADMIN: 500,
    };
    this.throttler.limit = limits[user.role] || 100;
    return super.shouldThrottle(request);
  }
}
```

### Rate Limit Headers

Always include these headers in response:

```
X-RateLimit-Limit: 100           # Requests allowed per window
X-RateLimit-Remaining: 87       # Requests remaining
X-RateLimit-Reset: 1705314600   # Unix timestamp when window resets
```

---

## Pagination Standards

All list endpoints **must** support pagination via query parameters:

```
GET /api/v1/documents?page=1&pageSize=20
```

**Query Parameters**:
- `page` (integer, default: 1): Current page number (1-indexed)
- `pageSize` (integer, default: 20, max: 100): Items per page
- `sortBy` (string, optional): Field to sort by (e.g., `createdAt`)
- `sortOrder` (string, optional): `asc` or `desc` (default: `desc`)

**Response** must include pagination metadata in `data`:
```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 450,
    "page": 2,
    "pageSize": 20,
    "totalPages": 23
  }
}
```

**Implementation** (Spring Data JPA):
```java
@GetMapping("/documents")
public ResponseEntity<PageResponse<DocumentResponse>> getDocuments(
    @RequestParam(defaultValue = "1") int page,
    @RequestParam(defaultValue = "20") int pageSize,
    @RequestParam(defaultValue = "createdAt") String sortBy,
    @RequestParam(defaultValue = "desc") String sortOrder
) {
    Pageable pageable = PageRequest.of(
        page - 1,  // Spring uses 0-indexed pages
        pageSize,
        Sort.by(Sort.Direction.fromString(sortOrder), sortBy)
    );
    
    Page<Document> result = documentService.findAll(pageable);
    
    return ResponseEntity.ok(PageResponse.of(result));
}
```

---

## Health Check Standards

All services **must** implement Kubernetes-compatible health endpoints:

| Endpoint | Purpose | Should Be Public? |
|----------|---------|-------------------|
| `GET /health` | Overall health (all dependencies) | Yes |
| `GET /health/live` | Liveness (is process running?) | Yes |
| `GET /health/ready` | Readiness (can accept traffic?) | Yes |

### Expected Response Format

```json
{
  "status": "UP",
  "components": {
    "postgres": {
      "status": "UP",
      "details": { "database": "poliwise", "version": "16.2" }
    },
    "rabbitmq": {
      "status": "UP",
      "details": { "connection": "connected" }
    },
    "minio": {
      "status": "UP",
      "details": { "bucket": "documents" }
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Status Values**:
- `UP`: Healthy
- `DOWN`: Unhealthy
- `OUT_OF_SERVICE`: Temporarily unavailable (maintenance)
- `UNKNOWN`: Unknown state

### Implementation (NestJS)

```typescript
import { HealthCheckService } from '@nestjs/terminus';

@Controller('health')
export class HealthController {
  constructor(private health: HealthCheckService) {}

  @Get()
  @HealthCheck()  // Requires @nestjs/terminus
  async check() {
    return this.health.check([
      async () => ({
        postgres: await this.postgresHealthIndicator.isHealthy(),
      }),
      async () => ({
        rabbitmq: await this.rabbitmqHealthIndicator.isHealthy(),
      }),
    ]);
  }
}
```

### Readiness vs Liveness

- **Liveness** (`/health/live`): Simple check if process is running. No dependencies. Returns 200 if HTTP server is up.
- **Readiness** (`/health/ready`): Checks all dependencies (DB, RabbitMQ, MinIO). Returns 200 only if all ready to accept traffic.
- **Overall** (`/health`): Full health check including all components.

---

## API Versioning

**Current Strategy**: URL path versioning (e.g., `/api/v1/...`). When making breaking changes, create `/api/v2/...`.

### Version Lifecycle

1. **v1**: Initial release
2. **v2**: New version with breaking changes (field removals, type changes)
3. **Deprecation**: Announce v1 deprecation 6 months before shutdown
4. ** Sunset**: After 6 months, v1 endpoints return 410 Gone

**Deprecation Headers** (optional):
```
Deprecation: true
Sunset: Sun, 01 Jul 2024 00:00:00 GMT
Link: <https://api.poliwise.com/docs/v2>; rel="successor-version"
```

---

## Common Response Patterns

### 201 Created (Resource Created)

```json
{
  "success": true,
  "data": {
    "id": "new-resource-uuid",
    "createdAt": "2024-01-15T10:30:00Z"
  },
  "message": "Resource created successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

With `Location` header:
```
Location: /api/v1/documents/new-resource-uuid
```

### 204 No Content (Successful Delete)

Empty response body, status 204.

### 422 Unprocessable Entity (Business Rule Violation)

Use when request is syntactically valid but semantically invalid:

```json
{
  "success": false,
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Cannot delete document with active processing jobs",
    "details": [
      { "field": "document_id", "message": "Document is currently being processed" }
    ]
  }
}
```

---

## Request/Response Examples by Service

### AI Q&A Service

**POST** `/api/v1/ai/chat`

Request:
```json
{
  "query": "How is the time off policy applied ?",
  "conversation_id": "optional-uuid",
  "stream": false
}
```

Response (non-streaming):
```json
{
  "success": true,
  "data": {
    "message_id": "msg-uuid",
    "conversation_id": "conv-uuid",
    "content": "According to the policy, employees get 12 days off per year",
    "sources": [
      {
        "document_id": "doc-uuid",
        "title": "HR Policy 2024",
        "section": "Article 15: Time Off",
        "page": 12,
        "similarity_score": 0.92
      }
    ],
    "tokens_used": 1250,
    "latency_ms": 2500
  }
}
```

**POST** `/api/v1/ai/chat/stream` (SSE)

Response stream:
```
event: message
data: {"type":"chunk","content":"Theo"}

event: message
data: {"type":"chunk","content":" HR"}

event: message
data: {"type":"chunk","content":" Policy..."}

event: done
data: {"traceId":"...","latency_ms":2500}
```

### Knowledge Service

**POST** `/api/v1/documents/upload` (multipart/form-data)

Request:
```
Content-Type: multipart/form-data; boundary=----boundary

------boundary
Content-Disposition: form-data; name="file"; filename="policy.pdf"
Content-Type: application/pdf

<binary file data>
------boundary--
```

Response:
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "version_id": "ver-uuid",
    "job_id": "job-uuid",
    "status": "PROCESSING",
    "estimated_completion": "2024-01-15T10:35:00Z"
  }
}
```

---

## Testing API Contracts

### Contract Tests (Pact or Spring Cloud Contract)

Define consumer expectations:

```yaml
# pact contract between ai-qa-service (consumer) and metadata-service (provider)
consumer:
  name: ai-qa-service
provider:
  name: metadata-service
pact:
  interaction:
    request:
      method: GET
      path: /api/v1/metadata/documents/doc-uuid
      headers:
        X-User-Id: user-uuid
        X-Role: USER
    response:
      status: 200
      headers:
        Content-Type: application/json
      body:
        id: doc-uuid
        title: like("Document Title")
        access_level: like("PUBLIC")
```

### Postman/OpenAPI Collection

Maintain OpenAPI 3.0 spec for all services:
```
openapi/
├── ai-qa-service.yaml
├── ingestion-service.yaml
├── knowledge-service.yaml
├── metadata-service.yaml
└── api-gateway.yaml  # Aggregated spec
```

Generate from code:
```bash
# NestJS
npm run doc

# Spring Boot
./mvnw springdoc:generate
```

---

## References

- **Service Boundaries**: `.agent/context/service-boundaries/responsibilities.md` - which service owns which endpoint
- **Error Codes**: Standard error catalog above
- **Rate Limiting**: Implementation in `services/api-gateway/src/common/interceptors/rate-limit.interceptor.ts`
- **Health Checks**: `@nestjs/terminus` documentation, Spring Boot Actuator

---

**Last Updated**: 2026-04-08
**Maintained By**: API Team
**Breaking Changes Require**: Team approval + version bump


## Employee Roster (M1) — verified against code 2026-10-16

Public routes go through the gateway (`services/api-gateway/src/proxy/proxy.controller.ts`, `JwtAuthGuard` + `RolesGuard`) and are forwarded unchanged to user-service `EmployeeRosterController` (`/api/v1/users/roster`).

| Method | Gateway path | Roles | user-service handler | Notes |
|---|---|---|---|---|
| GET | `/api/v1/users/roster/template` | ADMIN, MANAGER | `downloadTemplate` | Binary `.xlsx` (template + department sheet) |
| POST | `/api/v1/users/roster/import` | ADMIN | `importRoster` | `multipart/form-data`, field `file`, Excel `.xlsx` only; returns `RosterImportResponse`. CSV import is ticket NEXT-03 |
| GET | `/api/v1/users/roster` | ADMIN | `searchRoster` | Query: `keyword`, `departmentId`, `status`, `isClaimed`, Spring `page`/`size`/`sort` (default size 20, `createdAt,desc`); returns `Page<RosterResponse>` |
| GET | `/api/v1/users/roster/{id}` | ADMIN | `getById` | `RosterResponse` |
| PUT | `/api/v1/users/roster/{id}` | ADMIN | **none** | Gateway route exists but user-service has no `@PutMapping`; the call cannot succeed until a handler is added |
| DELETE | `/api/v1/users/roster/{id}` | ADMIN | `deactivate` | Soft-deactivates the roster row; `204 No Content` |

Internal routes (user-service `InternalRosterController`, `@PreAuthorize("hasRole('INTERNAL')")`, called by auth-service through `UserServiceClient` with the `X-Internal-Service` header; not exposed by the gateway):

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/internal/v1/roster/claim` | `ClaimRosterRequest` | `ClaimRosterResponse`; atomic JIT claim, publishes `user.registered` / `user.assigned.dept` (see `events.md` §7) |
| POST | `/internal/v1/roster/google-admission` | `AdmitGoogleLoginRequest` `{email, userId}` | `ClaimRosterResponse`; see the Google admission section below |

## Google admission update ? 2026-10-15

Google authentication is owned exclusively by auth-service. The public POST /api/v1/auth/google/verify contract remains unchanged. Internal POST /internal/v1/roster/google-admission accepts {email,userId}; userId is resolved by auth-service from the verified issuer/subject link and is never supplied by the browser. X-Internal-Service authenticates the caller. Every Google login checks roster admission; 404 missing roster maps to public 403, deactivated roster returns 403, inconsistent claim or account mismatch returns 409, unavailable service fails closed with 503. See docs/archive/02-architecture/designs/TECH-google-admission.md for exact JSON and status contracts. Legacy gateway code-exchange routes are unregistered.
