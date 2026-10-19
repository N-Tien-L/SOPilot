---
id: PLAN-VIOL-01
title: "Violation Management System"
status: approved
created: 2026-09-24
updated: 2026-09-24
refs: [docs/01-requirements/PRD-VIOL-violation-management.md]
milestone: "Trust & Safety v1.0"
total_tickets: 6
completed_tickets: 0
implemented_tickets: 0
review_tickets: 0
---

## Context & Motivation
We need to implement a Violation Management System to flag, track, and manage inappropriate AI generations and malicious user prompts. This ensures SOPilot adheres to our Trust & Safety guidelines and allows administrators to ban repeat offenders.

## Scope Analysis
### Services Affected
| Service | Impact Description |
|---|---|
| user | Store violation records, manage user ban status. |
| ai-qa | Emit violation events when harmful content is detected by LLM guards. |
| gateway | Add routing for violation-related endpoints. |
| web | Admin dashboard to view violations and ban users. |

### Database Changes
- **user-service (PostgreSQL `user_db`)**:
  - Create new `violations` table (`id`, `user_id`, `reason`, `severity`, `created_at`).
  - Add `is_banned` boolean to existing `users` table.

### Event Flow
- **ai-qa-service**: Publishes `ViolationDetectedEvent` to RabbitMQ topic `trust.safety.violations`.
- **user-service**: Consumes `ViolationDetectedEvent` to persist violation records and automatically ban users reaching a threshold.

## Architecture Decisions
- **Async Violation Processing**: The AI-QA service will not directly write to the User DB. It will use event-driven messaging (RabbitMQ) to prevent tight coupling and minimize latency on generation endpoints.

## Ticket Breakdown
### Phase 1: Backend Foundation
| Ticket ID | Title | Size | Depends On |
|---|---|---|---|
| VIOL-01 | Create Violation Entity & DB Migrations in User Service | S | - |
| VIOL-02 | Implement Violation Service Logic & API | M | VIOL-01 |

### Phase 2: Integration
| Ticket ID | Title | Size | Depends On |
|---|---|---|---|
| VIOL-03 | Publish Violation Events from AI-QA Service | M | - |
| VIOL-04 | Consume Violation Events in User Service | M | VIOL-02, VIOL-03 |

### Phase 3: Frontend
| Ticket ID | Title | Size | Depends On |
|---|---|---|---|
| VIOL-05 | Add Gateway Routes for Violations | S | VIOL-02 |
| VIOL-06 | Admin Dashboard: Violation Log UI | L | VIOL-05 |

### Phase 4: Testing & Polish
| Ticket ID | Title | Size | Depends On |
|---|---|---|---|
| VIOL-07 | End-to-End Test for Trust & Safety Flow | M | VIOL-04, VIOL-06 |

## Risk Assessment
- **Event Dropping**: Ensure RabbitMQ dead-letter queues (DLQ) are configured for violation events so they aren't lost if the user service is down.

## Definition of Done
- [ ] All 7 tickets completed and merged.
- [ ] E2E tests passing for the violation detection and banning flow.
- [ ] API documentation updated in Gateway.
