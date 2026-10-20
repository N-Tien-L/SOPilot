---
id: VIOL-02
title: "Implement Violation Service Logic & API"
type: feat
status: todo
created: 2026-09-24
updated: 2026-09-24
scope: user
priority: P0
size: M
parent_plan: PLAN-VIOL-01
depends_on: ["VIOL-01"]
blocks: ["VIOL-04", "VIOL-05"]
branch: "feat/viol-02-service-logic"
assignee: pair
---

## Context
Following the creation of the `violations` table in VIOL-01, we need to implement the business logic and REST endpoints in the Spring Boot `user-service` to allow querying and manually creating violations.

## Acceptance Criteria
- [ ] `ViolationRepository` is created with necessary JPA methods.
- [ ] `ViolationService` handles creation and applies a ban if a user has >= 3 high-severity violations.
- [ ] `ViolationController` exposes `GET /api/users/{id}/violations` and `POST /api/users/{id}/violations`.
- [ ] Endpoints are secured with appropriate role checks (Admin only).

## Implementation Guide
1. **Create Repository**
   - **File:** `services/user/src/main/java/com/sopilot/user/repository/ViolationRepository.java`
   - **Action:** CREATE
   - **Details:** Create a Spring Data JPA interface extending `JpaRepository<Violation, UUID>`. Add `List<Violation> findByUserId(UUID userId)`.

2. **Create Service Logic**
   - **File:** `services/user/src/main/java/com/sopilot/user/service/ViolationService.java`
   - **Action:** CREATE
   - **Details:** 
     ```java
     @Service
     @RequiredArgsConstructor
     public class ViolationService {
         private final ViolationRepository repository;
         private final UserRepository userRepository;
         
         @Transactional
         public Violation createViolation(UUID userId, ViolationDto dto) {
             // Logic to create violation
             // Logic to check threshold and ban user
         }
     }
     ```

3. **Create Controller**
   - **File:** `services/user/src/main/java/com/sopilot/user/controller/ViolationController.java`
   - **Action:** CREATE
   - **Details:** Implement the REST endpoints using `@RestController`.

## Technical Notes
- Ensure `@Transactional` is used in the service layer because saving a violation and updating the user's ban status must be atomic.

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Unit | Ban threshold logic (user banned on 3rd violation). | JUnit 5 + Mockito |
| Integration | REST endpoints return correct HTTP status codes (201 Created, 403 Forbidden). | SpringBootTest + MockMvc |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `ViolationRepository.java` | CREATE | +15 |
| `ViolationService.java` | CREATE | +60 |
| `ViolationController.java` | CREATE | +50 |
| `ViolationServiceTest.java` | CREATE | +100 |
