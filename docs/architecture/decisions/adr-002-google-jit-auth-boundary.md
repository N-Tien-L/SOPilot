---
id: ADR-002
title: "auth-service verifies the Google ID token itself; the gateway is a reverse proxy"
status: superseded
created: 2026-09-25
updated: 2026-11-13
author: "Owner"
refs: [docs/archive/01-requirements/PRD-M1-jit-onboarding.md]
deciders: ["Principal Architect", "Tech Lead"]
superseded_by: "ADR-004"
---

# ADR-002: auth-service verifies the Google ID token itself; the gateway is a reverse proxy

> **Status:** Superseded by ADR-004 (2026-10-20), previously Accepted | **Decided:** 2026-09-25 | **Deciders:** Principal Architect, Tech Lead
>
> V1 decision, kept for the decision log. Translated from Vietnamese on 2026-11-13.

---

## 1. Context & Problem Statement
When an employee clicks "Sign in with Google", the frontend receives a Google ID token. Which layer calls Google JWKS to verify the signature: the API gateway (NestJS) or `auth-service` (Spring Boot)?

---

## 2. Decision Drivers
- **Centralized authentication logic:** keep token issuance, refresh tokens and `core.login_history` recording in a single place.
- **Gateway independence:** the gateway should stay a lightweight reverse proxy and not carry third-party token-provider logic.

---

## 3. Considered Options

### Option A: the gateway verifies the Google token and forwards
- **Cons:** the gateway would need the Google Auth library and client id configuration, and would still have to call `auth-service` to mint SOPilot's internal session JWT. Authentication logic would be fragmented.

### Option B: auth-service verifies the Google ID token itself (CHOSEN)
- **Pros:**
  - The gateway only forwards `POST /api/v1/auth/google/verify` with the `@Public()` decorator.
  - `auth-service` checks the JWKS signature, matches the whitelist, creates the session and issues the internal JWT in one transaction.

---

## 4. Decision Outcome & Rationale
- **Decision:** **Option B**. `auth-service` is the single point responsible for verifying user identity and issuing SOPilot's internal JWTs.
