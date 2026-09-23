---
title: Service Ownership Matrix
description: Complete feature ownership mapping for Poliwise microservices
type: service-boundaries
version: 1.0
---

# Service Ownership Matrix

## Purpose

This document provides a **quick-reference matrix** showing which service owns which feature, database table, and API endpoint. Use this as a lookup table when implementing or debugging features.

## When to Use

- Quick determination of which service to modify for a feature
- Understanding cross-service dependencies
- Debugging ownership questions
- Onboarding new team members

---

## Feature Ownership Matrix

| Feature Category | Feature | Primary Owner | Secondary Owner | Database Tables | API Endpoints |
|-----------------|---------|--------------|----------------|----------------|---------------|
| **Authentication** | User login/logout | `auth-service` | - | `core.users`, `core.refresh_tokens`, `core.login_history` | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/refresh` |
| | User registration | `auth-service` | - | `core.users` | `POST /api/v1/auth/register` |
| | Token validation | `auth-service` | `api-gateway` | `core.refresh_tokens` | Internal only |
| **User Management** | User profile CRUD | `user-service` | - | `core.user_profiles`, `core.departments` | `GET/PUT /api/v1/users/me`, `GET /api/v1/users/{id}` |
| | Department management | `user-service` | - | `core.departments` | `GET /api/v1/departments` |
| | Account status changes | `user-service` | `auth-service` (via events) | `core.users` | `PATCH /api/v1/users/{id}/status` |
| **Document Management** | File upload | `knowledge-service` | `ingestion-service` (processing) | `knowledge.documents`, `knowledge.document_versions` | `POST /api/v1/documents/upload` |
| | Document metadata | `metadata-service` | - | `metadata.document_metadata` | `GET/PUT /api/v1/metadata/documents/{id}` |
| | Document search/list | `knowledge-service` | `metadata-service` (access control) | `knowledge.documents` | `GET /api/v1/documents` |
| | Document deletion | `knowledge-service` | `ingestion-service` (cleanup) | `knowledge.documents` | `DELETE /api/v1/documents/{id}` |
| **Document Processing** | Text extraction | `ingestion-service` | - | `knowledge.processing_jobs` | Internal only |
| | Chunking | `ingestion-service` | - | `knowledge.chunks` | Internal only |
| | Embedding generation | `ingestion-service` | - | `knowledge.chunks` | Internal only |
| | Vector indexing | `ingestion-service` | - | `knowledge.chunks` | Internal only |
| **AI Q&A** | Question processing | `ai-qa-service` | - | `conversation.messages` | `POST /api/v1/ai/chat` |
| | Vector search | `ai-qa-service` | - | `knowledge.chunks` | Internal only |
| | LLM response generation | `ai-qa-service` | - | `conversation.messages` | Internal only |
| | Conversation management | `ai-qa-service` | - | `conversation.conversations` | `GET/DELETE /api/v1/ai/conversations` |
| **Metadata & Access** | Categories/tags | `metadata-service` | - | `metadata.categories`, `metadata.tags`, `metadata.document_tags` | `GET /api/v1/metadata/categories`, `GET /api/v1/metadata/tags` |
| | Access rules | `metadata-service` | - | `metadata.document_access_rules` | `POST /api/v1/metadata/access-rules` |
| | Document access check | `metadata-service` | `ai-qa-service` (cached) | `metadata.document_access_rules` | Internal only |
| **Analytics** | User feedback | `feedback-service` | - | `analytics.feedbacks` | `POST /api/v1/feedback` |
| | Usage statistics | `feedback-service` | - | `analytics.usage_stats` | Internal only |
| | Unanswered questions | `feedback-service` | `ai-qa-service` (publish) | `analytics.unanswered_questions` | `GET /api/v1/ai/unanswered` |
| | Audit logs | `feedback-service` | - | `analytics.audit_logs` | Internal only |
| | Reports/dashboards | `feedback-service` | - | `analytics.daily_aggregates`, `analytics.hourly_aggregates` | `GET /api/v1/analytics/dashboard` |
| **Infrastructure** | API routing | `api-gateway` | - | None | All routes |
| | Rate limiting | `api-gateway` | - | None | All routes |
| | JWT validation | `api-gateway` | `auth-service` (internal) | None | All protected routes |
| | Circuit breaking | `api-gateway` | - | None | All routes |
| | Request tracing | `api-gateway` | - | None | All routes |

---

## Database Table Ownership

### Schema: `core` (auth-service)
- `core.users` - User accounts, authentication
- `core.refresh_tokens` - JWT refresh tokens
- `core.login_history` - Login audit trail

### Schema: `public` (user-service)
- `core.user_profiles` - User profile details
- `core.departments` - Department hierarchy

### Schema: `metadata` (metadata-service)
- `metadata.categories` - Document categories
- `metadata.tags` - Document tags
- `metadata.document_metadata` - Document metadata
- `metadata.document_tags` - Document-tag relationships
- `metadata.document_access_rules` - Document access control rules

### Schema: `knowledge` (knowledge-service + ingestion-service)
**knowledge-service (read-only)**:
- `knowledge.documents` - Document file tracking
- `knowledge.document_versions` - Document version history
- `knowledge.processing_jobs` - Processing job status

**ingestion-service (write-only)**:
- `knowledge.chunks` - Document chunks with embeddings
- `knowledge.embedding_cache` - Embedding cache

### Schema: `conversation` (ai-qa-service)
- `conversation.conversations` - Chat sessions
- `conversation.messages` - Chat messages

### Schema: `analytics` (feedback-service)
- `analytics.feedbacks` - User feedback (like/dislike)
- `analytics.usage_stats` - API usage statistics
- `analytics.audit_logs` - System audit trail
- `analytics.daily_aggregates` - Daily aggregated stats
- `analytics.hourly_aggregates` - Hourly aggregated stats
- `analytics.department_daily_stats` - Department-level stats
- `analytics.popular_questions` - Frequently asked questions
- `analytics.document_popularity` - Document citation stats
- `analytics.report_exports` - Report export tracking
- `analytics.unanswered_questions` - Questions AI couldn't answer

---

## API Endpoint Ownership

### Public Endpoints (No Auth)
| Endpoint | Method | Service | Description |
|----------|--------|---------|-------------|
| `/health` | GET | All services | Health check |
| `/health/live` | GET | All services | Liveness probe |
| `/health/ready` | GET | All services | Readiness probe |
| `/api/v1/auth/login` | POST | auth-service | User login |
| `/api/v1/auth/register` | POST | auth-service | User registration |

### Protected Endpoints (Require JWT)
| Endpoint | Method | Service | Required Role | Description |
|----------|--------|---------|--------------|-------------|
| `/api/v1/auth/logout` | POST | auth-service | USER+ | Logout user |
| `/api/v1/auth/refresh` | POST | auth-service | USER+ | Refresh token |
| `/api/v1/auth/sessions` | GET | auth-service | USER+ | List active sessions |
| `/api/v1/users/me` | GET | user-service | USER+ | Get current user profile |
| `/api/v1/users/me` | PUT | user-service | USER+ | Update own profile |
| `/api/v1/users/{id}` | GET | user-service | MANAGER+ | Get user by ID |
| `/api/v1/users` | GET | user-service | MANAGER+ | List users with filters |
| `/api/v1/users/{id}` | PATCH | user-service | ADMIN | Update user status |
| `/api/v1/users/{id}` | DELETE | user-service | ADMIN | Delete user |
| `/api/v1/departments` | GET | user-service | USER+ | List departments |
| `/api/v1/documents` | GET | knowledge-service | USER+ | List documents |
| `/api/v1/documents/{id}` | GET | knowledge-service | USER+ | Get document details |
| `/api/v1/documents/upload` | POST | knowledge-service | ADMIN | Upload document |
| `/api/v1/documents/{id}` | DELETE | knowledge-service | ADMIN | Delete document |
| `/api/v1/metadata/categories` | GET | metadata-service | USER+ | List categories |
| `/api/v1/metadata/tags` | GET | metadata-service | USER+ | List tags |
| `/api/v1/metadata/documents/{id}` | GET | metadata-service | USER+ | Get document metadata |
| `/api/v1/metadata/documents/{id}` | PUT | metadata-service | ADMIN | Update document metadata |
| `/api/v1/metadata/access-rules` | POST | metadata-service | ADMIN | Create access rule |
| `/api/v1/metadata/documents/{id}/access` | GET | metadata-service | USER+ | Check document access |
| `/api/v1/ai/chat` | POST | ai-qa-service | USER+ | Ask question (non-streaming) |
| `/api/v1/ai/chat/stream` | POST | ai-qa-service | USER+ | Ask question (streaming) |
| `/api/v1/ai/conversations` | GET | ai-qa-service | USER+ | List conversations |
| `/api/v1/ai/conversations/{id}` | GET | ai-qa-service | USER+ | Get conversation |
| `/api/v1/ai/conversations/{id}` | DELETE | ai-qa-service | USER+ | Delete conversation |
| `/api/v1/ai/unanswered` | GET | ai-qa-service | MANAGER+ | List unanswered questions |
| `/api/v1/ai/unanswered/{id}/resolve` | PUT | ai-qa-service | MANAGER+ | Mark question as resolved |
| `/api/v1/feedback` | POST | feedback-service | USER+ | Submit feedback |
| `/api/v1/analytics/dashboard` | GET | feedback-service | MANAGER+ | Get analytics dashboard |
| `/api/v1/analytics/reports` | POST | feedback-service | MANAGER+ | Generate report |
| `/api/v1/analytics/reports/{id}/download` | GET | feedback-service | MANAGER+ | Download report |

### Internal Endpoints (Service-to-Service)
| Endpoint | Method | Service | Consumer | Description |
|----------|--------|---------|----------|-------------|
| `/api/v1/embed/query` | POST | ingestion-service | ai-qa-service | Generate embedding for query |
| `/api/v1/embed/batch` | POST | ingestion-service | ingestion-service | Batch embed chunks |
| `/api/v1/search/hybrid` | POST | ingestion-service | ai-qa-service | Hybrid semantic+keyword search |
| `/api/v1/rerank` | POST | ingestion-service | ai-qa-service | Rerank search results |
| `/api/v1/ingest` | POST | ingestion-service | knowledge-service | Start ingestion pipeline |
| `/api/v1/ingest/{job_id}/status` | GET | ingestion-service | knowledge-service | Check ingestion status |
| `/api/v1/ingest/{doc_id}/reindex` | POST | ingestion-service | knowledge-service | Reindex document |

---

## Event Ownership

### Events Published
| Event | Publisher | Description | Payload Fields |
|-------|-----------|-------------|----------------|
| `user.status.changed` | user-service | User account status changed | `user_id`, `old_status`, `new_status`, `changed_by`, `reason` |
| `user.revoked` | user-service | User account revoked | `user_id`, `revoked_at`, `reason`, `revoked_by` |
| `document.uploaded` | ingestion-service | Document processing complete | `document_id`, `document_version_id`, `title`, `department_id`, `status`, `uploaded_by`, `uploaded_at` |
| `document.deleted` | knowledge-service | Document deleted | `document_id`, `reason`, `deleted_by`, `deleted_at` |
| `ingestion.requested` | knowledge-service | Request document processing | `document_id`, `document_version_id`, `file_key`, `bucket_name`, `job_id`, `metadata` |
| `unanswered.question` | ai-qa-service | AI couldn't answer question | `user_id`, `message_id`, `conversation_id`, `question`, `question_normalized`, `search_query`, `top_similarity_score`, `priority` |

### Events Consumed
| Service | Consumed Events | Action |
|---------|----------------|--------|
| `auth-service` | `user.status.changed`, `user.revoked` | Update token blacklist, invalidate sessions |
| `ai-qa-service` | `user.status.changed`, `user.revoked` | Invalidate user caches, soft-delete conversations |
| `feedback-service` | `unanswered.question` | Store for admin review, notify content team |
| `ingestion-service` | `ingestion.requested`, `document.deleted` | Process document or clean up chunks |
| `knowledge-service` | `document.uploaded` | Update document status |
| `metadata-service` | `document.uploaded` | Update metadata stats |

---

## Cross-Service Dependencies

### Data Flow Dependencies
1. **Document Upload Flow**:
   - `knowledge-service` → `ingestion-service` (via `ingestion.requested`)
   - `ingestion-service` → `ai-qa-service` (via `document.uploaded`)

2. **User Status Change Flow**:
   - `user-service` → `auth-service`, `ai-qa-service` (via `user.status.changed`)

3. **AI Q&A Flow**:
   - `ai-qa-service` → `metadata-service` (HTTP: check document access)
   - `ai-qa-service` → `ingestion-service` (HTTP: vector search)
   - `ai-qa-service` → `feedback-service` (via `unanswered.question`)

### Database Access Patterns
| Service | Read Access | Write Access | Notes |
|---------|-------------|--------------|-------|
| `auth-service` | `core.*` | `core.*` | Owns `core` schema |
| `user-service` | `public.*` | `public.*` | Owns `public` schema |
| `knowledge-service` | `knowledge.*` | `knowledge.*` (except chunks) | Read/write all except chunks |
| `metadata-service` | `metadata.*` | `metadata.*` | Owns `metadata` schema |
| `ingestion-service` | `knowledge.chunks`, `knowledge.embedding_cache` | `knowledge.chunks`, `knowledge.embedding_cache` | Write-only to chunks |
| `ai-qa-service` | `knowledge.chunks`, `conversation.*` | `conversation.*`, `analytics.*` (writes) | Owns `conversation`, writes to `analytics` |
| `feedback-service` | `analytics.*` | `analytics.*` | Owns `analytics` schema |

---

## Common Ownership Questions

### Q: Who owns document access control?
**A**: `metadata-service` owns the rules (`metadata.document_access_rules`), but `ai-qa-service` has flattened copies in `knowledge.chunks` for performance.

### Q: Who can modify `knowledge.chunks`?
**A**: Only `ingestion-service` during document processing. Other services read-only.

### Q: Where do I add a new document field?
**A**: 
- File metadata → `knowledge-service` (add to `knowledge.documents`)
- Business metadata → `metadata-service` (add to `metadata.document_metadata`)
- Search metadata → `ingestion-service` (add to `knowledge.chunks`)

### Q: Who handles document deletion?
**A**: 
1. `knowledge-service` receives DELETE request
2. Marks document as deleted in `knowledge.documents`
3. Publishes `document.deleted` event
4. `ingestion-service` consumes event, soft-deletes chunks
5. `ai-qa-service` consumes event, removes from search index

### Q: Where do I add a new user field?
**A**:
- Authentication fields → `auth-service` (add to `core.users`)
- Profile fields → `user-service` (add to `core.user_profiles`)
- Department fields → `user-service` (add to `core.departments`)

---

## References

- **Service Responsibilities**: `contexts/service-boundaries/responsibilities.md` - Detailed service responsibilities
- **Event Contracts**: `contexts/service-boundaries/events.md` - Complete RabbitMQ event specifications
- **API Standards**: `contexts/service-boundaries/api-contracts.md` - API response formats and error codes
- **Database Schema**: `contexts/database/schema.md` - Table definitions per schema
- **Authorization**: `contexts/authorization/rbac-matrix.md` - Role-based access control

---

**Last Updated**: 2026-04-08  
**Maintained By**: Architecture Team  
**Critical**: Keep this matrix synchronized with implementation changes.