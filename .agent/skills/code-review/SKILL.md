---
name: code-review
description: Comprehensive self-review and peer-review guidelines for code changes to ensure quality, security, performance, and conventions.
version: 1.0.0
author: SOPilot Team
---

# Code Review Skill

## When to use this skill
- After implementing a ticket and before creating a PR or committing changes.
- When reviewing someone else's code (e.g., Pull Request review).
- When asked to perform a general code review or audit of existing changes.

## Core Instructions

1. **Gather Context**
   - Read the relevant ticket or requirement to fully understand the intent of the change.
   - Get the full diff of the changes (e.g., using `git diff`).

2. **Correctness Review**
   - Check for logic errors, proper null handling, and correct error propagation.
   - Look out for race conditions and handle boundary conditions correctly.

3. **Security Review**
   - Identify vulnerabilities: SQL injection, XSS, authentication bypass, secret exposure.
   - Ensure proper RBAC (ADMIN > MANAGER > USER) enforcement and strict input validation.

4. **Performance Review**
   - Detect N+1 queries, missing database indexes, and unoptimized GIN/vector indexes.
   - Look for unnecessary re-renders in React, memory leaks, or unbounded collections.

5. **Convention Review**
   - Enforce naming conventions, correct package structures, and DTO patterns.
   - Ensure standard error response shapes and adhere to coding style specific to the service (Java, Python, TS).

6. **Architecture Review**
   - Prevent service boundary violations (e.g., cross-schema DB access is forbidden).
   - Verify proper event-driven communication via RabbitMQ topic exchange `poliwise.events`.
   - Ensure proper API Gateway routing. No direct service-to-service HTTP calls if they should be events.

7. **Documentation Review**
   - Verify that necessary contexts, standard docs, Javadoc/JSDoc for public APIs, and READMEs are updated.

8. **Report Findings**
   - Categorize issues clearly into:
     - **BLOCKER**: Must be fixed before merging.
     - **WARNING**: Should be fixed to prevent future issues.
     - **SUGGESTION**: Nice to have improvements or nitpicks.

## References
- [Review Checklist](resources/review-checklist.md)
- [Security Patterns](references/security-patterns.md)
- [Performance Antipatterns](references/performance-antipatterns.md)
