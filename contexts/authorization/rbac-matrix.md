---
title: RBAC Matrix and Implementation
description: Role-Based Access Control matrix and implementation guidance for guards and decorators
type: authorization
version: 1.0
---

# RBAC Matrix & Implementation Guide

## Purpose

Provides AI agents with the definitive Role-Based Access Control (RBAC) matrix for Poliwise and implementation patterns for both NestJS (API Gateway) and Spring Boot (Java services).

## When to Use

- Implementing endpoint protection
- Creating new services with authorization
- Testing permission boundaries
- Debugging access control issues

---

## RBAC Matrix

| STT | Functionality | User | Manager | Admin |
|:--- |:--- |:---:|:---:|:---:|
| 01 | AI Q&A Chat | ✅ | ✅ | ✅ |
| 02 | View Personal Chat History | ✅ | ✅ | ✅ |
| 03 | Like / Dislike Answers | ✅ | ✅ | ✅ |
| 04 | View Personal Profile | ✅ | ✅ | ✅ |
| 05 | Update Personal Profile | ✅ | ✅ | ✅ |
| 06 | Change Password | ✅ | ✅ | ✅ |
| 07 | View Active Sessions | ✅ | ✅ | ✅ |
| 08 | Revoke Other Sessions | ✅ | ✅ | ✅ |
| 09 | Logout All Devices | ✅ | ✅ | ✅ |
| 10 | View Statistics Reports | ❌ | ✅ | ✅ |
| 11 | View Analytics Dashboard | ❌ | ✅ | ✅ |
| 12 | View Unanswered Questions | ❌ | ✅ | ✅ |
| 13 | Upload Knowledge Documents | ❌ | ❌ | ✅ |
| 14 | Manage Document Metadata | ❌ | ❌ | ✅ |
| 15 | Create / Lock / Revoke User Accounts | ❌ | ❌ | ✅ |
| 16 | Manage Document Versions | ❌ | ❌ | ✅ |
| 17 | Create Single User (with email) | ❌ | ❌ | ✅ |
| 18 | Create Bulk Users (with email) | ❌ | ❌ | ✅ |
| 19 | View User Login History | ❌ | ❌ | ✅ |
| 20 | Deactivate / Reactivate Users | ❌ | ❌ | ✅ |
| 21 | **Search Users (Admin/Manager)** | ❌ | ✅ | ✅ |
| 22 | **View User Detail (full info)** | ❌ | ✅ | ✅ |
| 23 | **Update User Role** | ❌ | ❌ | ✅ |
| 24 | **Assign User to Department** | ❌ | ❌ | ✅ |
| 25 | **Soft Delete User** | ❌ | ❌ | ✅ |
| 26 | **View All Departments** | ❌ | ❌ | ✅ |
| 27 | **Create Department** | ❌ | ❌ | ✅ |
| 28 | **Edit Department** | ❌ | ❌ | ✅ |
| 29 | **Deactivate/Activate Department** | ❌ | ❌ | ✅ |
| 30 | **View Department Users** | ❌ | ❌ | ✅ |
| 31 | **View Own Violation History** | ✅ | ✅ | ✅ |
| 32 | **Submit Appeal for Own Violation** | ✅ | ✅ | ✅ |
| 33 | **View Own Warnings** | ✅ | ✅ | ✅ |
| 34 | **Acknowledge Own Warning** | ✅ | ✅ | ✅ |
| 35 | **View All Users' Violations (Admin Queue)** | ❌ | ❌ | ✅ |
| 36 | **Review / Dismiss Violations** | ❌ | ❌ | ✅ |
| 37 | **Reset Strike Count** | ❌ | ❌ | ✅ |
| 38 | **View Pending Appeals** | ❌ | ❌ | ✅ |
| 39 | **Review Appeals** | ❌ | ❌ | ✅ |
| 40 | **View Violation Statistics** | ❌ | ❌ | ✅ |

## Role Definitions

### USER
- **Focus**: Primary AI user, knowledge consumer
- **Capabilities**: Chat, view own history, feedback, personal profile management
- **System Impact**: Low - consumer only

### MANAGER
- **Includes**: All USER permissions
- **Additional**: Monitoring and analytics capabilities
- **Use Cases**: Track team engagement, identify knowledge gaps via unanswered questions, generate reports
- **System Impact**: Medium - read-heavy on analytics data

### ADMIN
- **Highest Privilege**: Full system control
- **Capabilities**: All MANAGER + USER permissions + data management + user administration
- **Responsibilities**: Document upload/metadata, user lifecycle (create, lock, revoke), version control
- **System Impact**: High - write operations across multiple schemas

---

## Implementation Patterns

### NestJS (API Gateway)

#### Role Decorator

```typescript
// common/decorators/roles.decorator.ts
import { SetMetadata } from '@nestjs/common';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

#### RBAC Guard

```typescript
// common/guards/rbac.guard.ts
import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JwtService } from '@nestjs/jwt';
import { ROLES_KEY } from '../decorators/roles.decorator';

@Injectable()
export class RbqGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private jwtService: JwtService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (!requiredRoles) {
      return true; // No @Roles() decorator = public to authenticated users
    }

    const request = context.switchToHttp().getRequest();
    const user = request.user; // Set by JwtAuthGuard
    
    if (!user || !user.role) {
      return false;
    }

    // Check if user role matches any required role
    return requiredRoles.includes(user.role);
  }
}
```

#### Usage

```typescript
// ai/chat.controller.ts
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles('USER', 'MANAGER', 'ADMIN')  // All three roles allowed
@Post('chat')
async chat(@Body() dto: ChatDto) {
  return this.aiService.chat(dto);
}

// admin/users.controller.ts
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles('ADMIN')  // Admin only
@Post('users')
async createUser(@Body() dto: CreateUserDto) {
  return this.userService.create(dto);
}
```

### Spring Boot (Java Services)

#### Role-Based Method Security

```java
// Enable global method security in main application class
@EnableGlobalMethodSecurity(prePostEnabled = true)
@SpringBootApplication
public class AuthServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthServiceApplication.class, args);
    }
}
```

#### Controller-Level Annotations

```java
@RestController
@RequestMapping("/api/v1/admin")
public class AdminController {

    @PostMapping("/users")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest request) {
        return ResponseEntity.ok(userService.createUser(request));
    }

    @DeleteMapping("/users/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> deleteUser(@PathVariable UUID id) {
        userService.deleteUser(id);
        return ResponseEntity.noContent().build();
    }
}
```

#### Service-Level Annotations

```java
@Service
public class DocumentService {

    @PreAuthorize("hasAnyRole('ADMIN')")
    public Document uploadDocument(MultipartFile file, DocumentMetadata metadata) {
        // Only ADMIN can upload
    }

    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public Document getDocument(UUID id) {
        // All authenticated roles can view
    }
}
```

#### Custom Permission Evaluator (for complex ACL)

If you need to check `document_access_rules` dynamically:

```java
@Component
public class DocumentPermissionEvaluator implements PermissionEvaluator {

    @Autowired
    private DocumentRepository documentRepository;

    @Override
    public boolean hasPermission(
        Authentication authentication,
        Object targetDomainObject,
        Object permission
    ) {
        if (!(targetDomainObject instanceof Document)) {
            return false;
        }

        Document document = (Document) targetDomainObject;
        String username = authentication.getName();
        String role = authentication.getAuthorities().iterator().next().getAuthority();

        // Query metadata.document_access_rules
        return documentRepository.userHasAccess(
            document.getId(),
            username,
            role,
            authentication.getDetails()  // department_id, etc.
        );
    }
}
```

---

## Endpoint Protection Reference

### Public Endpoints (No Auth Required)

```typescript
// api-gateway/src/auth/auth.controller.ts
@Public()  // Custom decorator skips JWT guard
@Post('auth/login')
async login(@Body() dto: LoginDto) { ... }

@Public()
@Get('health')
healthCheck() { return { status: 'ok' }; }
```

### Role Hierarchy

The roles are strictly hierarchical:

```
ADMIN
  └─ MANAGER
       └─ USER
```

**Implementation**: In both NestJS and Spring Boot, explicit role checks are required. There is **no automatic role inheritance**. If a route needs both USER and MANAGER access, you must list both: `@Roles('USER', 'MANAGER')`.

If you want automatic role inheritance, configure:

**Spring Security**:
```java
@Configuration
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
                .antMatchers("/api/v1/ai/**").hasAnyRole("USER", "MANAGER", "ADMIN")
                .antMatchers("/api/v1/analytics/**").hasAnyRole("MANAGER", "ADMIN")
                .antMatchers("/api/v1/admin/**").hasRole("ADMIN");
    }
}
```

**NestJS**: Use a utility function:
```typescript
function expandRoles(roles: string[]): string[] {
    const allRoles = ['USER', 'MANAGER', 'ADMIN'];
    const expanded = new Set<string>();
    
    for (const role of roles) {
        const roleIndex = allRoles.indexOf(role);
        if (roleIndex !== -1) {
            for (let i = roleIndex; i < allRoles.length; i++) {
                expanded.add(allRoles[i]);
            }
        }
    }
    return Array.from(expanded);
}

// Usage:
@Roles('MANAGER')  // Automatically grants USER too (if you call expandRoles in guard)
@Roles('ADMIN')    // Grants all
```

**Recommendation**: Keep explicit checks for clarity. Role hierarchy is conceptual, not automatic.

---

## Testing Authorization

### Unit Test Pattern (NestJS)

```typescript
describe('ChatController', () => {
  let controller: ChatController;
  let mockAuthService: MockAuthService;

  beforeEach(async () => {
    mockAuthService = {
      validateToken: jest.fn().mockResolvedValue({
        userId: 'user-uuid',
        role: 'USER',
        departmentId: 'dept-uuid',
      }),
    };

    const module: TestingModule = await Test.createTestingModule({
      controllers: [ChatController],
      providers: [{ provide: AuthService, useValue: mockAuthService }],
    }).compile();

    controller = module.get<ChatController>(ChatController);
  });

  it('should allow USER to access chat', async () => {
    const req = { user: { role: 'USER' } } as any;
    const guard = new RolesGuard(new Reflector());
    const canActivate = await guard.canActivate({
      getHandler: () => ({ /* with @Roles('USER','MANAGER','ADMIN') */ }),
      getHandler: () => ({}),
      switchToHttp: () => ({ getRequest: () => req }),
    } as ExecutionContext);
    
    expect(canActivate).toBe(true);
  });

  it('should deny USER access to admin endpoints', async () => {
    const req = { user: { role: 'USER' } } as any;
    const guard = new RolesGuard(new Reflector());
    // Handler has @Roles('ADMIN')
    // Expect false
  });
});
```

### Integration Test (Full Request Flow)

```typescript
describe('Auth endpoints (e2e)', () => {
  it('/api/v1/admin/users (POST) returns 403 for non-admin', async () => {
    const token = await loginAsUser('regular-user@example.com', 'password');
    
    const response = await request({
      method: 'POST',
      url: '/api/v1/admin/users',
      headers: { Authorization: `Bearer ${token}` },
      body: { username: 'newuser', email: 'new@example.com', password: 'pass123' },
    });

    expect(response.status).toBe(403);
  });
});
```

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `@Roles()` decorator not working | Forgot to add `RolesGuard` to `useGuards()` | Add `RolesGuard` to controller method or controller class |
| All authenticated users bypass role checks | Using `@Public()` decorator on controller | Remove `@Public()`, ensure `JwtAuthGuard` runs |
| Role names case mismatch | Database stores 'admin' but code checks 'ADMIN' | Normalize: store uppercase in DB, transform during token creation |
| User can access admin routes | Role hierarchy not understood | Explicitly list roles in `@Roles()`, don't assume inheritance |
| 403 on valid user request | User's role not in required roles list | Verify user's role in JWT payload; update role mapping if needed |

---

## Audit & Compliance

**Important**: All role changes (user → manager, admin → user, account revocation) must be logged to `analytics.audit_logs`.

Example audit log entry:
```sql
INSERT INTO analytics.audit_logs (
    user_id, username, action, resource_type, resource_id,
    old_value, new_value, ip_address, created_at
) VALUES (
    'admin-uuid', 'admin_user', 'ROLE_CHANGED', 'USER', 'target-user-uuid',
    '{"role": "USER"}', '{"role": "ADMIN"}', '192.168.1.1', NOW()
);
```

---

## References

- **Dual-Strategy Auth**: `contexts/authorization/dual-strategy.md` - detailed ACL patterns
- **Database Schema**: `contexts/database/schema.md` - `core.users`, `metadata.document_access_rules`
- **Event Contracts**: `contexts/service-boundaries/events.md` - `user.status.changed` event handling
- **API Specifications**: `contexts/service-boundaries/api-contracts.md` - endpoint requirements

---

**Last Updated**: 2026-04-08
**Maintained By**: Security & Auth Team
