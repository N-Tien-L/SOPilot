---
title: Authentication Full-Flow Design
description: Complete authentication system design including Login, Logout, Token Management, Email, Multi-Session
type: development
version: 1.0
---

# Authentication System Design - Full Flow

## Purpose

This document provides a comprehensive design of the authentication system for Poliwise, covering all auth flows from Frontend to Backend to Database to Email Service.

## When to Use

- Implementing authentication features
- Debugging auth issues
- Understanding token lifecycle
- Reviewing security implementation

---

## Authentication Features

### 1. Login

**Flow:**
```
Frontend (login page)
  → POST /api/v1/auth/login { username, password }
  → API Gateway (validates, proxies)
  → Auth Service (validates credentials, checks status, creates tokens)
  → Database (core.users, core.refresh_tokens, core.login_history)
  → Response { accessToken, refreshToken, user }
  → Frontend stores tokens
```

**Security:**
- BCrypt password verification
- Account status check (ACTIVE/DEACTIVATED/REVOKED)
- Brute-force protection (5 attempts = 15 min lock)
- Login history tracking
- Refresh token rotation

**Request:**
```json
POST /api/v1/auth/login
{
  "username": "admin",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
  "refreshToken": "a1b2c3d4e5f6...",
  "tokenType": "Bearer",
  "expiresInSeconds": 900,
  "user": {
    "userId": "uuid",
    "username": "admin",
    "email": "admin@poliwise.local",
    "role": "ADMIN"
  }
}
```

**Error Cases:**
- 401: Invalid credentials
- 403: Account deactivated/revoked/locked

---

### 2. Register (Admin Only)

**Flow:**
```
Admin (creates user form)
  → POST /api/v1/auth/register { username, email, password, role }
  → Auth Service validates
  → Database creates user
  → Email Service sends credentials to user
  → Response { userId, username, email }
```

**Security:**
- ADMIN role required
- Unique username/email validation
- Temporary password generated
- Password must be changed on first login

**Request:**
```json
POST /api/v1/auth/register
{
  "username": "newuser",
  "email": "newuser@poliwise.local",
  "password": "TempPassword123",
  "role": "USER"
}
```

---

### 3. Bulk User Creation (Admin Only)

**Flow:**
```
Admin (bulk create form)
  → POST /api/v1/users/bulk { users: [...] }
  → Auth Service validates all
  → Creates users sequentially
  → Email Service sends credentials to each user
  → Response summary { successCount, failureCount, details }
```

**Security:**
- ADMIN role required
- Max 100 users per batch
- Partial success supported (continues on error)

**Request:**
```json
POST /api/v1/users/bulk
{
  "users": [
    { "username": "user1", "email": "user1@poliwise.local", "fullName": "User One", "role": "USER" },
    { "username": "user2", "email": "user2@poliwise.local", "fullName": "User Two", "role": "MANAGER" }
  ]
}
```

**Response:**
```json
{
  "totalRequested": 2,
  "successCount": 2,
  "failureCount": 0,
  "successfulUsers": [
    { "userId": "uuid1", "username": "user1", "email": "user1@poliwise.local", "tempPassword": "Abc123!@#", "emailSent": true },
    { "userId": "uuid2", "username": "user2", "email": "user2@poliwise.local", "tempPassword": "Xyz789!@#", "emailSent": true }
  ],
  "failedUsers": []
}
```

---

### 4. Refresh Token

**Flow:**
```
Frontend (token expired)
  → POST /api/v1/auth/refresh { refreshToken }
  → Auth Service validates refresh token
  → Rotates tokens (old revoked, new created)
  → Response { newAccessToken, newRefreshToken }
```

**Security:**
- Refresh token rotation (old token revoked, new token issued)
- Token reuse detection (reuse = revoke ALL sessions)
- User status validation
- Expired token cleanup

**Request:**
```json
POST /api/v1/auth/refresh
Headers: X-User-Id: uuid
{
  "refreshToken": "a1b2c3d4e5f6..."
}
```

---

### 5. Logout

**Flow:**
```
User (logout button)
  → POST /api/v1/auth/logout { refreshToken }
  → Auth Service revokes refresh token
  → Blacklists access token
  → Response { message }
```

**Single Device Logout:**
```json
POST /api/v1/auth/logout
{
  "refreshToken": "a1b2c3d4e5f6..."
}
```

**All Devices Logout:**
```json
POST /api/v1/auth/logout-all
```

**Security:**
- Immediate token revocation
- Access token blacklisted (stored in DB)
- All refresh tokens of user revoked

---

### 6. Token Blacklist

**Purpose:** Invalidates access tokens before expiration (e.g., after logout).

**Storage:** `core.access_token_blacklist` table

**Flow:**
```
Token created with JTI (unique ID)
  ↓
User logs out
  ↓
Token JTI added to blacklist
  ↓
Future requests with this token → 401 Unauthorized
```

**Database Schema:**
```sql
CREATE TABLE core.access_token_blacklist (
    jti VARCHAR(50) PRIMARY KEY,
    user_id UUID NOT NULL,
    expired_at TIMESTAMPTZ NOT NULL,
    blacklisted_at TIMESTAMPTZ NOT NULL,
    reason VARCHAR(100)
);
```

**Cleanup:** Expired blacklist entries are periodically deleted.

---

### 7. Login History

**Purpose:** Audit trail of all login attempts (success/failure).

**Storage:** `core.login_history` table

**Flow:**
```
Login attempt
  ↓
Auth Service validates credentials
  ↓
Login history recorded
  ↓
Success: status=SUCCESS
  ↓
Failure: status=FAILED_*, failure_reason captured
```

**Database Schema:**
```sql
CREATE TABLE core.login_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    username VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_type VARCHAR(50),
    location VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
```

---

### 8. Multi-Session Management

**Purpose:** User can be logged in on multiple devices simultaneously.

**Storage:** `core.refresh_tokens` table (one per session)

**Flow:**
```
User logs in from Device A → Refresh Token A created
User logs in from Device B → Refresh Token B created
User logs in from Device C → Refresh Token C created
```

**Session Info:**
```json
GET /api/v1/auth/sessions
{
  "sessions": [
    {
      "sessionId": "uuid-A",
      "deviceInfo": "Desktop - Chrome",
      "ipAddress": "192.168.1.100",
      "createdAt": "2026-04-28T10:00:00Z",
      "expiresAt": "2026-05-05T10:00:00Z",
      "isCurrent": true
    },
    {
      "sessionId": "uuid-B",
      "deviceInfo": "Mobile - Safari",
      "ipAddress": "192.168.1.101",
      "createdAt": "2026-04-27T15:00:00Z",
      "expiresAt": "2026-05-04T15:00:00Z",
      "isCurrent": false
    }
  ]
}
```

**Revoke Single Session:**
```json
DELETE /api/v1/auth/sessions/{sessionId}
```

**Revoke All Sessions:**
```json
POST /api/v1/auth/logout-all
```

---

### 9. Forgot Password

**Flow:**
```
User (forgot password page)
  → POST /api/v1/auth/forgot-password { email }
  → Auth Service validates email exists
  → Generates new random password
  → Updates user password (hashed)
  → Email Service sends new password
  → Response { message, emailSent }
```

**Security:**
- Rate limited (3 attempts per 5 minutes per IP)
- Email existence hidden (prevents enumeration)
- Password reset sets mustChangePassword=true

**Request:**
```json
POST /api/v1/auth/forgot-password
{
  "email": "user@poliwise.local"
}
```

**Response:**
```json
{
  "message": "Nếu email tồn tại trong hệ thống, mật khẩu mới sẽ được gửi đến email của bạn.",
  "emailSent": true
}
```

---

### 10. Reset Password (Change Password)

**Flow:**
```
User (profile page)
  → POST /api/v1/auth/change-password { oldPassword, newPassword, confirmPassword }
  → Auth Service validates old password
  → Updates password (hashed)
  → Response { success, message }
```

**Security:**
- Old password required
- Password strength validation
- Cannot reuse same password
- clears mustChangePassword flag

**Request:**
```json
POST /api/v1/auth/change-password
{
  "oldPassword": "OldPass123",
  "newPassword": "NewPass456!@#",
  "confirmPassword": "NewPass456!@#"
}
```

---

## Security Implementation

### Password Hashing

- Algorithm: BCrypt (Spring Security default)
- Strength: 10 rounds
- Never log or expose raw passwords

### JWT Configuration

- Algorithm: HMAC-SHA256
- Access Token TTL: 15 minutes (PT15M)
- Refresh Token TTL: 7 days (P7D)
- Claims: sub (userId), jti (tokenId), role, status, department

### Rate Limiting

| Endpoint | Window | Max Requests |
|----------|--------|-------------|
| /auth/login | 60s | 5 |
| /auth/forgot-password | 300s | 3 |

### Brute-Force Protection

- 5 failed attempts = 15 minute lockout
- Lockout tracked per user
- Successful login resets counter

---

## Database Schema

### core.users
```sql
CREATE TABLE core.users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    department_id UUID,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ,
    must_change_password BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
```

### core.refresh_tokens
```sql
CREATE TABLE core.refresh_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    device_info VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),
    replaced_by UUID,
    created_at TIMESTAMPTZ NOT NULL
);
```

---

## Email Templates

### Account Created
- Subject: "Tài khoản Poliwise của bạn đã được tạo"
- Content: Username, temporary password, login URL, security tips

### Password Reset
- Subject: "Khôi phục mật khẩu Poliwise"
- Content: New password, security warnings, login URL

### Bulk Account Created
- Subject: "Tài khoản Poliwise - Thông tin đăng nhập"
- Content: Username, temporary password, admin name, login URL

---

## Environment Variables

```env
# Email Configuration
EMAIL_USER=xuanvietle20050228@gmail.com
EMAIL_APP_PASSWORD=tkfu mkso nbra yndd
EMAIL_ENABLED=true

# Auth JWT Configuration
AUTH_JWT_SECRET=your-256-bit-secret-key
AUTH_JWT_ISSUER=poliwise-auth-service
AUTH_ACCESS_TOKEN_TTL=PT15M
AUTH_REFRESH_TOKEN_TTL=P7D
AUTH_MAX_FAILED_ATTEMPTS=5
AUTH_LOCK_DURATION=PT15M
```

---

## API Gateway Routes

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/v1/auth/login | Public | Login |
| POST | /api/v1/auth/register | ADMIN | Register user |
| POST | /api/v1/auth/refresh | Public | Refresh token |
| POST | /api/v1/auth/forgot-password | Public | Request password reset |
| POST | /api/v1/auth/logout | JWT | Logout current device |
| POST | /api/v1/auth/logout-all | JWT | Logout all devices |
| GET | /api/v1/auth/sessions | JWT | Get active sessions |
| DELETE | /api/v1/auth/sessions/{id} | JWT | Revoke specific session |
| POST | /api/v1/auth/change-password | JWT | Change password |
| GET | /api/v1/auth/me | JWT | Get current user profile |
| POST | /api/v1/users | ADMIN | Create user |
| POST | /api/v1/users/bulk | ADMIN | Create multiple users |
| GET | /api/v1/users | ADMIN | Search users |
| GET | /api/v1/users/{id} | ADMIN | Get user details |
| PUT | /api/v1/users/{id} | ADMIN | Update user |
| POST | /api/v1/users/{id}/deactivate | ADMIN | Deactivate user |
| POST | /api/v1/users/{id}/reactivate | ADMIN | Reactivate user |
| POST | /api/v1/users/{id}/revoke | ADMIN | Revoke user |
| DELETE | /api/v1/users/{id} | ADMIN | Delete user |
| GET | /api/v1/users/{id}/login-history | ADMIN | Get login history |

---

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | /login | Login form |
| Forgot Password | /forgot-password | Password reset request |
| Profile | /profile | User profile + password change |
| Sessions | /sessions | Active sessions management |

---

**Last Updated**: 2026-04-28
**Maintained By**: Auth Team
