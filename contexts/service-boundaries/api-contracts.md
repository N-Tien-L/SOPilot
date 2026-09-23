---
title: API Contracts & Standards
description: Standardized API response formats, error codes, and authentication requirements for all Poliwise services
type: service-boundaries
version: 1.0
---

# API Contracts & Standards

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

See `contexts/authorization/rbac-matrix.md` for complete role matrix.

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

- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md` - which service owns which endpoint
- **Error Codes**: Standard error catalog above
- **Rate Limiting**: Implementation in `services/api-gateway/src/auth/throttler/`
- **Health Checks**: `@nestjs/terminus` documentation, Spring Boot Actuator

---

**Last Updated**: 2026-04-08
**Maintained By**: API Team
**Breaking Changes Require**: Team approval + version bump
