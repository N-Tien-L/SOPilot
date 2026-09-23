# Document Management System - Architecture & Design

## Overview

The Document Management system provides full CRUD operations for documents with MinIO storage, versioning, metadata management, access control, audit logging, and **OnlyOffice collaborative editing with GitHub-style version conflict resolution**.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js)                            │
│  Documents Page │ Document Detail │ Upload Modal │ Categories │ Tags     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ REST API (JWT Auth)
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        API Gateway (NestJS)                              │
│  Routes │ JWT Validation │ RBAC Guards │ Rate Limiting │ Proxy          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ knowledge-service │ │ metadata-service   │ │  auth-service     │
│     (8083)       │ │     (8084)        │ │    (8081)        │
│                   │ │                   │ │                   │
│ • Document CRUD   │ │ • Categories      │ │ • JWT validation  │
│ • MinIO Storage  │ │ • Tags           │ │ • User roles      │
│ • Versioning     │ │ • Access Rules   │ │ • Token refresh   │
│ • Processing     │ │ • Metadata       │ │                   │
│ • Audit Logs    │ │                   │ │                   │
└────────┬──────────┘ └────────┬─────────┘ └───────────────────┘
         │                      │
         ▼                      ▼
┌───────────────────┐ ┌───────────────────┐
│     MinIO         │ │   PostgreSQL       │
│  Object Storage   │ │   (4 schemas)     │
│                   │ │                   │
│ Bucket: documents │ │ • poliwise_auth   │
│ Presigned URLs    │ │ • poliwise_user   │
│                   │ │ • poliwise_knowledge │
│                   │ │ • poliwise_metadata  │
└───────────────────┘ └───────────────────┘
```

## Database Schema

### Schema: knowledge

| Table | Purpose |
|-------|---------|
| `documents` | Core document records with MinIO reference |
| `document_versions` | Version history for each document |
| `processing_jobs` | ETL pipeline tracking |
| `chunks` | Text chunks with vector embeddings for RAG |
| `document_audit_logs` | Full audit trail for document operations |

### Schema: metadata

| Table | Purpose |
|-------|---------|
| `categories` | Hierarchical document categories |
| `tags` | Document tags with usage tracking |
| `document_metadata` | Document metadata and lifecycle management |
| `document_tags` | Many-to-many junction for document tags |
| `document_access_rules` | ACL rules for document access control |
| `metadata_audit_logs` | Audit trail for metadata changes |

## Service Responsibilities

### knowledge-service (8083)

**Responsibilities:**
- Document upload/download with MinIO integration
- Document versioning (create new version, view history)
- Document search with pagination and filters
- Soft delete with audit logging
- Processing pipeline (parse, chunk, embed, index)
- Staging cleanup scheduler

**Key Endpoints:**
- `POST /api/v1/documents` - Upload document (ADMIN)
- `GET /api/v1/documents` - List documents with filters
- `GET /api/v1/documents/{id}` - Get document detail
- `POST /api/v1/documents/{id}/versions` - Upload new version
- `GET /api/v1/documents/{id}/versions` - Get version history
- `GET /api/v1/documents/{id}/download` - Download document
- `DELETE /api/v1/documents/{id}` - Soft delete
- `DELETE /api/v1/documents/{id}/cancel` - Cancel staging upload
- `GET /api/v1/documents/{id}/audit-logs` - Get audit logs

### metadata-service (8084)

**Responsibilities:**
- Category CRUD with hierarchy (parent-child)
- Tag CRUD with auto-slug and bulk resolve
- Document metadata management
- Access rules (ROLE, DEPARTMENT, USER level)
- Document lifecycle (DRAFT → PUBLISHED → ARCHIVED)

**Key Endpoints:**
- `GET/POST /api/v1/categories` - List/Create categories
- `GET /api/v1/categories/active/tree` - Get category tree
- `GET/POST /api/v1/tags` - List/Create tags
- `POST /api/v1/tags/resolve` - Bulk resolve tags
- `POST /api/v1/metadata` - Create document metadata
- `POST /api/v1/metadata/{id}/rules` - Add access rule
- `GET /api/v1/metadata/{id}/rules` - Get access rules

## Document Lifecycle

```
STAGING ──────► UPLOADED ──────► PARSED ──────► CHUNKED ──────► EMBEDDED ──────► READY
   │                │              │              │               │                │
   │                │              │              │               │                │
   │ Cancel          │              │              │               │                │
   │ (delete file)   │              │              │               │                │
   │                 │              │              │               │                │
   └────────────────►│              │              │               │                │
        FAIL         │              │              │               │                │
   (mark as failed)  │              │              │               │                │
                     │              │              │               │                │
                     └──────────────┴──────────────┴───────────────┴────────────────► CANCELLED
                                         FAILED
```

## Metadata Lifecycle

```
DRAFT ──────► PUBLISHED ──────► ARCHIVED ──────► EXPIRED
  │               │                │                │
  │               │                │                │
  │ Publish        │ Archive        │ Auto-expire    │
  │ (admin)       │ (admin)        │ (scheduler)    │
  │               │                │                │
  └──────────────►│◄──────────────┘                │
     Re-publish   │                                │
                  └────────────────────────────────┘
                           Re-publish
```

## Access Control

### Access Levels

| Level | Description |
|-------|-------------|
| `PUBLIC` | All authenticated users can view |
| `DEPARTMENT_ONLY` | Only users in the same department |
| `RESTRICTED` | Only users with explicit access rules |

### Access Rules

Rules are checked in order:
1. ADMIN always has access
2. PUBLIC documents are accessible to all authenticated users
3. DENY rules take precedence over VIEW rules
4. Rules checked by specificity: USER > DEPARTMENT > ROLE

### RBAC Matrix

| Action | USER | MANAGER | ADMIN |
|--------|------|---------|-------|
| View documents | ✅ | ✅ | ✅ |
| Search documents | ✅ | ✅ | ✅ |
| Download documents | ✅ | ✅ | ✅ |
| Upload document | ❌ | ❌ | ✅ |
| Delete document | ❌ | ❌ | ✅ |
| Manage categories | ❌ | ❌ | ✅ |
| Manage tags | ❌ | ✅ | ✅ |
| Set access rules | ❌ | ❌ | ✅ |
| Publish document | ❌ | ❌ | ✅ |
| Archive document | ❌ | ❌ | ✅ |

## OnlyOffice Collaborative Editing

### Architecture

```
User clicks "Edit with OnlyOffice"
    │
    ▼
Frontend → POST /documents/{id}/lock
    │
    ├─ Lock acquired (returns lockToken)
    │
    ▼
Frontend → GET /documents/{id}/editor-config
    │
    ├─ Returns JWT-signed config
    ├─ OnlyOffice iframe loads
    │
    ▼
User edits in OnlyOffice
    │
    ├─ Auto-save triggers callback to backend
    │
    ▼
POST /documents/{id}/save-callback
    │
    ├─ Validate OnlyOffice JWT token
    ├─ Check lock token ownership
    ├─ Compare version: currentVersion vs versionAtLock
    │
    ├─ No conflict (same version) → create new version, release lock
    │
    └─ Conflict detected (version changed) → return conflict status
        │
        ▼
        Frontend shows ConflictResolver (3-way diff)
        ├─ "Merge & Save": Upload merged file as new version
        ├─ "Discard Mine": Release lock, keep their version
        └─ "Force Push": Overwrite latest (ADMIN only)
```

### Conflict Resolution Flow (GitHub-style)

1. **User A** opens OnlyOffice editor for `document v1` → acquires lock (version_at_lock = 1)
2. **User B** uploads `document v2` → current_version = 2
3. **User A** saves → backend detects `current_version (2) > version_at_lock (1)` → returns conflict
4. Frontend opens `ConflictResolver` modal showing 3-way diff:
   - **Base** (v1): What User A started from
   - **Theirs** (v2): User B's new version
   - **Mine**: User A's changes (from OnlyOffice save buffer)
5. User A resolves (merge / discard / force-push)
6. New version (v3) created with merged content

### Supported File Types

| Type | Edit Mode | Conflict Resolution |
|-------|-----------|-------------------|
| DOCX | Full OnlyOffice editor | Line diff via java-diff-utils |
| TXT | Plain text mode | Line-by-line diff |
| MD | Markdown mode | Line-by-line diff with syntax |
| Image (PNG/JPG/JPEG) | View only | No diff — version tracking only |

### Lock System

- **Duration**: 30 minutes (configurable via `ONLYOFFICE_LOCK_DURATION_MINUTES`)
- **Auto-expiry**: Locks auto-release after expiry time
- **Lock refresh**: Frontend refreshes lock every 5 minutes while editing
- **One lock per document**: Attempting to lock an already-locked document returns 409 Conflict

### OnlyOffice JWT Security

The callback endpoint (`/documents/{id}/save-callback`) is authenticated via a **separate OnlyOffice JWT token** (not the user JWT). This token is generated by `knowledge-service` using the shared `ONLYOFFICE_JWT_SECRET` and verified by `OnlyOfficeCallbackFilter` before reaching the controller.

### Key Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/documents/{id}/lock` | USER/MANAGER/ADMIN | Acquire edit lock |
| DELETE | `/documents/{id}/lock` | USER/MANAGER/ADMIN | Release lock |
| GET | `/documents/{id}/editor-config` | USER/MANAGER/ADMIN | Get OnlyOffice config (JWT-signed) |
| POST | `/documents/{id}/save-callback` | OnlyOffice JWT | Process save from Document Server |
| GET | `/documents/{id}/conflict-status` | USER/MANAGER/ADMIN | Check for version conflict |
| GET | `/documents/{id}/versions/diff` | USER/MANAGER/ADMIN | Get diff between versions |
| POST | `/documents/{id}/resolve-conflict` | USER/MANAGER/ADMIN | Resolve conflict |
| POST | `/documents/{id}/force-push` | ADMIN | Force push version |
| DELETE | `/documents/{id}/versions/{n}` | ADMIN | Delete specific version (not latest) |

## Versioning

### Version Creation

When uploading a new version:
1. Document is locked with pessimistic write lock
2. New file is uploaded to MinIO with unique key
3. Version record created with changelog
4. Document's `current_version` is incremented
5. Audit log entry created

### Version History

Each version stores:
- `version_number` (v1, v2, v3...)
- `file_key` (MinIO path)
- `file_size_bytes`
- `changelog` (user-provided description)
- `created_by`
- `created_at`

## File Storage (MinIO)

### Bucket Structure

```
poliwise-documents/
├── documents/
│   ├── {documentId}/
│   │   ├── {timestamp}.pdf
│   │   ├── {timestamp}.pdf      (previous versions)
│   │   └── ...
```

### File Access

- **Upload:** Direct upload to MinIO with UUID-based key
- **Download:** Streaming through backend or presigned URL
- **URL Expiry:** Default 1 hour for presigned URLs

## Edge Cases

### Upload Failure Mid-Way

If upload succeeds but DB save fails:
- File remains in MinIO (orphaned)
- Cleanup job removes files with `deleted_at IS NULL` and `expires_at < NOW()`
- Files older than 24 hours in STAGING are cleaned up

### Cancel Upload for Non-Staging

Only documents in `STAGING` status can be cancelled. Attempting to cancel other statuses returns 400 error.

### Race Condition on Version Creation

Uses pessimistic locking (`SELECT ... FOR UPDATE`) to prevent concurrent version creation.

### Download Deleted Document

Returns 404 if document's `deleted_at IS NOT NULL`.

### Duplicate File Upload

UUID-based document ID ensures no collision. Files are never overwritten.

## Performance Considerations

- Pagination: Default 20 items, max 100
- Search: Debounced 300ms
- Download: Streaming response for large files
- MinIO: Presigned URLs for direct browser access
- Indexes: Optimized for common query patterns
