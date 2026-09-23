# Database Ownership Boundaries

## Ownership Model

Each microservice owns its schema. Cross-schema references are managed through:
- Foreign keys (where appropriate)
- Event-driven synchronization
- UUID references without hard FK constraints

## Schema Ownership

| Schema | Owner Service | Port |
|--------|--------------|------|
| `poliwise_core` (public) | auth-service | 8081 |
| `poliwise_user` | user-service | 8082 |
| `poliwise_knowledge` | knowledge-service | 8083 |
| `poliwise_metadata` | metadata-service | 8084 |
| `poliwise_analytics` | feedback-service | 8085 |

## Schema Details

### poliwise_core

Tables owned by `auth-service`:
- `users` - User accounts
- `departments` - Department hierarchy
- `user_profiles` - Detailed user info
- `refresh_tokens` - JWT refresh tokens
- `login_history` - Login audit trail

### poliwise_knowledge

Tables owned by `knowledge-service`:
- `documents` - Core document records
- `document_versions` - Version history
- `processing_jobs` - ETL job tracking
- `chunks` - Vector embeddings
- `document_audit_logs` - Document audit trail

### poliwise_metadata

Tables owned by `metadata-service`:
- `categories` - Document categories
- `tags` - Document tags
- `document_metadata` - Document metadata
- `document_tags` - Tag associations
- `document_access_rules` - ACL rules
- `metadata_audit_logs` - Metadata audit trail

### poliwise_analytics

Tables owned by `feedback-service`:
- `conversations` - AI chat conversations
- `messages` - Chat messages
- `feedback` - Message feedback
- `analytics_events` - Usage analytics
- `audit_logs` - System audit logs
- `unanswered_questions` - Questions needing answers

## Cross-Service References

### Document References

```
documents.document_id ────────────► document_metadata.document_id
                                     │
                                     └──► categories.id (FK)
                                     └──► document_tags.tag_id
                                              └──► tags.id (FK)
                                     └──► document_access_rules.document_metadata_id
```

### User References

```
documents.uploaded_by ────────────► users.id (no FK)
users.department_id ─────────────► departments.id (FK)
document_metadata.created_by ─────► users.id (no FK)
```

## Integration Patterns

### Event-Driven Sync

Services communicate via RabbitMQ events:

| Event | Publisher | Consumer |
|-------|-----------|----------|
| `document.uploaded` | knowledge-service | metadata-service |
| `document.deleted` | knowledge-service | metadata-service |
| `user.created` | auth-service | user-service |
| `user.status.changed` | auth-service | user-service |

### API Composition

Frontend accesses all services through API Gateway (NestJS) which:
- Validates JWT tokens
- Enforces RBAC
- Proxies to appropriate microservice
- Normalizes responses

## Migration Guidelines

When adding new tables or modifying schemas:

1. **Identify owner service** - Which service owns this data?
2. **Update init scripts** - Add SQL to `infrastructure/init-db/`
3. **Update contexts/** - Document the change
4. **Update services** - Add entities, repositories, services
5. **Update API Gateway** - Add routes and guards if needed
6. **Update frontend** - Add types and services

Do NOT add foreign keys across schema boundaries without explicit architecture approval.
