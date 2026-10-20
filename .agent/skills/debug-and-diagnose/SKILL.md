---
name: debug-and-diagnose
description: Systematic debugging and root cause analysis for the SOPilot polyglot microservices stack.
version: 1.0.0
author: SOPilot Team
---

# Debug and Diagnose

## When to use this skill
- When a bug is reported
- When a service is failing/unhealthy
- When investigating unexpected behavior
- When tracing errors across services
- When diagnosing performance issues

## Core Instructions

1. **Reproduce**: Confirm the bug exists. Collect: error message, stack trace, HTTP status, affected endpoint, user context. Try to reproduce with minimal steps.
2. **Locate**: Identify which service(s) are involved by tracing the request flow:
   - Frontend error? → Check browser console, network tab
   - Gateway error (3001)? → Check gateway logs, proxy config
   - Backend 5xx? → Check specific service logs
   - Event processing failure? → Check RabbitMQ DLQ, consumer logs
   - Use `./scripts/check-services.ps1` (repo root) to verify all services are healthy, and `./scripts/trace-request.ps1 -Endpoint <path>` to trace gateway routing
3. **Isolate**: Narrow down to specific layer:
   - Controller (routing, validation)
   - Service (business logic)
   - Repository (database queries)
   - Event (RabbitMQ publish/consume)
   - External (MinIO, Groq API, Jina API)
4. **Root Cause Analysis**: Read the relevant code, check:
   - Recent changes (`git log --oneline -20`)
   - Database state (correct schema, data integrity)
   - Configuration (.env values, docker-compose config)
   - Dependencies (service-to-service communication)
5. **Fix & Verify**: Apply the fix → write a test covering the bug → run affected service tests → verify the fix resolves the original issue
6. **Prevent**: Document the root cause → create ticket if architectural gap → update common-issues.md if pattern is reusable

## Quick Diagnostics

| Symptom | First Check | Service |
|---------|-------------|---------|
| 401/403 errors | Gateway JWT/RBAC guards, token expiry | api-gateway |
| 500 from backend | Service logs, DB connection, schema | specific service |
| Event not processing | RabbitMQ management UI, DLQ, consumer status | producer + consumer |
| Slow response | DB query plans, missing indexes, N+1 | specific service |
| File upload fails | MinIO connection, bucket permissions, multipart config | knowledge-service |
| AI response wrong | Prompt template, retrieval results, embedding quality | ai-qa-service |
| Frontend blank/error | Build errors, API connection, CORS | frontend/web |

## References
- [Common Issues](references/common-issues.md)
