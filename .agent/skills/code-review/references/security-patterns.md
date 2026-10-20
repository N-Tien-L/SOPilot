# Security Patterns & Anti-Patterns for SOPilot

## SQL Injection
- **Pattern**: Use JPA/Hibernate or parameterized queries.
- **Anti-Pattern**: String concatenation in native queries or raw SQL execution. Always validate inputs even when using ORMs if dynamic fields are used.

## Cross-Site Scripting (XSS)
- **Pattern**: Rely on React's automatic escaping.
- **Anti-Pattern**: Using `dangerouslySetInnerHTML` or rendering unescaped user-generated content directly into the DOM.

## Role-Based Access Control (RBAC) Bypass
- **Pattern**: Enforce strict checks (`ADMIN > MANAGER > USER`). Protect endpoints with `@PreAuthorize` in Spring Boot or Guards in NestJS API Gateway.
- **Anti-Pattern**: Missing endpoint authorization decorators or relying solely on frontend hiding logic.

## JWT Vulnerabilities
- **Pattern**: Validate token expiration, audience, issuer, and signature.
- **Anti-Pattern**: Accepting expired tokens, algorithm confusion attacks (e.g., accepting 'none' algorithm), or weak signing keys.

## Secret Management
- **Pattern**: Store all secrets in `.env` or environment variables, injected by the platform.
- **Anti-Pattern**: Hardcoded API keys, passwords, or tokens in source code or default configuration files.

## File Upload Security (MinIO)
- **Pattern**: Validate content types, use random filenames/UUIDs, and restrict upload paths.
- **Anti-Pattern**: Trusting user-provided filenames (path traversal risks) or missing MIME-type validation.

## Rate Limiting
- **Pattern**: Configure robust throttler settings at the API Gateway level to prevent abuse.
- **Anti-Pattern**: Missing rate limiters on public or authentication-related endpoints.

## Event Poisoning
- **Pattern**: Validate all incoming event payloads against defined schemas before processing.
- **Anti-Pattern**: Blindly trusting data from the message broker without validation.
