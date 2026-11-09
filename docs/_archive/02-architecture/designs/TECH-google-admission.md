---
id: TECH-GOOGLE-ADMISSION
title: "Google admission contract"
status: superseded
created: 2026-10-15
updated: 2026-11-08
author: "Owner"
refs: [docs/_archive/01-requirements/PRD-M1-jit-onboarding.md, docs/02-architecture/adr/ADR-001-employee-roster-ownership.md, docs/02-architecture/adr/ADR-002-google-jit-auth-boundary.md, docs/02-architecture/adr/ADR-003-google-identity-and-roster-admission.md]
affected_services: [auth-service, user-service, api-gateway]
affected_schemas: [core]
---

> **Đóng 2026-11-08:** `superseded` vì ADR-001 đến 003 đã `superseded`; thay bằng [TECH-V2-core-api](../../../02-architecture/designs/TECH-V2-core-api.md) và ADR-005. Giữ file làm lịch sử V1; không dùng làm đặc tả.

# Google admission contract

Public contract remains `POST /api/v1/auth/google/verify` with JSON `{"idToken":"<Google ID token>"}`. The gateway forwards it. Success remains the existing `TokenResponse` (accessToken, refreshToken, tokenType, expiresIn, user). The browser cannot choose user ID, role, department or provider subject.

New internal endpoint: `POST /internal/v1/roster/google-admission`, user-service owner; header `X-Internal-Service` with the shared internal credential. It is not a public gateway route.

First enrollment:

```json
{"email":"employee@company.example","userId":null}
```

Returning identity:

```json
{"email":"renamed@company.example","userId":"7ac3007e-30c5-4c48-9cc2-117a1d17570f"}
```

Here userId is resolved by auth-service from `(issuer, sub)`. User-service locks the nondeleted roster by claimed user ID for returning users, by normalized email otherwise. A valid claimed record returns the existing user/profile without creating users or republishing registration events. Pending records execute the existing atomic claim routine.

Success is `ClaimRosterResponse`:

```json
{
  "userId":"7ac3007e-30c5-4c48-9cc2-117a1d17570f",
  "username":"employee", "email":"employee@company.example", "fullName":"Employee",
  "role":"USER", "departmentId":"50096c0e-d743-47c3-bf88-72a6a8769524",
  "departmentName":"Engineering", "departmentCode":"ENG"
}
```

| Condition | Internal HTTP | Public Google verify |
|---|---|---|
| Valid enrollment or admitted returning user | 200 | 200 |
| Invalid body/email | 400 | Invalid public body: 400 |
| Missing/invalid internal credential | 401 | No token issued; auth service fails closed |
| Missing/deleted roster | 404 `ROSTER_NOT_FOUND` | 403 `ROSTER_NOT_FOUND` |
| Deactivated roster | 403 | 403 |
| Inconsistent claim / legacy role-department mismatch | 409 | 409 |
| Subject already bound differently | N/A | 409 |
| Invalid signature/audience/issuer/expiry/subject | N/A | 401 |
| First email enrollment without Gmail/Workspace authority | N/A | 403; existing bound subject can still authenticate |
| Local account deactivated/revoked/locked | 403 on first claim or checked by auth | 403 |
| User-service unavailable | N/A | 503 |

`/internal/v1/roster/claim` remains a strict first-claim endpoint for compatibility. Google login uses the new idempotent admission contract. The external identity table is auth-owned; user-service does not query it.

```mermaid
sequenceDiagram
  participant F as Frontend
  participant G as Gateway
  participant A as auth-service
  participant U as user-service
  participant D as PostgreSQL core
  F->>G: POST google/verify {idToken}
  G->>A: Forward request and trace metadata
  A->>A: Verify Google JWKS/claims
  A->>D: Resolve canonical issuer + sub
  A->>U: Google admission {email, linkedUserId}, internal header
  U->>D: Lock roster; admit existing claim or enroll
  U-->>A: ClaimRosterResponse
  A->>D: Lock user; check status; insert identity ON CONFLICT DO NOTHING
  A->>D: Verify binding; save login/session
  A-->>G: SOPilot TokenResponse
  G-->>F: TokenResponse
```

Testing: `tests/integration/google-auth-flow.mjs` starts two real service processes against a fresh loopback-only PostgreSQL container and local RSA JWKS. It exercises backend identity, admission, concurrency and session lifecycle. It does not automate Google's hosted account UI, Excel import UI, RabbitMQ audit delivery or chatbot navigation; M1-06 still owns that full product evidence.
