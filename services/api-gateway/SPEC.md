# API Gateway Specification

## 1. Project Overview

**Project**: Poliwise API Gateway
**Type**: NestJS Microservices API Gateway
**Role**: Single entry point for all client requests in the Poliwise system
**Target**: Production-grade, enterprise-ready

---

## 2. Functionality Specification

### 2.1 Core Features

#### A. JWT Authentication Guard
- Verify JWT tokens from Authorization Bearer header
- Parse and validate claims: `sub`, `username`, `email`, `role`, `status`, `department`, `jti`
- Check account status: Only `ACTIVE` accounts allowed; `DEACTIVATED` and `REVOKED` → 403 Forbidden
- Support shared JWT secret from environment configuration
- Skip validation for endpoints marked with `@Public()` decorator
- Attach user context to request object for downstream use

#### B. RBAC Authorization Guard
- Three roles: `USER`, `MANAGER`, `ADMIN`
- Role hierarchy: ADMIN > MANAGER > USER
- Decorator-based: `@Roles('ADMIN')`, `@Roles('USER', 'MANAGER')`
- Permission matrix aligned with `docs/allow_per_role.md`:

| Endpoint Pattern | USER | MANAGER | ADMIN |
|-----------------|:----:|:-------:|:-----:|
| `/api/v1/ai/*` (Q&A) | ✅ | ✅ | ✅ |
| `/api/v1/feedback/*` | ✅ | ✅ | ✅ |
| `/api/v1/users/profile` | ✅ | ✅ | ✅ |
| `/api/v1/analytics/*` | ❌ | ✅ | ✅ |
| `/api/v1/documents/upload` | ❌ | ❌ | ✅ |
| `/api/v1/metadata/*` | ❌ | ❌ | ✅ |
| `/api/v1/admin/*` | ❌ | ❌ | ✅ |

#### C. Rate Limiting
- Use `@nestjs/throttler` package
- Per-user rate limiting based on user ID (authenticated) or IP (unauthenticated)
- Configuration by role:
  - `USER`: 100 requests/minute
  - `MANAGER`: 200 requests/minute
  - `ADMIN`: 500 requests/minute
  - `Public`: 20 requests/minute (IP-based)
- Return `429 Too Many Requests` when exceeded
- Include `X-RateLimit-*` headers in response

#### D. Circuit Breaker
- Use `opossum` package for resilience
- Circuit states: CLOSED → OPEN → HALF_OPEN
- Per-service circuit breakers:
  - `auth-service`: failure threshold 5, timeout 30000ms
  - `user-service`: failure threshold 5, timeout 30000ms
  - `knowledge-service`: failure threshold 5, timeout 60000ms
  - `metadata-service`: failure threshold 5, timeout 30000ms
  - `feedback-service`: failure threshold 5, timeout 30000ms
- Fallback response on circuit open:
  ```json
  {
    "success": false,
    "error": {
      "code": "SERVICE_UNAVAILABLE",
      "message": "Service temporarily unavailable",
      "retryAfter": 30
    },
    "timestamp": "ISO-8601"
  }
  ```
- Log circuit state transitions

#### E. Trace ID Generation & Propagation
- Generate UUID v4 for each incoming request
- Header name: `X-Trace-ID`
- If `X-Trace-ID` already exists in request, use it (upstream propagation)
- Attach to all downstream service calls as `X-Trace-ID` header
- Include in all log entries and response headers
- Use AsyncLocalStorage for request-scoped context

#### F. Request/Response Logging
- Use Winston for structured JSON logging
- Log levels: ERROR, WARN, INFO, DEBUG
- Log format:
  ```json
  {
    "timestamp": "ISO-8601",
    "level": "info",
    "traceId": "uuid",
    "message": "...",
    "method": "POST",
    "path": "/api/v1/...",
    "statusCode": 200,
    "duration": 150,
    "userId": "uuid",
    "ip": "x.x.x.x",
    "userAgent": "..."
  }
  ```
- Log request body for POST/PUT/PATCH (sanitize sensitive fields)
- Log response body for errors only
- Never log passwords, tokens, or PII

#### G. Request Validation
- Use `class-validator` + `class-transformer`
- Global validation pipe applied to all routes
- DTO validation with decorators
- Return 400 Bad Request with detailed validation errors:
  ```json
  {
    "success": false,
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Validation failed",
      "details": [
        { "field": "email", "message": "email must be valid" }
      ]
    },
    "timestamp": "ISO-8601"
  }
  ```

#### H. HTTP Proxy/Routing
- Use Axios for HTTP forwarding to downstream services
- Route configuration:
  | Path Pattern | Target Service | Port |
  |-------------|---------------|------|
  | `/api/v1/auth/*` | (handled internally) | - |
  | `/api/v1/users/*` | user-service | 8082 |
  | `/api/v1/documents/*` | knowledge-service | 8083 |
  | `/api/v1/metadata/*` | metadata-service | 8084 |
  | `/api/v1/feedback/*` | feedback-service | 8085 |
  | `/api/v1/analytics/*` | feedback-service | 8085 |
  | `/api/v1/ai/*` | (future AI service) | 8086 |
- Preserve original request headers
- Forward `Authorization`, `X-Trace-ID`, `X-User-Id`, `X-Role` headers
- Timeout: 30 seconds (configurable per service)

#### I. Response Transformation
- Normalize all responses to standard format:
  ```json
  {
    "success": true,
    "data": { ... },
    "message": "Optional message",
    "timestamp": "ISO-8601",
    "traceId": "uuid"
  }
  ```
- Handle error responses from downstream services
- Preserve pagination metadata

#### J. CORS Handling
- Configure CORS for frontend origin
- Support credentials
- Allowed methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
- Allowed headers: Content-Type, Authorization, X-Trace-ID, X-Requested-With
- Max age: 86400 (1 day)
- Dynamic origin from environment config

### 2.2 Security Features

- Helmet for security headers (disabled for API health check)
- Request body size limit: 10MB
- Timeout for all requests: 30 seconds
- No sensitive data in logs
- No stack traces in production responses

### 2.3 Health Checks

- `GET /health` - Overall health (public, no auth)
- `GET /health/ready` - Readiness probe (check downstream services)
- `GET /health/live` - Liveness probe

---

## 3. Configuration

### 3.1 Environment Variables

```env
# Server
PORT=3000
NODE_ENV=development

# JWT (must match auth-service)
JWT_SECRET=your-256-bit-secret-key-here

# CORS
CORS_ORIGIN=http://localhost:3001

# Downstream Services
AUTH_SERVICE_URL=http://localhost:8081
USER_SERVICE_URL=http://localhost:8082
KNOWLEDGE_SERVICE_URL=http://localhost:8083
METADATA_SERVICE_URL=http://localhost:8084
FEEDBACK_SERVICE_URL=http://localhost:8085

# Rate Limiting
THROTTLE_TTL=60000
THROTTLE_LIMIT_USER=100
THROTTLE_LIMIT_MANAGER=200
THROTTLE_LIMIT_ADMIN=500
THROTTLE_LIMIT_PUBLIC=20

# Circuit Breaker
CIRCUIT_BREAKER_TIMEOUT=30000
CIRCUIT_BREAKER_VOLUME_THRESHOLD=10

# Logging
LOG_LEVEL=info
```

---

## 4. Module Structure

```
src/
├── main.ts
├── app.module.ts
├── app.controller.ts
│
├── config/
│   ├── app.config.ts
│   ├── cors.config.ts
│   ├── throttler.config.ts
│   └── services.config.ts
│
├── common/
│   ├── dto/
│   │   ├── api-response.dto.ts
│   │   ├── error-response.dto.ts
│   │   └── pagination.dto.ts
│   ├── interfaces/
│   │   ├── jwt-payload.interface.ts
│   │   └── user-context.interface.ts
│   ├── decorators/
│   │   ├── roles.decorator.ts
│   │   ├── public.decorator.ts
│   │   ├── current-user.decorator.ts
│   │   └── rate-limit.decorator.ts
│   ├── filters/
│   │   └── http-exception.filter.ts
│   ├── interceptors/
│   │   ├── logging.interceptor.ts
│   │   ├── trace-id.interceptor.ts
│   │   ├── response-transform.interceptor.ts
│   │   └── timeout.interceptor.ts
│   ├── guards/
│   │   ├── jwt-auth.guard.ts
│   │   └── rbac.guard.ts
│   └── utils/
│       └── trace-id.util.ts
│
├── auth/
│   ├── auth.module.ts
│   ├── strategies/
│   │   └── jwt.strategy.ts
│   └── services/
│       └── jwt-auth.service.ts
│
├── proxy/
│   ├── proxy.module.ts
│   ├── proxy.service.ts
│   └── proxy.controller.ts
│
├── health/
│   ├── health.module.ts
│   ├── health.controller.ts
│   └── indicators/
│       └── services.indicator.ts
│
└── logging/
    └── winston.config.ts
```

---

## 5. Acceptance Criteria

### Authentication
- [ ] JWT tokens are verified on every authenticated request
- [ ] Invalid/expired tokens return 401 Unauthorized
- [ ] REVOKED/DEACTIVATED accounts return 403 Forbidden
- [ ] Public endpoints skip authentication
- [ ] User context (userId, role, department) is available in request

### Authorization
- [ ] Role-based access control enforced on all protected routes
- [ ] Insufficient permissions return 403 Forbidden
- [ ] Role decorators work correctly with NestJS guards

### Rate Limiting
- [ ] Authenticated users limited by role-based limits
- [ ] Unauthenticated requests limited by IP
- [ ] 429 response includes rate limit headers
- [ ] Limits reset after TTL

### Circuit Breaker
- [ ] Service failures trigger circuit open after threshold
- [ ] Fallback response returned when circuit is open
- [ ] Circuit auto-recovers after timeout
- [ ] State transitions are logged

### Tracing
- [ ] Unique trace ID generated for each request
- [ ] Trace ID propagated to all downstream services
- [ ] Trace ID included in all log entries
- [ ] Trace ID returned in response headers

### Logging
- [ ] All requests/responses logged in structured JSON
- [ ] Sensitive data (passwords, tokens) never logged
- [ ] Error logs include stack traces in development
- [ ] Log level configurable via environment

### Validation
- [ ] Invalid request bodies return 400 with details
- [ ] Validation errors include field names and messages
- [ ] Global validation pipe applied to all routes

### Proxy/Routing
- [ ] Requests routed to correct downstream service
- [ ] Original headers forwarded (except hop-by-hop)
- [ ] Timeout applied to all proxied requests
- [ ] Error responses transformed to standard format

### Response Transformation
- [ ] All responses wrapped in standard format
- [ ] Success responses include data, message, timestamp
- [ ] Error responses include error code and details

### CORS
- [ ] CORS headers set correctly for all origins
- [ ] Preflight requests handled
- [ ] Credentials supported

### Health Checks
- [ ] /health endpoint returns overall status
- [ ] /health/ready checks downstream services
- [ ] Health checks are unauthenticated

---

## 6. Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| UNAUTHORIZED | 401 | Missing or invalid token |
| ACCOUNT_DEACTIVATED | 403 | Account is deactivated |
| ACCOUNT_REVOKED | 403 | Account is revoked |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 400 | Request validation failed |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests |
| SERVICE_UNAVAILABLE | 503 | Circuit breaker open |
| INTERNAL_ERROR | 500 | Internal server error |
| BAD_GATEWAY | 502 | Downstream service error |

---

## 7. Testing Strategy

### Unit Tests
- JWT authentication service
- RBAC guard logic
- Rate limiting logic
- Proxy routing logic
- Response transformation

### Integration Tests
- Full request flow with mocked downstream services
- Circuit breaker behavior
- CORS handling
- Health check endpoints

---

## 8. Non-Functional Requirements

- **Performance**: P99 latency < 500ms for proxied requests
- **Availability**: Graceful degradation with circuit breakers
- **Security**: OWASP Top 10 considerations
- **Observability**: Structured logging, trace IDs
- **Maintainability**: Clean architecture, dependency injection
