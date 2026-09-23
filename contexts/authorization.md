# Authorization & Access Control

## Overview

Poliwise uses Role-Based Access Control (RBAC) with JWT authentication across all services.

## Role Hierarchy

```
ADMIN (level 3)
   │
   ├── MANAGER (level 2)
   │      │
   │      └── USER (level 1)
   │
   └── USER (level 1)
```

Roles are hierarchical:
- ADMIN has all permissions
- MANAGER has all USER permissions plus additional management features
- USER has basic read access

## JWT Claims

```json
{
  "sub": "user-uuid",
  "username": "john.doe",
  "email": "john@company.com",
  "role": "ADMIN",
  "department": "department-uuid",
  "status": "ACTIVE",
  "iat": 1234567890,
  "exp": 1234571490
}
```

## Permission Matrix

### Document Management

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View documents | ✅ | ✅ | ✅ |
| Search documents | ✅ | ✅ | ✅ |
| Download documents | ✅ | ✅ | ✅ |
| Upload documents | ❌ | ❌ | ✅ |
| Delete documents | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ✅ | ✅ |

### Metadata Management

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View categories | ✅ | ✅ | ✅ |
| Manage categories | ❌ | ❌ | ✅ |
| View tags | ✅ | ✅ | ✅ |
| Manage tags | ❌ | ✅ | ✅ |
| Set access rules | ❌ | ❌ | ✅ |

### Document Lifecycle

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View drafts | Own only | Own only | ✅ |
| Publish documents | ❌ | ❌ | ✅ |
| Archive documents | ❌ | ❌ | ✅ |

### User Management

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View own profile | ✅ | ✅ | ✅ |
| View all users | ❌ | ❌ | ✅ |
| Create users | ❌ | ❌ | ✅ |
| Update users | ❌ | ❌ | ✅ |
| Deactivate users | ❌ | ❌ | ✅ |

### Analytics

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View analytics | ❌ | ✅ | ✅ |
| Export reports | ❌ | ✅ | ✅ |
| View audit logs | ❌ | ✅ | ✅ |

### AI Q&A

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| Ask questions | ✅ | ✅ | ✅ |
| View conversation history | Own only | ✅ | ✅ |
| Provide answers | ❌ | ✅ | ✅ |

## Implementation

### API Gateway (NestJS)

JWT validation and role checking in guards:

```typescript
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles(UserRole.ADMIN)
@Post('documents/upload')
handleDocumentUpload(@Req() request: Request) {
  // Only ADMIN can upload documents
}
```

### Spring Boot Services

Annotation-based authorization:

```java
@PreAuthorize("hasRole('ADMIN')")
public ResponseEntity<DocumentResponse> upload(...) {
  // Only ADMIN can access
}
```

### Frontend

Role-based UI rendering:

```typescript
const { user, isAdmin } = useAuth();
{isAdmin && <UploadButton />}
```

## Access Rules

Document-level access control via access rules (managed by `metadata-service`):

### Rule Types

| Type | Description |
|------|-------------|
| `ROLE` | Grant/deny access by role (ADMIN, MANAGER, USER) |
| `DEPARTMENT` | Grant/deny access by department |
| `USER` | Grant/deny access by specific user |

### Permission Types

| Permission | Description |
|------------|-------------|
| `VIEW` | Allow viewing the document |
| `DENY` | Explicitly deny access |

### Rule Evaluation (OR Algorithm)

When multiple rules exist for a document, access is determined by:

1. **ADMIN always has access** — admin role bypasses all rules
2. **PUBLIC documents** — accessible to all authenticated users
3. **DENY rules evaluated FIRST** — if any DENY rule matches the user, access is denied
4. **VIEW rules evaluated SECOND (OR logic)** — if at least one VIEW rule matches, access is granted
5. **No matching rule = deny by default**

```
User has access = (ADMIN role) OR (PUBLIC doc) OR (has VIEW rule AND no DENY rule)
```

**Example:**
- Document has rules: `[ROLE=USER:VIEW, DEPARTMENT=HR:VIEW]`
- A USER in Finance department → has access (matches USER role rule)
- A MANAGER in HR department → has access (matches DEPARTMENT rule)
- A USER explicitly DENY'd for that department → no access (DENY takes priority)

### Duplicate Rules

Rules targeting different targets are always allowed (no 100%-identical duplicate enforcement). Rules targeting the same target will update the existing rule instead of creating a duplicate.

### Simulation Feature

ADMIN can preview who in the company has access to a document via the simulation endpoint:
- Shows all users grouped by access (granted/denied) with reasoning
- Helps verify access rules before deployment

### Default Behavior on Upload

When a new document is uploaded:
- Metadata is auto-created with `accessLevel = RESTRICTED`
- **No access rules exist initially**
- **Only ADMIN can access the document** until access rules are added
- To make a document public, add a `ROLE=USER:VIEW` rule or set `accessLevel = PUBLIC`

## Security Considerations

### Token Management

- Access token: 1 hour expiry
- Refresh token: 7 days expiry
- Tokens stored in localStorage (with refresh mechanism)
- 401 triggers automatic refresh and retry

### Password Policy

- Minimum 8 characters
- Must include uppercase, lowercase, number
- Password change required after 90 days
- 5 failed login attempts = account lock

### Session Management

- Multiple sessions supported
- View and revoke sessions from profile
- Logout all sessions option
- Session timeout: 30 minutes inactivity
