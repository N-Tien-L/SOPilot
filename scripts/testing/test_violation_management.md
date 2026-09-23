# Plan: Test Section 14 — User Behavior & Violation Management

## Overview

Test the complete violation management flow from toxic query detection through strike counting, escalation, warnings, and admin review.

---

## Test Categories

### 1. AI QA Service — Violation Event Publishing

**What to test:**
- Layer 1 blocks toxic query → violation event published to RabbitMQ
- Event payload contains correct user_id, violation_type, severity, evidence, source
- Admin users bypass escalation (violations logged but no strikes)

**Test cases:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T1.1 | User sends toxic query | Violation event published with user_id, TOXIC_QUERY, severity=HIGH |
| T1.2 | Admin sends toxic query | Event published but escalation NOT triggered |
| T1.3 | Normal user sends clean query | No violation event published |

**How to test:**
```bash
# Start services and monitor RabbitMQ
cd services/ai-qa-service
uv run uvicorn src.main:app --reload --port 8086

# In another terminal, consume violation events
# Check logs for "violation_published" entries
```

---

### 2. Feedback Service — Violation Consumer & Logging

**What to test:**
- Consumer receives violation events from queue `poliwise.feedback.violation`
- Violation record created in `analytics.user_violations` table
- Strike count incremented in user-service via Feign client

**Test cases:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T2.1 | Violation event received | Violation record created with status=PENDING |
| T2.2 | Strike count incremented | user-service strike_count += 1 |
| T2.3 | Admin violation logged | No strike increment (exempt) |

**How to test:**
```bash
# Check feedback-service logs
# Query database:
SELECT * FROM analytics.user_violations ORDER BY created_at DESC LIMIT 10;

# Check user strike count
SELECT id, username, strike_count FROM core.users WHERE strike_count > 0;
```

---

### 3. Escalation Checker — Strike Thresholds

**What to test:**
- 3 strikes → Warning sent
- 5 strikes → User deactivated
- 10 strikes → User revoked

**Test cases:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T3.1 | User reaches 3 strikes | Warning created in `analytics.user_warnings` |
| T3.2 | User reaches 5 strikes | User status = DEACTIVATED |
| T3.3 | User reaches 10 strikes | User status = REVOKED |
| T3.4 | Warning expiry | Warnings expire after 30 days |

**How to test:**
```sql
-- Manually set strikes to test escalation
UPDATE core.users SET strike_count = 3 WHERE id = 'test-user-uuid';

-- Trigger escalation by sending a violation
-- Check results:
SELECT * FROM analytics.user_warnings;
SELECT id, username, status, strike_count FROM core.users;
```

---

### 4. User Service — Strike Count Endpoints

**What to test:**
- Internal endpoints work correctly
- Strike increment/decrement/reset functions
- Status change (deactivate/revoke) works

**Test cases:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T4.1 | POST /strikes/increment | strike_count += 1, last_violation_at updated |
| T4.2 | POST /strikes/decrement | strike_count -= 1 (min 0) |
| T4.3 | POST /strikes/reset | strike_count = 0, last_violation_at = NULL |
| T4.4 | POST /status?status=DEACTIVATED | User status changes |

**How to test:**
```bash
# Test internal endpoints (requires internal network or token)
curl -X POST http://localhost:8082/api/v1/internal/users/{userId}/strikes/increment

# Check results
curl http://localhost:8082/api/v1/internal/users/{userId}/strikes
```

---

### 5. ViolationController — API Endpoints

**What to test:**
- User can view own violations
- User can submit appeal
- Admin can view review queue
- Admin can review/dismiss violations
- Admin can reset strike counts

**Test cases:**
| ID | Endpoint | Role | Expected Result |
|----|----------|------|-----------------|
| T5.1 | GET /api/v1/violations/me | USER | Returns user's violations |
| T5.2 | POST /api/v1/violations/{id}/appeal | USER | Appeal submitted |
| T5.3 | GET /api/v1/violations/queue | ADMIN | Returns pending violations |
| T5.4 | POST /api/v1/violations/{id}/review | ADMIN | Violation reviewed, action taken |
| T5.5 | POST /api/v1/violations/users/{id}/reset-strikes | ADMIN | Strike count reset to 0 |
| T5.6 | GET /api/v1/violations/me/warnings | USER | Returns user's active warnings |
| T5.7 | POST /api/v1/violations/warnings/{id}/acknowledge | USER | Warning marked as read |

**How to test:**
```bash
# Get JWT token
TOKEN=$(curl -s -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.data.accessToken')

# Test endpoints
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/v1/violations/me

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3001/api/v1/violations/queue
```

---

### 6. API Gateway — Route Proxying

**What to test:**
- Routes correctly proxy to feedback-service
- RBAC enforced (ADMIN-only routes blocked for USER)

**Test cases:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T6.1 | USER calls /violations/queue | 403 Forbidden |
| T6.2 | ADMIN calls /violations/queue | 200 OK, proxied to feedback |
| T6.3 | USER calls /violations/me | 200 OK |

**How to test:**
```bash
# Test with different user roles
USER_TOKEN="..."  # USER role token
ADMIN_TOKEN="..." # ADMIN role token

# Should fail
curl -H "Authorization: Bearer $USER_TOKEN" \
  http://localhost:3001/api/v1/violations/queue

# Should succeed
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:3001/api/v1/violations/queue
```

---

### 7. End-to-End Flow Test

**Complete flow:**
1. USER sends toxic query → Layer 1 blocks → Violation event published
2. ViolationConsumer receives → Creates violation record → Increments strike count
3. At 3 strikes → EscalationChecker sends warning
4. USER views warnings via API
5. USER submits appeal via API
6. ADMIN reviews appeal → Approves
7. Strike count decremented, violation soft-deleted

**Test case:**
| ID | Scenario | Expected Result |
|----|----------|-----------------|
| T7.1 | Full violation lifecycle | All steps complete successfully |

**How to test:**
```bash
# 1. Send toxic query as test user
curl -X POST http://localhost:3001/api/v1/ai/chat \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "test toxic content"}'

# 2. Check violation created (repeat 3x for warning)
# 3. Check warnings
curl -H "Authorization: Bearer $USER_TOKEN" \
  http://localhost:3001/api/v1/violations/me/warnings

# 4. Submit appeal
curl -X POST http://localhost:3001/api/v1/violations/{id}/appeal \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"appealText": "This was a test, please dismiss"}'

# 5. Admin reviews appeal
curl -X POST "http://localhost:3001/api/v1/violations/appeals/{id}/review?approved=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 6. Verify strike count decremented
```

---

## 8. Playwright E2E Tests

**Test file:** `scripts/testing/e2e-violation-management.spec.ts`

**Run:**
```bash
cd frontend/web
npx playwright test ../../scripts/testing/e2e-violation-management.spec.ts
```

### Test Suites

| Suite | Tests | Description |
|-------|-------|-------------|
| User - View Own Violations | 3 | View violation history, timestamps, filters |
| User - Submit Appeal | 4 | Appeal button, modal, submission, status |
| User - Warnings | 3 | Warning banner, list, acknowledge |
| Admin - Violation Queue | 4 | Access queue, view pending, details, filters |
| Admin - Review & Take Action | 3 | Action buttons, dismiss, view history |
| Admin - Reset Strikes | 2 | Reset button, reset action |
| Admin - Appeals | 4 | Appeals queue, view text, approve, reject |
| E2E - Complete Flow | 1 | Full violation → appeal → review cycle |
| RBAC - Permissions | 2 | User denied, admin allowed |

### Required Page Routes

The frontend should implement these routes:

| Route | Component | Access | Description |
|-------|-----------|--------|-------------|
| `/violations` | ViolationsPage | USER+ | View own violations |
| `/violations/warnings` | WarningsPage | USER+ | View own warnings |
| `/admin/violations` | AdminViolationQueue | ADMIN | Review queue |
| `/admin/violations/appeals` | AppealsPage | ADMIN | Review appeals |

---

## Test Data Setup

```sql
-- Create test users
INSERT INTO core.users (id, username, email, password_hash, role, status, created_at, updated_at, strike_count)
VALUES 
  ('00000000-0000-0000-0000-000000000001', 'testuser', 'test@example.com', '$2a$10$...', 'USER', 'ACTIVE', NOW(), NOW(), 0),
  ('00000000-0000-0000-0000-000000000002', 'testadmin', 'admin@example.com', '$2a$10$...', 'ADMIN', 'ACTIVE', NOW(), NOW(), 0);

-- Reset test data before each test run
UPDATE core.users SET strike_count = 0, last_violation_at = NULL WHERE id IN ('00000000-0000-0000-0000-000000000001');
DELETE FROM analytics.user_violations WHERE user_id = '00000000-0000-0000-0000-000000000001';
DELETE FROM analytics.user_warnings WHERE user_id = '00000000-0000-0000-0000-000000000001';
```

---

## Manual Test Checklist

- [ ] Layer 1 blocks toxic query
- [ ] Violation event appears in RabbitMQ
- [ ] Violation record created in DB
- [ ] Strike count incremented
- [ ] 3 strikes → Warning created
- [ ] 5 strikes → User deactivated
- [ ] 10 strikes → User revoked
- [ ] USER can view own violations
- [ ] USER can submit appeal
- [ ] USER can view own warnings
- [ ] USER can acknowledge warning
- [ ] ADMIN can view violation queue
- [ ] ADMIN can review/dismiss violation
- [ ] ADMIN can reset strike count
- [ ] ADMIN can review appeals
- [ ] Admin violations exempt from escalation
- [ ] API gateway routes protected correctly

---

## Automated Test Script

```python
# scripts/testing/test_violation_management.py
import requests
import time

BASE_URL = "http://localhost:3001/api/v1"

def test_violation_flow():
    # Setup: Get tokens
    user_token = get_token("testuser", "password")
    admin_token = get_token("testadmin", "password")
    
    # T1: Send toxic query
    response = requests.post(
        f"{BASE_URL}/ai/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "test toxic content"}
    )
    assert response.status_code == 200
    
    # T2: Check violation created
    response = requests.get(
        f"{BASE_URL}/violations/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200
    violations = response.json()["data"]["content"]
    assert len(violations) >= 1
    
    # T3: Admin can view queue
    response = requests.get(
        f"{BASE_URL}/violations/queue",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    
    # T4: User CANNOT view queue (403)
    response = requests.get(
        f"{BASE_URL}/violations/queue",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    
    print("All tests passed!")
```

---

## Notes

1. **RabbitMQ**: Ensure queue `poliwise.feedback.violation` is created and bound
2. **Database**: Run migrations for new tables `user_violations` and `user_warnings`
3. **Feign**: Verify feedback-service can reach user-service on internal network
4. **Admin Test**: Always verify admin exemption is working (no accidental lockout)
