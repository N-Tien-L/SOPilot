---
title: AI Agent Knowledge Base
description: Comprehensive guide for AI agents working on the Poliwise codebase
type: reference
version: 1.0
---

# AI Agent Knowledge Base - Poliwise

## Purpose

This is the primary reference for AI agents implementing features, fixing bugs, or making architectural decisions in Poliwise. It consolidates critical patterns, code examples, and architectural decisions into a single navigable document.

## Quick Start

### System Essence

**Poliwise** is an AI-powered Enterprise Knowledge Platform enabling employees to ask natural-language questions about company policies and internal documents, receiving AI-generated answers with source citations.

### Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend | Next.js 16 (App Router) | 16.1.6 |
| API Gateway | NestJS | 11.x |
| Microservices | Spring Boot | 3.4.3 |
| AI Services | FastAPI (Python) | 0.115+ |
| Database | PostgreSQL 16 | + pgvector |
| Message Queue | RabbitMQ | 3.13 |

### Service Ports

| Service | Port | Technology |
|---------|------|------------|
| Frontend | 3000 | Next.js |
| API Gateway | 3001 | NestJS |
| auth-service | 8081 | Spring Boot |
| user-service | 8082 | Spring Boot |
| knowledge-service | 8083 | Spring Boot |
| metadata-service | 8084 | Spring Boot |
| feedback-service | 8085 | Spring Boot |
| ai-qa-service | 8086 | FastAPI |
| ingestion-service | 8088 | FastAPI |

### Key Directories

```
Poliwise/
├── frontend/web/           # Next.js frontend
│   ├── app/               # App Router pages
│   ├── components/        # UI components (ui/, layout/, chat/, documents/)
│   ├── services/          # API client layer
│   ├── lib/api.ts         # Centralized API client (1800+ lines)
│   ├── store/             # Zustand stores (auth, ui, preferences)
│   ├── types/             # TypeScript types
│   └── interfaces/        # Model interfaces
├── services/
│   ├── api-gateway/        # NestJS gateway
│   │   └── src/
│   │       ├── auth/      # JWT validation, strategies
│   │       ├── common/    # Guards, decorators, filters, interceptors
│   │       ├── proxy/     # Request routing and proxying
│   │       └── health/    # Health checks
│   ├── auth-service/      # Authentication & users
│   ├── user-service/      # User profiles
│   ├── knowledge-service/ # Documents & files
│   ├── metadata-service/  # Categories, tags, access rules
│   ├── feedback-service/  # Analytics & feedback
│   ├── ai-qa-service/     # AI Q&A (FastAPI)
│   └── ingestion-service/  # Document processing (FastAPI)
├── contexts/              # Architecture documentation
└── infrastructure/         # Docker, init-db
```

---

## Spring Boot Service Patterns

### Package Structure

```java
com.poliwise.<service-name>/
├── config/           # Configuration classes
├── controller/       # REST controllers
├── dto/
│   ├── request/      # Input DTOs (records)
│   ├── response/     # Output DTOs (records)
│   └── event/        # Event DTOs
├── entity/           # JPA entities
├── enums/            # Enumerations
├── event/            # Event publishers
├── exception/        # Custom exceptions & global handler
├── mapper/           # Entity-DTO mappers
├── repository/       # Spring Data repositories
├── security/         # Security components
└── service/          # Business logic services
```

### Controller Pattern

```java
@RestController
@RequestMapping("/api/v1/<resource>")
@RequiredArgsConstructor
public class ResourceController {

    private final ResourceService resourceService;

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> create(@Valid @RequestBody CreateRequest request) {
        var result = resourceService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }

    @GetMapping("/{id}")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<?> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(resourceService.findById(id));
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<?> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(resourceService.findAll(page, size));
    }
}
```

**Key Patterns:**
- `@RestController` + `@RequestMapping` for route grouping
- `@RequiredArgsConstructor` for constructor injection
- `@Valid` for bean validation on request bodies
- `@PreAuthorize` for role-based access control
- `ResponseEntity<?>` as return type
- Use `UUID` for all entity IDs

### Service Pattern

```java
@Service
@RequiredArgsConstructor
public class ResourceService {

    private static final Logger log = LoggerFactory.getLogger(ResourceService.class);

    private final ResourceRepository resourceRepository;

    @Transactional
    public ResourceResponse create(CreateRequest request) {
        // Validate uniqueness
        if (resourceRepository.existsByNameIgnoreCase(request.name())) {
            throw conflict("Resource with this name already exists");
        }

        // Build entity
        Resource entity = Resource.builder()
                .id(UUID.randomUUID())
                .name(request.name())
                .createdAt(OffsetDateTime.now(ZoneOffset.UTC))
                .build();

        // Save and return
        Resource saved = resourceRepository.save(entity);
        return toResponse(saved);
    }

    @Transactional(readOnly = true)
    public ResourceResponse findById(UUID id) {
        return resourceRepository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> notFound("Resource not found"));
    }

    private ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }

    private ResponseStatusException notFound(String message) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, message);
    }
}
```

**Key Patterns:**
- `@Transactional` on mutation methods
- `@Transactional(readOnly = true)` on read methods
- Slf4j Logger for logging
- Builder pattern for entity construction
- Use `OffsetDateTime.now(ZoneOffset.UTC)` for timestamps
- Private helper methods for error responses

### Repository Pattern

```java
@Repository
public interface ResourceRepository extends JpaRepository<Resource, UUID> {

    Optional<Resource> findByNameIgnoreCase(String name);

    boolean existsByNameIgnoreCase(String name);

    // Pessimistic locking for updates
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select r from Resource r where r.id = :id")
    Optional<Resource> findByIdForUpdate(@Param("id") UUID id);

    // Custom JPQL with parameters
    @Query("""
            select r from Resource r
            where (:search is null or :search = ''
               or lower(r.name) like lower(concat('%', :search, '%')))
              and (:status is null or r.status = :status)
            """)
    Page<Resource> search(
            @Param("search") String search,
            @Param("status") ResourceStatus status,
            Pageable pageable);

    // Bulk update
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Resource r set r.status = :status where r.id in :ids")
    int bulkUpdateStatus(@Param("ids") List<UUID> ids, @Param("status") ResourceStatus status);
}
```

**Key Patterns:**
- Extend `JpaRepository<Entity, UUID>`
- Method naming conventions (`findBy...`, `existsBy...`)
- Custom JPQL with `@Query`
- Pessimistic locking with `@Lock(LockModeType.PESSIMISTIC_WRITE)`
- `@Modifying` for update/delete with transaction management

### Entity Pattern

```java
@Entity
@Table(name = "resources", schema = "service_schema")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Resource {

    @Id
    @Column(columnDefinition = "uuid", nullable = false)
    private UUID id;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false)
    private ResourceStatus status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    @ToString.Exclude
    private Department department;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    @PrePersist
    void onCreate() {
        if (createdAt == null) createdAt = OffsetDateTime.now(ZoneOffset.UTC);
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = OffsetDateTime.now(ZoneOffset.UTC);
    }
}
```

**Key Patterns:**
- Lombok annotations (`@Getter`, `@Setter`, `@Builder`, etc.)
- PostgreSQL schema specification (`schema = "schema_name"`)
- `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` for PostgreSQL enums
- `@PrePersist` / `@PreUpdate` for lifecycle timestamps
- `@ToString.Exclude` on lazy-loaded relations

### DTO Pattern (Java Records)

```java
// Request DTO
public record CreateRequest(
        @NotBlank @Size(max = 255) String name,
        @NotNull ResourceStatus status,
        UUID departmentId
) {}

// Response DTO with nested records
public record ResourceResponse(
        UUID id,
        String name,
        ResourceStatus status,
        DepartmentInfo department
) {
    public record DepartmentInfo(UUID id, String name) {}
}
```

**Key Patterns:**
- Java records for immutable DTOs
- Validation annotations from `jakarta.validation.constraints`
- Nested record definitions for related data

### Enum Pattern

```java
@Getter
public enum ResourceStatus {
    ACTIVE("Hoạt động"),
    INACTIVE("Không hoạt động"),
    PENDING("Đang chờ");

    private final String label;

    ResourceStatus(String label) {
        this.label = label;
    }
}
```

---

## RabbitMQ Event Patterns

### Publisher Pattern

```java
@Component
@RequiredArgsConstructor
public class ResourceEventPublisher {

    private final RabbitTemplate rabbitTemplate;

    public void publishResourceCreated(ResourceCreatedEvent event) {
        rabbitTemplate.convertAndSend(
                "poliwise.events",
                "resource.created",
                event
        );
        log.info("Published ResourceCreatedEvent: id={}", event.id());
    }

    public void publishResourceDeleted(ResourceDeletedEvent event) {
        rabbitTemplate.convertAndSend(
                "poliwise.events",
                "resource.deleted",
                event
        );
        log.info("Published ResourceDeletedEvent: id={}", event.id());
    }
}
```

### Consumer Pattern

```java
@Component
@RequiredArgsConstructor
public class ResourceEventConsumer {

    private final DependentService dependentService;

    @RabbitListener(queues = "poliwise.resource.created")
    public void handleResourceCreated(Map<String, Object> message) {
        try {
            UUID id = UUID.fromString(String.valueOf(message.get("id")));
            dependentService.onResourceCreated(id);
        } catch (Exception e) {
            log.error("Failed to handle resource created event", e);
            throw e; // Re-throw for DLQ
        }
    }
}
```

### Event DTO Pattern

```java
public record ResourceCreatedEvent(
        UUID id,
        String name,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static ResourceCreatedEvent from(Resource resource, UUID createdBy) {
        return new ResourceCreatedEvent(
                resource.getId(),
                resource.getName(),
                createdBy,
                OffsetDateTime.now(ZoneOffset.UTC)
        );
    }
}
```

---

## API Gateway Patterns (NestJS)

### JWT Auth Guard

Location: `services/api-gateway/src/common/guards/jwt-auth.guard.ts`

```typescript
@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private jwtAuthService: JwtAuthService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    // Skip validation for public routes
    const isPublic = this.reflector.getAllAndOverride(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest();
    const token = this.jwtAuthService.extractTokenFromHeader(
      request.headers['authorization'],
    );
    if (!token) throw new UnauthorizedException();

    const payload = this.jwtAuthService.verifyToken(token);
    if (!payload) throw new UnauthorizedException();

    // Check account status
    if (payload.status === AccountStatus.DEACTIVATED) {
      throw new ForbiddenException(ErrorResponse.accountDeactivated());
    }

    // Attach user context to request
    request.user = this.jwtAuthService.buildUserContext(payload);
    return true;
  }
}
```

### RBAC Guard

Location: `services/api-gateway/src/common/guards/rbac.guard.ts`

```typescript
@Injectable()
export class RolesGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<UserRole[]>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );

    if (!requiredRoles?.length) return true;

    const request = context.switchToHttp().getRequest();
    const user = request.user as IUserContext;

    const hasRole = requiredRoles.some((role) =>
      this.roleMatches(user.role as UserRole, role),
    );

    if (!hasRole) throw new ForbiddenException();
    return true;
  }

  private roleMatches(userRole: UserRole, requiredRole: UserRole): boolean {
    const hierarchy = { ADMIN: 3, MANAGER: 2, USER: 1 };
    return hierarchy[userRole] >= hierarchy[requiredRole];
  }
}
```

### Roles Decorator

```typescript
export const ROLES_KEY = 'roles';
export const Roles = (...roles: UserRole[]) => SetMetadata(ROLES_KEY, roles);

// Usage
@Get('users')
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles(UserRole.ADMIN)
async getUsers() { }

// Public route
@Get('public-data')
@UseGuards(JwtAuthGuard)
@Public()
async getPublicData() { }
```

### Proxy Service Pattern

Location: `services/api-gateway/src/proxy/proxy.service.ts`

```typescript
@Injectable()
export class ProxyService {
  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {}

  async forward<T>(
    serviceName: ServiceName,
    path: string,
    method: string,
    request: Request,
  ): Promise<T> {
    const baseUrl = this.configService.get(`${serviceName}.url`);
    const url = `${baseUrl}${path}`;

    const response = await this.httpService.axiosRef({
      method,
      url,
      data: request.body,
      params: request.query,
      headers: this.buildHeaders(request),
      timeout: this.getTimeout(serviceName),
    });

    return response.data;
  }
}
```

---

## Frontend Patterns (Next.js + TypeScript)

### Zustand Store Pattern

Location: `frontend/web/store/auth-store.ts`

```typescript
interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({ user, isAuthenticated: !!user }),

      setTokens: (accessToken, refreshToken) => {
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', refreshToken);
        set({ accessToken, refreshToken, isAuthenticated: true });
      },

      logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
    }),
    { name: 'auth-storage' }
  )
);

// Convenience hooks
export const useUser = () => useAuthStore((s) => s.user);
export const useIsAdmin = () => useAuthStore((s) => s.user?.role === 'ADMIN');
export const useIsManager = () => ['ADMIN', 'MANAGER'].includes(useAuthStore((s) => s.user?.role));
```

### API Client Pattern

Location: `frontend/web/services/api-client.ts`

```typescript
// Singleton with automatic token refresh
const apiClient = axios.create({ baseURL: API_BASE_URL });

// Request interceptor: add auth token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 → refresh → retry
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !isRefreshing) {
      // Trigger refresh and retry all queued requests
    }
    return Promise.reject(error);
  }
);
```

### Centralized API Client

Location: `frontend/web/lib/api.ts` (1800+ lines)

```typescript
// Organized by domain
export const api = {
  auth: {
    login: (data: LoginRequest) => client.post('/auth/login', data),
    logout: (data: LogoutRequest) => client.post('/auth/logout', data),
    refresh: (data: RefreshTokenRequest) => client.post('/auth/refresh', data),
    me: () => client.get<User>('/auth/me'),
  },
  users: {
    list: (params: UserSearchParams) => client.get<PaginatedResponse<User>>('/users', { params }),
    getById: (id: string) => client.get<User>(`/users/${id}`),
    create: (data: CreateUserRequest) => client.post('/users', data),
    update: (id: string, data: UpdateUserRequest) => client.put(`/users/${id}`, data),
  },
  documents: {
    list: (params: DocumentSearchParams) => client.get('/documents', { params }),
    upload: (formData: FormData) => client.post('/documents', formData),
    download: (id: string) => client.get(`/documents/${id}/download`, { responseType: 'blob' }),
  },
  ai: {
    ask: (data: QuestionRequest) => client.post<QuestionResponse>('/ai/ask', data),
    askStream: (data: QuestionRequest) => client.post('/ai/ask/stream', data, { responseType: 'stream' }),
    conversations: () => client.get<Conversation[]>('/ai/conversations'),
  },
  // ... more domains
};
```

### Component with RBAC

```typescript
'use client';

import { useAuthStore } from '@/store/auth-store';

export function AdminPanel() {
  const user = useAuthStore((s) => s.user);

  if (user?.role !== 'ADMIN') {
    return <AccessDenied />;
  }

  return <AdminContent />;
}
```

### Streaming Response Pattern

```typescript
async function* streamAIResponse(question: string) {
  const response = await fetch('/api/ai/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversationId }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(Boolean);

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6));
        if (event.type === 'content') yield event.text;
        if (event.type === 'sources') yield { sources: event.sources };
      }
    }
  }
}
```

---

## RBAC Model

### Roles and Permissions

| Role | Capabilities |
|------|--------------|
| USER | AI Q&A, own profile, submit feedback |
| MANAGER | USER + analytics dashboard + report export + view unanswered |
| ADMIN | MANAGER + user management + document upload + metadata management |

### Role Hierarchy

```
ADMIN (3) > MANAGER (2) > USER (1)
```

Higher roles inherit all permissions from lower roles.

### Spring Security Pattern

```java
@PreAuthorize("hasRole('ADMIN')")           // Check specific role
@PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")  // Check multiple roles
@PreAuthorize("isAuthenticated()")          // Any authenticated user
```

### NestJS Guard Pattern

```java
@UseGuards(JwtAuthGuard, RolesGuard)
@Get('protected')
@Roles(UserRole.ADMIN)
async protectedEndpoint() {}
```

---

## Database Schema Ownership

| Schema | Owner | Tables |
|--------|-------|--------|
| `core` | auth-service | users, departments, refresh_tokens, login_history |
| `public` | user-service | user_profiles (duplicate) |
| `knowledge` | knowledge-service | documents, chunks, processing_jobs |
| `metadata` | metadata-service | categories, tags, document_metadata, access_rules |
| `conversation` | ai-qa-service | conversations, messages |
| `analytics` | feedback-service | feedbacks, usage_stats, audit_logs |

**Rule**: Never join across schemas. Use HTTP or events for cross-schema data access.

---

## Error Handling Patterns

### Spring Boot Global Exception Handler

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult()
            .getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                error -> error.getDefaultMessage()
            ));
        return ResponseEntity.badRequest().body(Map.of(
            "status", 400,
            "error", "Validation Error",
            "fieldErrors", errors
        ));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> handleResponseStatus(ResponseStatusException ex) {
        return ResponseEntity.status(ex.getStatusCode()).body(Map.of(
            "status", ex.getStatusCode().value(),
            "error", ex.getReason()
        ));
    }
}
```

### NestJS Exception Filter

```typescript
@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse();

    let status = 500;
    let message = 'Internal server error';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const errorResponse = exception.getResponse();
      message = typeof errorResponse === 'string' ? errorResponse :
        (errorResponse as any).message || message;
    }

    response.status(status).json({
      statusCode: status,
      message,
      timestamp: new Date().toISOString(),
    });
  }
}
```

---

## Common Commands

### Frontend

```bash
cd frontend/web
pnpm install        # Install dependencies
pnpm dev            # Start dev server (http://localhost:3000)
pnpm build          # Production build
pnpm lint           # Run linter
pnpm test           # Run tests
```

### API Gateway

```bash
cd services/api-gateway
pnpm install
pnpm run start:dev  # Start with hot reload (http://localhost:3001)
pnpm run build
pnpm run lint
```

### Spring Boot Services

```bash
cd services/<service-name>
./mvnw spring-boot:run           # Start service
./mvnw package                   # Build JAR
./mvnw test                      # Run tests
./mvnw -Dtest=ClassName test     # Run specific test class
./mvnw -Dtest=ClassName#method test  # Run specific test method
```

### Docker

```bash
docker compose up              # Start all services
docker compose up -d           # Start in background
docker compose down             # Stop all services
docker compose logs -f <service>  # View logs
```

---

## Key File References

### Controllers
- `services/auth-service/.../controller/AuthController.java` - Auth endpoints
- `services/user-service/.../controller/UserController.java` - User CRUD

### Services
- `services/auth-service/.../service/AuthService.java` - Auth logic
- `services/auth-service/.../service/RefreshTokenService.java` - Token management

### Repositories
- `services/auth-service/.../repository/UserRepository.java` - User queries

### Gateway Guards
- `services/api-gateway/src/common/guards/jwt-auth.guard.ts` - JWT validation
- `services/api-gateway/src/common/guards/rbac.guard.ts` - Role checking

### Frontend Stores
- `frontend/web/store/auth-store.ts` - Auth state
- `frontend/web/store/ui-store.ts` - UI state
- `frontend/web/store/preferences-store.ts` - User preferences

### Frontend API
- `frontend/web/lib/api.ts` - Centralized API client
- `frontend/web/services/api-client.ts` - Axios instance with interceptors

---

## Architecture Reference

For detailed architecture information, see:
- `contexts/architecture/system-overview.md` - System architecture
- `contexts/service-boundaries/responsibilities.md` - Service ownership
- `contexts/authorization/rbac-matrix.md` - RBAC details
- `contexts/database/schema.md` - Database schema
- `contexts/service-boundaries/events.md` - RabbitMQ events
