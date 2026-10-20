# Testing Strategy for SOPilot

## 1. Test Pyramid Approach
SOPilot follows a standard Test Pyramid:
- **Unit Tests (70%)**: Fast, isolated tests for core business logic. Every class/module should have unit tests.
- **Integration Tests (20%)**: Test interactions with databases, caches, message brokers, and other services. Focus on repositories, event listeners, and API gateways.
- **End-to-End (E2E) Tests (10%)**: Broad tests simulating real user workflows from the frontend through the gateway to the microservices.

## 2. Coverage Targets
- **New Code**: Target **80%** line coverage.
- **Overall Project**: Maintain a minimum of **60%** overall coverage.
- *Critical paths* (like authentication, document processing in `knowledge-service`, RRF logic in `ai-qa-service`) demand 90%+ coverage.

## 3. When to write Integration vs Unit Tests
- **Write Unit Tests when:**
  - Logic contains complex branching (e.g., algorithms, parsers).
  - Validating domain model rules or pure functions.
  - Testing edge cases that are hard to reproduce with real infrastructure.
- **Write Integration Tests when:**
  - Testing custom SQL/JPA queries.
  - Testing API endpoint serialization (e.g., Spring Boot `@WebMvcTest` or FastAPI `TestClient`).
  - Verifying asynchronous message publishing/consuming (RabbitMQ).

## 4. Cross-Service Testing
Instead of fragile end-to-end setups for every small change, prefer **Contract Testing** or mocked API responses for dependent services during CI/CD. True cross-service E2E tests are reserved for major deployment pipelines.
