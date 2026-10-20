# Comprehensive Review Checklist

## General
- [ ] Meaningful and consistent naming conventions for variables, functions, and classes.
- [ ] Proper code formatting according to project standards.
- [ ] No dead code, unused variables, or commented-out blocks of code.
- [ ] Meaningful commit messages and grouped logical changes.

## Java-specific (Spring Boot Services)
- [ ] Proper use of `Optional` to prevent `NullPointerException`.
- [ ] Stream API used efficiently and correctly (no unnecessary intermediate collections).
- [ ] Explicit and correct transaction boundaries (`@Transactional`).
- [ ] Proper entity relationships (Lazy loading by default, appropriate cascading).
- [ ] Controllers delegate to services, no business logic in controllers.

## Python-specific (FastAPI Services)
- [ ] Correct use of `async`/`await` without blocking the event loop.
- [ ] Complete and accurate type hints for all function parameters and return types.
- [ ] Proper exception handling (no bare `except:` clauses).
- [ ] Dependency injection used appropriately in FastAPI endpoints.

## TypeScript-specific (API Gateway & Frontend)
- [ ] Strict types used everywhere; absolutely no use of `any`.
- [ ] Proper null and undefined checks.
- [ ] Strict adherence to React Hooks rules (no conditional hooks, correct dependency arrays).

## Frontend-specific (Next.js & React)
- [ ] Accessibility (a11y) standards met (e.g., `aria-` attributes, alt text, keyboard navigation).
- [ ] Explicit loading states handling.
- [ ] Clear error states and error boundary handling.
- [ ] Responsive design implemented and tested for various screen sizes.

## Database (PostgreSQL & pgvector)
- [ ] Proper indexes added for heavily queried columns.
- [ ] Query efficiency (e.g., avoiding subqueries in `WHERE` clauses when a `JOIN` is better).
- [ ] Migration safety (e.g., no destructive operations like dropping columns without a plan).

## Events (RabbitMQ)
- [ ] Strict adherence to event schemas for `poliwise.events`.
- [ ] Idempotent event consumer logic.
- [ ] Proper dead-letter handling configured for failure scenarios.

## Security
- [ ] All external inputs are strictly validated.
- [ ] Output encoding implemented to prevent XSS.
- [ ] Proper authorization checks placed at endpoint/gateway levels.
