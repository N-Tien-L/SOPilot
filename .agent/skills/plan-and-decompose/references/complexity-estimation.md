# Complexity Estimation Guide

Properly estimating ticket sizes helps ensure they are executable as single, manageable units of work.

## Size Definitions

### Small (S) - Under 2 hours
- Simple bug fixes or minor refactoring.
- Adding a new isolated endpoint with no complex business logic.
- UI tweaks (CSS changes, adding a single button or simple form).
- Documentation updates.
- **Example:** Add a new query parameter to an existing FastAPI endpoint.

### Medium (M) - 2 to 4 hours
- Standard CRUD features within a single microservice.
- A new page in the Next.js frontend requiring data fetching and state management.
- Setting up a new RabbitMQ consumer/producer flow for a single event type.
- **Example:** Implement the Spring Boot REST controller, service, and repository for a new entity.

### Large (L) - 4 to 8 hours
- Complex business logic algorithms.
- Changes involving multiple layers (DB migration + backend logic + unit tests).
- Complex frontend features with intricate global state (Zustand) and side-effects.
- **Example:** Implement the RAG pipeline integration in the AI-QA FastAPI service, including pgvector queries and LLM prompt construction.

### Extra Large (XL) - Over 8 hours (Needs Splitting)
- **Do not create XL tickets.** If a task feels like an XL, it must be decomposed further.
- Cross-service features (e.g., changing something in `auth`, `user`, and `gateway` at once).
- Major schema refactors affecting multiple tables.

## Splitting Heuristics for XL Tasks
1. **Vertical Splitting (By Flow):** Instead of "Implement Search System", split into "Search API (Backend)" and "Search UI (Frontend)".
2. **Horizontal Splitting (By Phase):** Split into "Database Migrations", "Service Logic", "API Endpoints", "Event Emitters".
3. **Happy Path First:** "Implement Checkout (Happy Path)" and "Implement Checkout (Error Handling & Edge Cases)".

## Complexity Multipliers
When evaluating size, bump up the size if any of these are involved:
- **Database Migrations:** Modifying live schemas carries risk and requires careful testing.
- **Cross-Service Communication:** Dealing with Gateway routing or gRPC/REST between internal services.
- **Asynchronous Flows:** RabbitMQ messaging can be hard to test and trace.
