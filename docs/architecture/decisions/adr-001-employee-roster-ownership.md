---
id: ADR-001
title: "user-service owns the core.employee_roster table"
status: superseded
created: 2026-09-25
updated: 2026-11-13
author: "Owner"
refs: [docs/archive/01-requirements/PRD-M1-jit-onboarding.md]
deciders: ["Principal Architect", "Tech Lead"]
superseded_by: "ADR-005"
---

# ADR-001: user-service owns the core.employee_roster table

> Update 2026-10-15: ADR-003-google-identity-and-roster-admission.md replaces the assumption below that the roster is checked only once. Ownership stays with user-service; every Google login now checks admission.

> **Status:** Superseded by ADR-005 (2026-10-20), previously Accepted | **Decided:** 2026-09-25 | **Deciders:** Principal Architect, Tech Lead
>
> V1 decision, kept for the decision log. Translated from Vietnamese on 2026-11-13.

---

## 1. Context & Problem Statement
The system implements "Pre-provisioned Directory + Google 1-Click JIT Sign-in" and needs a table holding the staff directory (`core.employee_roster`) uploaded by Admin/HR. The architectural question: which service is the owner (System of Record) of this table, `user-service` or `auth-service`?

---

## 2. Decision Drivers
- **Domain-Driven Design (DDD):** put the entity in the right business bounded context.
- **Single Responsibility Principle (SRP):** keep `auth-service` lean, focused on authentication and token issuance.
- **Resources & dependencies:** avoid bringing a spreadsheet library (Apache POI) into the security-critical authentication service.

---

## 3. Considered Options

### Option A: `auth-service` manages it
- **Pros:** `auth-service` can query the email whitelist directly when it receives a Google token, without calling another service's internal API.
- **Cons:** `auth-service` becomes bloated, taking on Excel parsing, the department tree, directory paging and job-title validation, a serious SRP violation.

### Option B: `user-service` fully manages it (CHOSEN)
- **Pros:**
  - The staff directory belongs with the `Department` and `UserProfile` aggregates.
  - All Excel import, department filtering and employee-id validation belongs to `user-service`'s HR administration domain.
  - `auth-service` only calls one internal endpoint, `/internal/v1/roster/claim`, on `user-service`.
- **Cons:** one extra internal network call (internal HTTP) from `auth-service` to `user-service` on the first sign-in.

---

## 4. Decision Outcome & Rationale
- **Decision:** **Option B**: `user-service` is the **Owner (System of Record)** of `core.employee_roster`.
- **Rationale:** the internal call happens only once, when an employee claims the JIT account. After that the account is active in `core.users`, so later sign-ins are not affected.

---

## 5. Consequences
- **Positive:** clear business boundaries; `auth-service` does not depend on Apache POI.
- **Negative:** `auth-service` needs an OpenFeign client to call `user-service` with `INTERNAL_SERVICE_TOKEN` to protect the internal API.
