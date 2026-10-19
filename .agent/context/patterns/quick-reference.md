---
title: Code Patterns Quick Reference
description: Annotated code snippets and templates for common patterns in Poliwise
type: reference
version: 1.0
---

# Code Patterns Quick Reference

This document provides annotated code snippets for common patterns across the Poliwise codebase. Use these as templates when implementing similar functionality.

## Table of Contents

1. [Spring Boot Patterns](#spring-boot-patterns)
2. [NestJS Gateway Patterns](#nestjs-gateway-patterns)
3. [Frontend Patterns](#frontend-patterns)
4. [SQL Templates](#sql-templates)
5. [Event Schemas](#event-schemas)
6. [File Reference Index](#file-reference-index)

---

## Spring Boot Patterns

### Creating a New Controller

**File**: `services/<service>/src/main/java/com/poliwise/<service>/controller/ResourceController.java`

```java
@RestController
@RequestMapping("/api/v1/<resources>")
@RequiredArgsConstructor
@Slf4j
public class ResourceController {

    private final ResourceService resourceService;

    // POST - Create resource (ADMIN only)
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> create(@Valid @RequestBody CreateResourceRequest request) {
        ResourceResponse result = resourceService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }

    // GET - List resources with pagination (MANAGER+)
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<?> list(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) ResourceStatus status) {

        Page<ResourceResponse> result = resourceService.search(search, status, PageRequest.of(page, size));
        return ResponseEntity.ok(result);
    }

    // GET - Get single resource (authenticated)
    @GetMapping("/{id}")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<?> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(resourceService.findById(id));
    }

    // PUT - Update resource (ADMIN only)
    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateResourceRequest request) {
        return ResponseEntity.ok(resourceService.update(id, request));
    }

    // DELETE - Delete resource (ADMIN only)
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> delete(@PathVariable UUID id) {
        resourceService.delete(id);
        return ResponseEntity.ok(Map.of("message", "Deleted successfully"));
    }
}
```

### Creating a New Service

**File**: `services/<service>/src/main/java/com/poliwise/<service>/service/ResourceService.java`

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class ResourceService {

    private final ResourceRepository resourceRepository;
    private final EventPublisher eventPublisher;

    @Transactional
    public ResourceResponse create(CreateResourceRequest request) {
        // 1. Validate business rules
        if (resourceRepository.existsByNameIgnoreCase(request.name())) {
            throw conflict("Resource with this name already exists");
        }

        // 2. Build entity
        Resource entity = Resource.builder()
                .id(UUID.randomUUID())
                .name(request.name())
                .status(ResourceStatus.ACTIVE)
                .createdAt(OffsetDateTime.now(ZoneOffset.UTC))
                .updatedAt(OffsetDateTime.now(ZoneOffset.UTC))
                .build();

        // 3. Save
        Resource saved = resourceRepository.save(entity);

        // 4. Publish event
        eventPublisher.publishCreated(ResourceCreatedEvent.from(saved));

        // 5. Return response
        return toResponse(saved);
    }

    @Transactional(readOnly = true)
    public ResourceResponse findById(UUID id) {
        return resourceRepository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> notFound("Resource not found with id: " + id));
    }

    @Transactional(readOnly = true)
    public Page<ResourceResponse> search(String search, ResourceStatus status, Pageable pageable) {
        return resourceRepository.search(search, status, pageable)
                .map(this::toResponse);
    }

    @Transactional
    public ResourceResponse update(UUID id, UpdateResourceRequest request) {
        Resource entity = resourceRepository.findByIdForUpdate(id)
                .orElseThrow(() -> notFound("Resource not found"));

        if (!entity.getName().equals(request.name()) &&
            resourceRepository.existsByNameIgnoreCase(request.name())) {
            throw conflict("Name already in use");
        }

        entity.setName(request.name());
        entity.setStatus(request.status());
        entity.setUpdatedAt(OffsetDateTime.now(ZoneOffset.UTC));

        return toResponse(resourceRepository.save(entity));
    }

    @Transactional
    public void delete(UUID id) {
        Resource entity = resourceRepository.findByIdForUpdate(id)
                .orElseThrow(() -> notFound("Resource not found"));

        entity.setStatus(ResourceStatus.DELETED);
        entity.setUpdatedAt(OffsetDateTime.now(ZoneOffset.UTC));
        resourceRepository.save(entity);

        eventPublisher.publishDeleted(ResourceDeletedEvent.from(entity));
    }

    // Helper methods
    private ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }

    private ResponseStatusException notFound(String message) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, message);
    }

    private ResourceResponse toResponse(Resource entity) {
        return new ResourceResponse(
                entity.getId(),
                entity.getName(),
                entity.getStatus(),
                entity.getCreatedAt()
        );
    }
}
```

### Creating a New Repository

**File**: `services/<service>/src/main/java/com/poliwise/<service>/repository/ResourceRepository.java`

```java
@Repository
public interface ResourceRepository extends JpaRepository<Resource, UUID>,
        JpaSpecificationExecutor<Resource> {

    // Find by unique field (case-insensitive)
    Optional<Resource> findByNameIgnoreCase(String name);

    // Check existence
    boolean existsByNameIgnoreCase(String name);

    // Pessimistic locking for updates
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT r FROM Resource r WHERE r.id = :id")
    Optional<Resource> findByIdForUpdate(@Param("id") UUID id);

    // Custom query with multiple parameters
    @Query("""
            SELECT r FROM Resource r
            WHERE (:search IS NULL OR :search = ''
               OR LOWER(r.name) LIKE LOWER(CONCAT('%', :search, '%')))
              AND (:status IS NULL OR r.status = :status)
            ORDER BY r.createdAt DESC
            """)
    Page<Resource> search(
            @Param("search") String search,
            @Param("status") ResourceStatus status,
            Pageable pageable);

    // Bulk update
    @Transactional
    @Modifying
    @Query("UPDATE Resource r SET r.status = :status WHERE r.id IN :ids")
    int bulkUpdateStatus(@Param("ids") List<UUID> ids, @Param("status") ResourceStatus status);

    // Count by status
    long countByStatus(ResourceStatus status);

    // Delete (soft delete pattern)
    @Transactional
    @Modifying
    @Query("UPDATE Resource r SET r.status = 'DELETED', r.updatedAt = :now WHERE r.id = :id")
    int softDelete(@Param("id") UUID id, @Param("now") OffsetDateTime now);
}
```

### Creating a New Entity

**File**: `services/<service>/src/main/java/com/poliwise/<service>/entity/Resource.java`

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

    @Column(nullable = false, length = 255)
    private String name;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false)
    private ResourceStatus status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    @ToString.Exclude
    private Department department;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    @Column(name = "deleted_at")
    private OffsetDateTime deletedAt;

    // JSON column for metadata
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> metadata;

    // Lifecycle callbacks
    @PrePersist
    void onCreate() {
        if (id == null) id = UUID.randomUUID();
        if (createdAt == null) createdAt = OffsetDateTime.now(ZoneOffset.UTC);
        if (updatedAt == null) updatedAt = OffsetDateTime.now(ZoneOffset.UTC);
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = OffsetDateTime.now(ZoneOffset.UTC);
    }

    // Business methods
    public boolean isActive() {
        return status == ResourceStatus.ACTIVE;
    }

    public void softDelete() {
        this.status = ResourceStatus.DELETED;
        this.deletedAt = OffsetDateTime.now(ZoneOffset.UTC);
    }
}
```

### Creating Request/Response DTOs

**File**: `services/<service>/src/main/java/com/poliwise/<service>/dto/request/CreateResourceRequest.java`

```java
public record CreateResourceRequest(
        @NotBlank(message = "Name is required")
        @Size(min = 1, max = 255, message = "Name must be between 1 and 255 characters")
        String name,

        @NotNull(message = "Status is required")
        ResourceStatus status,

        UUID departmentId,

        @Size(max = 1000, message = "Description cannot exceed 1000 characters")
        String description
) {}
```

**File**: `services/<service>/src/main/java/com/poliwise/<service>/dto/response/ResourceResponse.java`

```java
public record ResourceResponse(
        UUID id,
        String name,
        ResourceStatus status,
        String description,
        DepartmentInfo department,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    // Nested record for related data
    public record DepartmentInfo(
            UUID id,
            String name,
            String code
    ) {}

    // Factory method
    public static ResourceResponse from(Resource entity) {
        return new ResourceResponse(
                entity.getId(),
                entity.getName(),
                entity.getStatus(),
                entity.getDescription(),
                entity.getDepartment() != null
                    ? new DepartmentInfo(
                            entity.getDepartment().getId(),
                            entity.getDepartment().getName(),
                            entity.getDepartment().getCode())
                    : null,
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}
```

### Creating an Event Publisher

**File**: `services/<service>/src/main/java/com/poliwise/<service>/event/ResourceEventPublisher.java`

```java
@Component
@RequiredArgsConstructor
public class ResourceEventPublisher {

    private final RabbitTemplate rabbitTemplate;

    private static final String EXCHANGE = "poliwise.events";

    public void publishCreated(ResourceCreatedEvent event) {
        rabbitTemplate.convertAndSend(EXCHANGE, "resource.created", event);
        log.info("Published ResourceCreatedEvent: id={}", event.id());
    }

    public void publishUpdated(ResourceUpdatedEvent event) {
        rabbitTemplate.convertAndSend(EXCHANGE, "resource.updated", event);
        log.info("Published ResourceUpdatedEvent: id={}", event.id());
    }

    public void publishDeleted(ResourceDeletedEvent event) {
        rabbitTemplate.convertAndSend(EXCHANGE, "resource.deleted", event);
        log.info("Published ResourceDeletedEvent: id={}", event.id());
    }

    public void publishStatusChanged(ResourceStatusChangedEvent event) {
        rabbitTemplate.convertAndSend(EXCHANGE, "resource.status.changed", event);
        log.info("Published ResourceStatusChangedEvent: id={}, from={} to={}",
                event.id(), event.previousStatus(), event.newStatus());
    }
}
```

### Creating an Event Consumer

**File**: `services/<service>/src/main/java/com/poliwise/<service>/event/ResourceEventConsumer.java`

```java
@Component
@RequiredArgsConstructor
public class ResourceEventConsumer {

    private final DependentService dependentService;
    private final CacheService cacheService;

    private static final String QUEUE = "poliwise.resource.created";

    @RabbitListener(queues = QUEUE)
    public void handleCreated(Map<String, Object> message) {
        try {
            UUID id = UUID.fromString(String.valueOf(message.get("id")));
            String name = String.valueOf(message.get("name"));
            OffsetDateTime createdAt = parseTimestamp(message.get("createdAt"));

            dependentService.onResourceCreated(id, name);
            log.info("Handled resource created: id={}", id);

        } catch (Exception e) {
            log.error("Failed to handle resource created event: {}", message, e);
            throw e; // Re-throw for DLQ
        }
    }

    @RabbitListener(queues = "poliwise.resource.deleted")
    public void handleDeleted(Map<String, Object> message) {
        try {
            UUID id = UUID.fromString(String.valueOf(message.get("id")));
            cacheService.invalidate(id);
            log.info("Handled resource deleted: id={}", id);
        } catch (Exception e) {
            log.error("Failed to handle resource deleted event", e);
            throw e;
        }
    }

    private OffsetDateTime parseTimestamp(Object value) {
        if (value instanceof String s) {
            return OffsetDateTime.parse(s);
        }
        return OffsetDateTime.now(ZoneOffset.UTC);
    }
}
```

### Creating an Event DTO

**File**: `services/<service>/src/main/java/com/poliwise/<service>/dto/event/ResourceCreatedEvent.java`

```java
public record ResourceCreatedEvent(
        UUID id,
        String name,
        String description,
        UUID departmentId,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static ResourceCreatedEvent from(Resource resource, UUID createdBy) {
        return new ResourceCreatedEvent(
                resource.getId(),
                resource.getName(),
                resource.getDescription(),
                resource.getDepartment() != null ? resource.getDepartment().getId() : null,
                createdBy,
                OffsetDateTime.now(ZoneOffset.UTC)
        );
    }
}
```

---

## NestJS Gateway Patterns

### Adding a New Route

**File**: `services/api-gateway/src/proxy/proxy.controller.ts`

```typescript
@Controller('api/v1')
export class ProxyController {
  // ... existing routes ...

  // Add new route for resource
  @Post('resources')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  @HttpCode(HttpStatus.CREATED)
  async createResource(
    @Body() body: CreateResourceDto,
    @Req() req: Request,
  ): Promise<ApiResponse<ResourceResponse>> {
    const result = await this.proxyService.forward<ResourceResponse>(
      ServiceName.RESOURCE,
      '/api/v1/resources',
      'POST',
      req,
      body,
    );
    return ApiResponse.success(result);
  }

  @Get('resources')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN, UserRole.MANAGER)
  async listResources(
    @Query() query: ListResourcesQueryDto,
    @Req() req: Request,
  ): Promise<ApiResponse<PaginatedResponse<ResourceResponse>>> {
    const result = await this.proxyService.forward<PaginatedResponse<ResourceResponse>>(
      ServiceName.RESOURCE,
      '/api/v1/resources',
      'GET',
      req,
    );
    return ApiResponse.success(result);
  }

  @Get('resources/:id')
  @UseGuards(JwtAuthGuard)
  async getResource(
    @Param('id') id: string,
    @Req() req: Request,
  ): Promise<ApiResponse<ResourceResponse>> {
    const result = await this.proxyService.forward<ResourceResponse>(
      ServiceName.RESOURCE,
      `/api/v1/resources/${id}`,
      'GET',
      req,
    );
    return ApiResponse.success(result);
  }

  // Public route example
  @Get('public/resources')
  @UseGuards(JwtAuthGuard)
  @Public()
  async getPublicResources(@Req() req: Request) {
    return this.proxyService.forward(
      ServiceName.RESOURCE,
      '/api/v1/resources/public',
      'GET',
      req,
    );
  }
}
```

### Creating a Guard

**File**: `services/api-gateway/src/common/guards/custom-guard.ts`

```typescript
@Injectable()
export class CustomGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    private customService: CustomService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const user = request.user as IUserContext;

    // Check custom condition
    const hasAccess = await this.customService.checkAccess(user);
    if (!hasAccess) {
      throw new ForbiddenException('Access denied');
    }

    return true;
  }
}
```

### Creating an Interceptor

**File**: `services/api-gateway/src/common/interceptors/logging.interceptor.ts`

```typescript
@Injectable()
export class CustomLoggingInterceptor implements NestInterceptor {
  constructor(private logger: Logger) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const request = context.switchToHttp().getRequest();
    const { method, url } = request;
    const startTime = Date.now();

    this.logger.log(`Request: ${method} ${url}`);

    return next.handle().pipe(
      tap(() => {
        const response = context.switchToHttp().getResponse();
        const duration = Date.now() - startTime;
        this.logger.log(`Response: ${method} ${url} ${response.statusCode} - ${duration}ms`);
      }),
      catchError((error) => {
        const duration = Date.now() - startTime;
        this.logger.error(`Error: ${method} ${url} - ${duration}ms`, error.stack);
        throw error;
      }),
    );
  }
}
```

---

## Frontend Patterns

### Creating a New API Method

**File**: `frontend/web/lib/api.ts`

```typescript
// Add to existing domain or create new domain
export const api = {
  // ... existing domains ...

  // New domain
  resources: {
    list: (params?: ResourceSearchParams) =>
      client.get<PaginatedResponse<Resource>>('/resources', { params }),

    getById: (id: string) =>
      client.get<Resource>(`/resources/${id}`),

    create: (data: CreateResourceRequest) =>
      client.post<Resource>('/resources', data),

    update: (id: string, data: UpdateResourceRequest) =>
      client.put<Resource>(`/resources/${id}`, data),

    delete: (id: string) =>
      client.delete(`/resources/${id}`),
  },
};
```

### Creating a Component with Loading State

**File**: `frontend/web/components/resources/ResourceList.tsx`

```typescript
'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { EmptyState } from '@/components/ui/EmptyState';
import type { Resource } from '@/types';

interface ResourceListProps {
  onSelect?: (resource: Resource) => void;
}

export function ResourceList({ onSelect }: ResourceListProps) {
  const [resources, setResources] = useState<Resource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadResources();
  }, []);

  const loadResources = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.resources.list();
      setResources(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resources');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <Spinner size="lg" />;
  }

  if (error) {
    return <EmptyState title="Error" description={error} action={<Button onClick={loadResources}>Retry</Button>} />;
  }

  if (resources.length === 0) {
    return <EmptyState title="No resources" description="No resources found" />;
  }

  return (
    <div className={styles.list}>
      {resources.map((resource) => (
        <ResourceCard
          key={resource.id}
          resource={resource}
          onClick={() => onSelect?.(resource)}
        />
      ))}
    </div>
  );
}
```

### Creating a Form Component

**File**: `frontend/web/components/resources/ResourceForm.tsx`

```typescript
'use client';

import { useForm } from 'react-hook-form';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

interface ResourceFormData {
  name: string;
  status: string;
  description?: string;
}

interface ResourceFormProps {
  initialData?: Partial<ResourceFormData>;
  onSuccess: () => void;
  onCancel: () => void;
}

export function ResourceForm({ initialData, onSuccess, onCancel }: ResourceFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResourceFormData>({
    defaultValues: initialData,
  });

  const onSubmit = async (data: ResourceFormData) => {
    try {
      if (initialData) {
        await api.resources.update(initialData.id!, data);
      } else {
        await api.resources.create(data);
      }
      onSuccess();
    } catch (error) {
      console.error('Failed to save resource:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
      <Input
        label="Name"
        {...register('name', { required: 'Name is required' })}
        error={errors.name?.message}
      />

      <Select
        label="Status"
        options={[
          { value: 'ACTIVE', label: 'Active' },
          { value: 'INACTIVE', label: 'Inactive' },
        ]}
        {...register('status', { required: 'Status is required' })}
        error={errors.status?.message}
      />

      <div className={styles.actions}>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          {initialData ? 'Update' : 'Create'}
        </Button>
      </div>
    </form>
  );
}
```

### Creating a Modal

**File**: `frontend/web/components/ui/ConfirmDialog.tsx`

```typescript
'use client';

import { useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import styles from './ConfirmDialog.module.css';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'primary';
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'primary',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    },
    [onCancel]
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleEscape]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p>{message}</p>
        <div className={styles.actions}>
          <Button variant="ghost" onClick={onCancel} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'destructive' : 'primary'}
            onClick={onConfirm}
            loading={isLoading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

---

## SQL Templates

### User Queries

```sql
-- Find active users by department
SELECT u.*, d.name as department_name
FROM core.users u
LEFT JOIN core.departments d ON u.department_id = d.id
WHERE u.status = 'ACTIVE'
  AND (:departmentId IS NULL OR u.department_id = :departmentId)
ORDER BY u.created_at DESC
LIMIT :limit OFFSET :offset;

-- Search users by keyword
SELECT u.*
FROM core.users u
WHERE (:keyword IS NULL OR :keyword = ''
   OR LOWER(u.username) LIKE LOWER(CONCAT('%', :keyword, '%'))
   OR LOWER(u.email) LIKE LOWER(CONCAT('%', :keyword, '%')))
  AND (:role IS NULL OR u.role = :role::core.user_role)
  AND (:status IS NULL OR u.status = :status::core.account_status)
ORDER BY u.created_at DESC;
```

### Document Queries

```sql
-- Find documents with access for user
SELECT d.*
FROM knowledge.documents d
JOIN metadata.document_access_rules ar ON d.id = ar.document_id
WHERE d.status = 'PUBLISHED'
  AND (
    ar.allowed_roles @> ARRAY[:userRole]::core.user_role[]
    OR ar.allowed_departments @> ARRAY[:departmentId]::uuid[]
    OR ar.allowed_users @> ARRAY[:userId]::uuid[]
  )
ORDER BY d.created_at DESC
LIMIT :limit;

-- Search chunks with ACL filter
SELECT c.id, c.content, c.metadata, d.title
FROM knowledge.chunks c
JOIN knowledge.documents d ON c.document_id = d.id
WHERE (
    c.allowed_roles @> ARRAY[:userRole]::core.user_role[]
    OR c.allowed_departments @> ARRAY[:departmentId]::uuid[]
    OR c.allowed_users @> ARRAY[:userId]::uuid[]
  )
  AND c.content_vector @@ to_tsquery('english', :searchQuery)
ORDER BY ts_rank(c.content_vector, to_tsquery('english', :searchQuery)) DESC
LIMIT :limit;
```

### Analytics Queries

```sql
-- Get daily usage stats
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_queries,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(response_time_ms) as avg_response_time
FROM analytics.usage_stats
WHERE created_at >= :startDate
  AND created_at < :endDate
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Get top unanswered questions
SELECT
    q.id, q.question, q.search_query, q.count, q.last_asked_at,
    u.username as asked_by
FROM analytics.unanswered_questions q
LEFT JOIN core.users u ON q.asked_by_user_id = u.id
WHERE q.status = 'UNANSWERED'
ORDER BY q.count DESC, q.priority DESC
LIMIT :limit;
```

---

## Event Schemas

### User Events

```typescript
// user.registered
interface UserRegisteredEvent {
  userId: string;           // UUID
  username: string;
  email: string;
  role: 'USER' | 'MANAGER' | 'ADMIN';
  registeredBy: string | null;  // UUID of admin who registered, null if self-registered
  createdAt: string;        // ISO timestamp
}

// user.status.changed
interface UserStatusChangedEvent {
  userId: string;
  previousStatus: 'ACTIVE' | 'DEACTIVATED' | 'REVOKED';
  newStatus: 'ACTIVE' | 'DEACTIVATED' | 'REVOKED';
  changedBy: string;
  changedAt: string;
}

// user.login.success
interface LoginSuccessEvent {
  userId: string;
  username: string;
  sessionId: string;
  ipAddress: string;
  userAgent: string;
  timestamp: string;
}

// user.login.failed
interface LoginFailedEvent {
  username: string;
  reason: 'INVALID_CREDENTIALS' | 'DEACTIVATED' | 'LOCKED' | 'REVOKED';
  ipAddress: string;
  timestamp: string;
}
```

### Document Events

```typescript
// document.uploaded
interface DocumentUploadedEvent {
  documentId: string;
  documentVersionId: string;
  title: string;
  fileType: string;
  fileSize: number;
  departmentId: string;
  uploadedBy: string;
  uploadedAt: string;
}

// document.deleted
interface DocumentDeletedEvent {
  documentId: string;
  reason: 'USER_REQUEST' | 'ADMIN_REQUEST' | 'RETENTION_POLICY';
  deletedBy: string;
  deletedAt: string;
}

// document.permissions.changed
interface DocumentPermissionsChangedEvent {
  documentId: string;
  previousRules: AccessRule[];
  newRules: AccessRule[];
  changedBy: string;
  changedAt: string;
}

// ingestion.requested
interface IngestionRequestedEvent {
  documentId: string;
  documentVersionId: string;
  fileKey: string;
  bucketName: string;
  jobId: string;
  metadata: {
    title: string;
    departmentId: string;
    categories: string[];
    tags: string[];
  };
}
```

### AI Events

```typescript
// unanswered.question
interface UnansweredQuestionEvent {
  userId: string;
  messageId: string;
  conversationId: string;
  question: string;
  searchQuery: string;
  topSimilarityScore: number;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  createdAt: string;
}
```

---

## File Reference Index

### Spring Boot - Auth Service

| Pattern | File Path |
|---------|-----------|
| Controller | `services/auth-service/src/main/java/com/poliwise/auth/controller/AuthController.java` |
| Service | `services/auth-service/src/main/java/com/poliwise/auth/service/AuthService.java` |
| Repository | `services/auth-service/src/main/java/com/poliwise/auth/repository/UserRepository.java` |
| Entity | `services/auth-service/src/main/java/com/poliwise/auth/entity/User.java` |
| Event Publisher | `services/auth-service/src/main/java/com/poliwise/auth/event/AuthEventPublisher.java` |
| Security Config | `services/auth-service/src/main/java/com/poliwise/auth/config/SecurityConfig.java` |

### NestJS - API Gateway

| Pattern | File Path |
|---------|-----------|
| JWT Guard | `services/api-gateway/src/common/guards/jwt-auth.guard.ts` |
| RBAC Guard | `services/api-gateway/src/common/guards/rbac.guard.ts` |
| Roles Decorator | `services/api-gateway/src/common/decorators/roles.decorator.ts` |
| Public Decorator | `services/api-gateway/src/common/decorators/public.decorator.ts` |
| Proxy Controller | `services/api-gateway/src/proxy/proxy.controller.ts` |
| Proxy Service | `services/api-gateway/src/proxy/proxy.service.ts` |
| Exception Filter | `services/api-gateway/src/common/filters/http-exception.filter.ts` |
| Rate Limiter | `services/api-gateway/src/common/interceptors/rate-limit.interceptor.ts` |

### Frontend - Next.js

| Pattern | File Path |
|---------|-----------|
| Auth Store | `frontend/web/store/auth-store.ts` |
| UI Store | `frontend/web/store/ui-store.ts` |
| API Client | `frontend/web/services/api-client.ts` |
| API Methods | `frontend/web/lib/api.ts` |
| Auth Types | `frontend/web/types/auth.ts` |
| Document Types | `frontend/web/types/document.ts` |
| AI Types | `frontend/web/types/ai.ts` |

### Database

| Schema | Tables |
|--------|--------|
| `core` | users, departments, refresh_tokens, login_history |
| `knowledge` | documents, document_versions, chunks, processing_jobs |
| `metadata` | categories, tags, document_metadata, document_tags, document_access_rules |
| `conversation` | conversations, messages, unanswered_questions |
| `analytics` | feedbacks, usage_stats, audit_logs, daily_aggregates |

---

## Related Documentation

- `.agent/README.md` - Consolidated agent knowledge base
- `.agent/context/architecture/frontend.md` - Frontend architecture
- `.agent/context/architecture/system-overview.md` - System architecture
- `.agent/context/service-boundaries/responsibilities.md` - Service ownership
- `.agent/context/database/schema.md` - Database schema details

|---

## Related Documentation

- .agent/README.md - Consolidated agent knowledge base
- .agent/context/architecture/frontend.md - Frontend architecture
- .agent/context/architecture/system-overview.md - System architecture
- .agent/context/service-boundaries/responsibilities.md - Service ownership
- .agent/context/database/schema.md - Database schema details

---

## Async Ingestion with Sync Confirmation Polling

When the frontend needs to confirm a document upload with real-time feedback, use this pattern:

### Problem
The ingestion pipeline runs asynchronously via RabbitMQ. The frontend needs to know:
1. Is the document a duplicate? (HTTP 409)
2. Is it a near-duplicate requiring user action? (HTTP 200 with NEAR_DUPLICATE status)
3. Did ingestion succeed? (HTTP 200 with READY status)

### Solution: 2-Phase Approach

#### Phase 1: Pre-confirm duplicate check (optional)
Frontend calls GET /check-duplicate after upload to show early warning.

#### Phase 2: Sync confirm with polling
Frontend calls POST /confirm which triggers async ingestion and polls for result.

### Duplicate Decision Thresholds

| Threshold | Action | HTTP Response |
|-----------|--------|----------------|
| similarity >= 0.98 | BLOCK (duplicate) | HTTP 409 or status=DUPLICATE |
|  .85 <= similarity < 0.98 | SUGGEST_VERSION | status=NEAR_DUPLICATE |
| similarity < 0.85 | INGEST | status=READY |

### Error Handling

- **Polling timeout (60s)**: Throw RuntimeException, frontend shows generic error
- **Ingestion failure**: Throw RuntimeException, frontend shows error
- **Service unavailable**: Fallback to local checks, log warnings

