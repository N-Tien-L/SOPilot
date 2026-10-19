# Poliwise — Feature Design Reference

> **Purpose**: This document describes the design of every feature in Poliwise. Use this to verify that the actual implementation matches the intended design. Each section covers the feature's owner, schema, key capabilities, data flow, and access control.
>
> **Language**: English (technical terms in Vietnamese where used in code/UI).

---

## Table of Contents

1. [Authentication & Session Management](#1-authentication--session-management)
2. [User & Department Management](#2-user--department-management)
3. [Document Lifecycle Management](#3-document-lifecycle-management)
4. [Document Processing Pipeline (Ingestion)](#4-document-processing-pipeline-ingestion)
5. [Document Upload Deduplication](#5-document-upload-deduplication)
6. [Metadata & Classification](#6-metadata--classification)
7. [AI Q&A Chat (RAG)](#7-ai-qa-chat-rag)
8. [User Query Safeguard — 3-Layer Processing Pipeline](#8-user-query-safeguard--3-layer-processing-pipeline)
9. [Feedback & Rating](#9-feedback--rating)
10. [Analytics & Reporting](#10-analytics--reporting)
11. [RBAC — Role-Based Access Control](#11-rbac--role-based-access-control)
12. [API Gateway Cross-Cutting Concerns](#12-api-gateway-cross-cutting-concerns)
13. [Scheduled Background Jobs](#13-scheduled-background-jobs)
14. [User Behavior & Violation Management](#14-user-behavior--violation-management)
15. [Cross-Feature Interactions](#15-cross-feature-interactions)

---

## 1. Authentication & Session Management

**Owner**: `auth-service` (port 8081)
**Schema**: `core`

### 1.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Login | Username/password → verify credentials → check account lock → create JWT (15 min) + refresh token (7 days) → log to `login_history` |
| Register | Admin only. Creates user in `core.users`, emits `user.registered` event to RabbitMQ |
| Refresh token | Rotate refresh token (invalidate old, issue new). Detects reuse (token theft attack) → revoke all sessions |
| Logout (single device) | Blacklist access token in `access_token_blacklist` + revoke that specific refresh token |
| Logout (all devices) | Revoke all refresh tokens for the user |
| Account lock | After 5 consecutive failed logins → lock for 15 minutes |
| Bootstrap admin | On first startup, create default admin account if none exists |
| Forgot password | User requests reset → server generates OTP/token → emailed → user submits new password |
| Change password | Authenticated user verifies old password, updates hash |

### 1.2 Data Flow

```
User → POST /api/v1/auth/login (Gateway)
     → auth-service (8081): verify credentials, check lock
     → AuthService: update failed attempts, save login history
     → RefreshTokenService: create refresh token (DB)
     → JwtTokenProvider: create access token (JWT)
     ← TokenResponse { access_token, refresh_token, expires_in }
```

### 1.3 Session Tracking

Every login is recorded in `core.login_history`: IP address, device type, user-agent, login status (SUCCESS/FAILED), failure reason if applicable.

### 1.4 RBAC

All auth endpoints are public (no JWT required to call them) except change-password which requires an active session.

---

## 2. User & Department Management

**Owner**: `user-service` (port 8082)
**Schema**: `public` (default)

### 2.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| View own profile | USER sees their own name, email, department, phone, position, bio |
| Update profile | USER updates `fullName`, `email`, `phone`, `position`, `bio` |
| Change department | USER requests department change |
| Search users | ADMIN/MANAGER search by username, email, role, department, status with pagination |
| Change user status | ADMIN transitions user: ACTIVE ↔ DEACTIVATED ↔ REVOKED |
| Soft delete user | ADMIN sets `deleted_at` timestamp |
| Departments | Pre-seeded list (Engineering, HR, Finance, Operations, Legal, Marketing, Sales). ADMIN CRUD with hierarchical tree support |

### 2.2 Data Flow

- On `user.registered` event from `auth-service` → user-service creates a `user_profile` entry.
- On `user.status.changed` event → user-service updates the user's account state.
- User-service never writes to `core` schema directly — auth-service owns `core.users`. User-service reads `core.users` for status checks.

### 2.3 Department-Document Relationship (Many-to-Many)

The system uses a **junction table pattern** for multi-department document ownership:

```
┌─────────────────┐       ┌──────────────────────────┐       ┌────────────────────────┐
│  departments     │       │  department_documents    │       │  document_metadata      │
├─────────────────┤       ├──────────────────────────┤       ├────────────────────────┤
│ id (PK)         │◄──────│ department_id (FK)       │──────►│ document_id (FK)        │
│ name            │       │ document_metadata_id(FK) │       │ title                  │
│ parent_id (FK)  │       │ granted_at               │       │ department_id (legacy) │
│ ...             │       │ granted_by (FK)          │       │ ...                    │
└─────────────────┘       │ permission_level         │       └────────────────────────┘
                          │ is_primary_owner        │
                          └──────────────────────────┘
```

**Key Design Principles:**

1. **Primary Owner**: One department is designated as `is_primary_owner = true` (the original uploader's department)
2. **Granular Permissions**: `permission_level` field supports: `VIEW`, `CONTRIBUTE`, `MANAGE`
3. **Safe Deletion**: Removing a department relationship does NOT delete the document or break other relationships
4. **Audit Trail**: `granted_at` and `granted_by` track when/how the relationship was created

### 2.4 RBAC

| Operation | USER | MANAGER | ADMIN |
|-----------|:----:|:-------:|:-----:|
| View own profile | ✅ | ✅ | ✅ |
| Update own profile | ✅ | ✅ | ✅ |
| Search users | ❌ | ✅ | ✅ |
| View user detail | ❌ | ✅ | ✅ |
| Change user status | ❌ | ❌ | ✅ |
| Soft delete user | ❌ | ❌ | ✅ |
| Manage departments | ❌ | ❌ | ✅ |

---

## 3. Document Lifecycle Management

**Owner**: `knowledge-service` (port 8083)
**Schema**: `knowledge` (read), `ingestion-service` (write)
**RBAC**: Only ADMIN can upload, delete, confirm metadata. All authenticated users can view/download.

### 3.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Upload | **USER/MANAGER/ADMIN** uploads file → stored in MinIO → `Document` record (status: STAGING) → `DocumentVersion` → `ProcessingJob` (PENDING) → publishes `ingestion.requested` to RabbitMQ. **See Section 3.5 for department relationship creation logic.** |
| Confirm metadata | ADMIN reviews AI-suggested title/category/tags → confirms → metadata created in `metadata-service` → document status moves to READY |
| Trigger processing | ADMIN calls process endpoint → async pipeline begins |
| Soft delete | ADMIN/MANAGER (primary owner) sets `deleted_at` → publishes `document.deleted` → ingestion-service marks chunks inactive. **See Section 3.6 for relationship deletion rules.** |
| Cancel upload | Uploader cancels STAGING documents before confirmation |
| Document versioning | Every re-upload creates a new `document_versions` entry. Users view version history and compare any two versions |
| Policy comparison | ADMIN/MANAGER selects two documents → extract plain text → compute line-level diff → return added/removed/modified sections |
| OnlyOffice editing | ADMIN/MANAGER (with edit permission) acquires edit lock → opens OnlyOffice editor → callback saves → lock released. Conflict detected if another version was pushed while editing |
| Staging cleanup | Scheduled job removes STAGING documents older than 10 minutes with no confirmation |
| Download | Authenticated users download file via presigned MinIO URL |

### 3.2 Document Status Flow

```
STAGING → UPLOADED → PARSING → PARSED → CHUNKING → CHUNKED
       → EMBEDDING → EMBEDDED → INDEXING → INDEXED → READY
                                                           → FAILED
                                                           → DUPLICATE
```

### 3.3 Data Flow

```
Admin/Manager/User → POST /api/v1/documents/upload (Gateway)
      → knowledge-service (8083): receive file
      → StorageService: upload to MinIO
      → DocumentService: create Document + DocumentVersion + ProcessingJob
      → DepartmentRelationshipService: create department_documents entry
        - For USER/MANAGER: auto-link to user's department with MANAGE permission, is_primary_owner = true
        - For ADMIN: use selected department from request body (see Section 11.9)
      → DocumentEventPublisher: publish ingestion.requested
      → RabbitMQ → metadata-service: create DocumentMetadata (pending)
      ← DocumentResponse (STAGING, metadata suggestion pending)

Admin → POST /api/v1/documents/:id/confirm
     → DocumentService: resolve category/tags via MetadataServiceClient
     → DocumentMetadataService: create metadata in metadata-service
     → DocumentService: update status = READY
     ← DocumentResponse (READY)
```

### 3.5 Upload Department Relationship Creation

When a user uploads a document, the system creates a relationship in `department_documents` based on the uploader's role:

**USER/MANAGER Upload**:
- Target department = uploader's department (automatic)
- `permission_level` = `MANAGE`
- `is_primary_owner` = `true`
- `granted_by` = uploader's user ID

**ADMIN Upload** (Option B - Manual Selection):
- Target department = selected from dropdown in upload UI (required)
- `permission_level` = `MANAGE`
- `is_primary_owner` = `true`
- `granted_by` = ADMIN's user ID
- If no department is selected → API returns `400 BAD_REQUEST` with error code `MISSING_DEPARTMENT`

**Deduplication Case**:
- If duplicate detected → see Section 5.4 for relationship handling
- The duplicate document version links to the original, but creates a NEW `department_documents` entry for the uploader's/selected department

**Upload Request Payload** (ADMIN):
```json
{
  "file": "...",
  "departmentId": "uuid-of-target-department",
  "metadata": {
    "title": "...",
    "description": "..."
  }
}
```

**Upload Request Payload** (USER/MANAGER):
```json
{
  "file": "...",
  "metadata": {
    "title": "...",
    "description": "..."
  }
}
// departmentId is auto-set from JWT context (X-Department-Id header)
```

### 3.6 Document Deletion and Relationship Cleanup

When deleting a document, the system follows a specific sequence to preserve data integrity:

**Soft Delete by ADMIN**:
1. Verify caller has delete permission (ADMIN role OR primary owner department with MANAGE permission)
2. Set `document_metadata.deleted_at = NOW()`
3. Publish `document.deleted` event with `document_id`
4. ingestion-service marks chunks inactive (`is_latest = false`)
5. **Decision point**: 
   - If document has only ONE department relationship → keep relationship for audit trail
   - If document has MULTIPLE department relationships → ask admin: "Remove all relationships?" (default: yes, but document remains queryable by ADMIN for audit)

**Soft Delete by MANAGER** (primary owner only):
1. Verify caller's department is `is_primary_owner = true` for this document
2. Same flow as ADMIN

**Relationship-Only Deletion** (remove one department's access without deleting document):
- Any department with `MANAGE` or `CONTRIBUTE` permission can request removal of their own relationship
- Creates a deletion request → primary owner approves → relationship removed
- Document remains active for other departments
- Audit log captures: who requested, who approved, which department removed

**Cascade Rules**:
- Deleting a department → all `department_documents` for that department are soft-deleted (not hard-deleted)
- Documents become inaccessible to the deleted department but remain accessible to other linked departments

---

## 4. Document Processing Pipeline (Ingestion)

**Owner**: `ingestion-service` (port 8088)
**Schema**: `knowledge` (write)
**Trigger**: `ingestion.requested` RabbitMQ event from `knowledge-service`

### 4.1 Processing Stages

| Stage | Tool | Description |
|-------|------|-------------|
| Text extraction | PyMuPDF (PDF), python-docx (DOCX/DOC), openpyxl (XLSX), pytesseract (OCR), direct read (TXT/MD) | Convert file to plain text |
| Standardization | Unicode NFC normalization, markdown heading detection, policy clause regex | Normalize content |
| AI metadata suggestion | Groq LLM (llama-3.3-70b) | Suggest title, category, tags from content |
| Chunking | Parent-child strategy: parent ~1500 chars, child ~400 chars, configurable overlap | Split into retrievable units |
| Embedding | BGE-M3 via LitServe HTTP API (port 8001) | Dense + sparse (colbert) vectors |
| Job tracking | `processing_jobs` table | Status per stage |

### 4.2 RBAC

Internal — triggered by RabbitMQ events. Only ADMIN can trigger via the process endpoint.

### 4.3 ACL Flattening

At chunk creation time, the ingestion-service receives flattened ACL data in the RabbitMQ event payload and assigns it to every chunk row:

```sql
INSERT INTO knowledge.chunks (
    id, document_id, chunk_type, content,
    embedding_vector, allowed_roles, allowed_departments, access_level, is_latest
) VALUES (
    :id, :doc_id, 'child', :content,
    :embedding, :allowed_roles, :allowed_departments, :access_level, true
);
```

---

## 5. Document Upload Deduplication

**Owner**: `ingestion-service` (port 8088)
**Schema**: `knowledge`
**Trigger**: Every document upload via `ingestion.requested` RabbitMQ event

### 5.1 Design Overview

A **3-layer deduplication strategy** prevents storing duplicate documents at three levels of precision. Each layer runs sequentially; the first layer that detects a duplicate stops the pipeline and marks the document as `DUPLICATE`.

```
Admin uploads file
        │
        ▼
┌───────────────────────────────────────────────────────┐
│ Layer 1 — Exact File Checksum (SHA-256)               │
│ Compare raw file bytes. Catches: identical files,     │
│ same file uploaded twice, renamed files.              │
└───────────────────────────────────────────────────────┘
        │ Not duplicate
        ▼
┌───────────────────────────────────────────────────────┐
│ Layer 2 — Exact Content Hash (SHA-256 of text)        │
│ Compare extracted plain text. Catches: same content   │
│ in different formats (PDF→DOCX), minor formatting     │
│ differences that preserve text.                        │
└───────────────────────────────────────────────────────┘
        │ Not duplicate
        ▼
┌───────────────────────────────────────────────────────┐
│ Layer 3 — Semantic / Near-Duplicate Fingerprint       │
│ Compare embedding vectors of extracted text.         │
│ Catches: substantially similar documents, revisions    │
│ with minor changes. Threshold: similarity ≥ 0.98.    │
└───────────────────────────────────────────────────────┘
        │ Not duplicate
        ▼
  Continue ingestion pipeline
```

### 5.2 Layer Details

**Layer 1 — Exact File Checksum**:
- Compute `SHA-256(file_bytes)` on the raw uploaded file.
- Query `knowledge.document_versions` for any existing version with the same `file_checksum`.
- Schema column: `document_versions.file_checksum`.
- On duplicate: mark `DUPLICATE`, link to existing, stop processing, job marked `COMPLETED`.

**Layer 2 — Exact Content Hash**:
- Extract plain text → Unicode NFC normalize → collapse whitespace → `SHA-256(normalized_text)`.
- Schema column: `document_versions.content_hash`.
- Catches: same content extracted from different file formats.

**Layer 3 — Semantic / Near-Duplicate Fingerprint**:
- Generate BGE-M3 embedding vector of full document text.
- Compare against all existing document version embeddings.
- Threshold: ≥ 0.98 = duplicate, 0.85–0.97 = logged warning (processing continues), < 0.85 = no action.
- Schema column: `document_versions.semantic_fingerprint vector(1024)`.

### 5.3 Duplicate Handling

When any layer detects a duplicate:

```python
async def _handle_duplicate(job_id, document_id, version_id, result) -> dict:
    await processing_job_service.complete(job_id, status="COMPLETED")
    await document_repo.update_status(document_id, status="DUPLICATE")
    await version_repo.set_duplicate_reference(
        version_id=version_id,
        duplicate_of_id=result.existing_document_id,
        layer=result.layer,           # 1, 2, or 3
        similarity=result.similarity,   # 1.0 for Layers 1&2, <1.0 for Layer 3
    )
    return {
        "status": "DUPLICATE",
        "layer": result.layer,
        "duplicate_of_document_id": result.existing_document_id,
        "message": "Document is a duplicate. No new chunks were created.",
    }
```

Duplicate checks exclude: the current document itself, `DELETED` documents, and documents already marked as duplicates.

### 5.4 Deduplication with Department Relationships

With the Many-to-Many department-document relationship, deduplication behaves as follows:

**Duplicate Detection**:
- Duplicates are detected system-wide, regardless of which department originally uploaded the document
- When a duplicate is detected, the new document links to the existing one via `duplicate_of_document_id` in `document_versions`

**Department Relationship Inheritance**:
- A duplicate document **does not automatically inherit** the department relationships of the original
- The uploader's/selected department creates a **new relationship entry** for the duplicate document
- Original document's relationships remain unchanged
- Admins can manually add additional department relationships after reviewing the duplicate

**Duplicate Flow**:

```
User A (Sales) uploads "Policy.pdf"
  → No duplicate found
  → Creates department_documents: (Sales, doc_X, MANAGE, is_primary=true)
  → Processing pipeline creates chunks for doc_X

User B (Marketing) uploads identical "Policy.pdf"
  → Layer 1/2/3 detects duplicate of doc_X
  → Creates new document_metadata entry (doc_Y) with status = DUPLICATE
  → Creates document_version for doc_Y with duplicate_of_document_id = doc_X
  → Creates department_documents: (Marketing, doc_Y, MANAGE, is_primary=true)
  → No new chunks created for doc_Y
  → Both Sales (via doc_X) and Marketing (via doc_Y) can see the duplicate banner

Result:
  - doc_X has chunks, searchable in AI Q&A
  - doc_Y is a marker pointing to doc_X, no chunks
  - Each department maintains its own "entry point" to the document
```

**Duplicate Information Display**:
- Users see a banner: "This document is a duplicate of [original document name]" on duplicate document detail pages
- Duplicate information is visible to all users with access to the document (via their department relationship)
- The banner links to the original document for chunk retrieval

**Edge Cases**:
- If the original document is soft-deleted after a duplicate is created → the duplicate remains accessible to its own departments (via its own relationships)
- If a duplicate is "promoted" to a unique document (admin action) → it gets its own chunks created via re-processing
- If all departments linked to the original are removed → the original becomes orphaned but chunks remain (admin can reassign)

---

## 6. Metadata & Classification

**Owner**: `metadata-service` (port 8084)
**Schema**: `metadata`

### 6.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Categories | Hierarchical (parentId). ADMIN CRUD. Active categories shown publicly. |
| Tags | ADMIN CRUD with auto-generated slugs and colors. Usage count tracked. Bulk find-or-create supported. |
| Document metadata | title, description, category, tags, document type (POLICY/GENERAL), access level (PUBLIC/PRIVATE), lifecycle status |
| Access rules | Per-document ACLs: allow/deny by role, by department, or by specific user |
| Lifecycle status | DRAFT → REVIEW → PUBLISHED → ARCHIVED → DELETED |
| Auto-archive | Scheduled job (1 AM daily) archives documents past their `expires_at` date |
| Access simulation | ADMIN can preview which users/roles/departments would have access before saving rules |

### 6.2 RBAC

Only ADMIN can create/modify categories, tags, and access rules. Metadata creation is triggered automatically when admin confirms a document.

---

## 7. AI Q&A Chat (RAG)

**Owner**: `ai-qa-service` (port 8086)
**Schemas**: `conversation` (write), `analytics` (write); reads `knowledge` + `metadata`

### 7.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Ask question | User sends message → query embedding → hybrid search (dense + sparse) on `knowledge.chunks` with ACL filtering → top-k → rerank → build prompt → call LLM → stream response |
| Streaming | Server-Sent Events (SSE) streams token-by-token to frontend |
| Conversation management | Chat sessions stored in `conversations`. Each message in `messages`. User views history, deletes conversation, clears messages |
| Sources | Retrieved chunks attached as citations (document title + snippet) |
| Mark unanswered | If top similarity < 0.3 → publish `unanswered.question` event → `feedback-service` stores for manager review |
| Auto-generate title | Background task on first message of a new conversation |

### 7.2 RAG Retrieval Flow

```
User query
    │
    ▼
Embedding (BGE-M3, port 8001)
    │
    ▼
Hybrid Search: dense vector + BM25 full-text → RRF fusion → top-50
    │ ACL filter (dual-strategy pattern - see Section 11.5):
    │   1. Flattened arrays on knowledge.chunks (allowed_departments, allowed_roles)
    │   2. Junction table join: metadata.department_documents
    │   Final result = UNION of both sources
    ▼
BGE-Reranker (port 8002) → top-5 chunks
    │
    ▼
LLM (user-selected model) → answer with citations
```

**Department Relationship Integration in AI Search**:

When a user asks a question, the system filters chunks using BOTH strategies:

1. **Flattened Array Check** (fast path): Check `chunks.allowed_departments @> ARRAY[:user_dept_id]`
2. **Junction Table Check** (covers new relationships): JOIN `metadata.department_documents` on `document_id` WHERE `department_id = :user_dept_id`

**Why dual-check?**
- Flattened arrays are denormalized for performance but may lag behind real-time relationship changes
- Junction table is the source of truth but requires a JOIN
- The UNION ensures newly created relationships (not yet propagated to chunks) are immediately effective

**Propagation Flow on Relationship Change**:

```
Admin creates new department_documents entry
    │
    ▼
metadata-service: INSERT into department_documents
    │
    ▼
Publish document.permissions.changed event → ingestion-service
    │
    ▼
ingestion-service: batch update knowledge.chunks.allowed_departments
    │
    ▼
Eventual consistency (sub-second delay)
```

Until propagation completes, the junction table check ensures the new relationship is immediately effective for AI search.

### 7.3 RBAC

All authenticated users (USER/MANAGER/ADMIN) can chat. Streaming and history are per-user.

---

## 8. User Query Safeguard — 3-Layer Processing Pipeline

**Owner**: `ai-qa-service` (port 8086)
**Entry point**: `POST /api/v1/ai/chat` and `POST /api/v1/ai/chat/stream`

### 8.1 Design Overview

Every user query passes through a **3-layer processing pipeline** before reaching RAG + LLM generation.

| Layer | Name | Model | Purpose | Cost |
|-------|------|-------|---------|------|
| 1 | Toxic Filter | `meta-llama/llama-prompt-guard-2-22m` (Groq) | Block harmful, jailbreak, and injection queries | Very cheap |
| 2 | Intent Classifier + Simple Responder | `llama-3.1-8b-instant` (Groq) | Classify as SIMPLE or COMPLEX; answer SIMPLE directly | Cheap |
| 3 | Core RAG + Generation | User-selected model | Full RAG pipeline for complex queries | Most expensive |

```
User Query
    │
    ▼
┌────────────────────────────────────────────────────┐
│ LAYER 1 — Toxic Filter                             │
│ llama-prompt-guard-2-22m, < 200ms, fail-open       │
└────────────────────────────────────────────────────┘
    │ JAILBREAK / INJECTION → Block, return error
    │ BENIGN ↓
    ▼
┌────────────────────────────────────────────────────┐
│ LAYER 2 — Intent Classifier                        │
│ llama-3.1-8b-instant, [SIMPLE] or [COMPLEX]       │
└────────────────────────────────────────────────────┘
    │ SIMPLE → Layer 2 Responder answers directly
    │ COMPLEX ↓
    │     → Query Refiner (de-contextualize + expand)
    ▼
┌────────────────────────────────────────────────────┐
│ LAYER 3 — Core RAG + Generation                   │
│ Hybrid search → rerank → LLM → response            │
│ Background: title generation, unanswered detection   │
└────────────────────────────────────────────────────┘
    │ Rate limited → HTTP 429 with available models
    │ OK ↓
  Response (+ sources)
```

### 8.2 Layer 1 — Toxic Filter

- **Model**: `meta-llama/llama-prompt-guard-2-22m` via Groq API.
- **Threshold**: `score > 0.75`.
- **Output**: `{ is_toxic: bool, label: str }`. Labels: `BENIGN`, `JAILBREAK`, `INJECTION`.
- **Keyword pre-check**: Supplementary regex patterns applied to Unicode-normalized, whitespace-collapsed input catch obvious bypasses (Unicode lookalikes, extra spaces, leetspeak).
- **Fail-open**: If Groq Layer 1 API is unavailable → log warning → allow the query through.
- **On toxic detection**: Return `PipelineResult(status="BLOCKED", layer_stopped=1, response="Nội dung không phù hợp. Vui lòng diễn đạt lại câu hỏi.")`.

### 8.3 Layer 2 — Intent Classifier

- **Model**: `llama-3.1-8b-instant` via Groq API.
- **SIMPLE**: Greetings, small talk, simple calculations, general knowledge not requiring documents.
- **COMPLEX**: Questions about policies, internal documentation, analysis, synthesis, anything needing a document source.
- **Viet-English code-switching**: Prompt must include mixed-language examples (`"policy về remote work như thế nào?" → COMPLEX`).
- **SIMPLE path**: `Layer2Responder` answers directly with `llama-3.1-8b-instant`. No RAG. Message saved with `metadata.processing_layer = 2`.
- **COMPLEX path**: `QueryRefiner` de-contextualizes, expands keywords, resolves ambiguity. Output: `{ refined_query, search_keywords, filters_hint }`.
- **Fail-safe**: If LLM call errors → treat as `COMPLEX` (proceed to Layer 3).

### 8.4 Layer 3 — Core RAG + Generation

See Section 7 for the RAG retrieval flow. Additional Layer 3 behaviors:

- **Model Registry**: Users select from available models (local, Groq, OpenRouter, Gemini). Registry tracks per-model availability: `AVAILABLE | RATE_LIMITED | UNAVAILABLE`.
- **Rate limit handling**: On HTTP 429 from provider → mark model as `RATE_LIMITED` → return HTTP 429 to client with `{ status: "RATE_LIMITED", available_models: [...] }` → auto-reset after 5 minutes.
- **Knowledge gap detection**: If `top_similarity < 0.3` → publish `unanswered.question` event to RabbitMQ asynchronously.
- **Auto title generation**: Background task (non-blocking) on first message of new conversation. Uses `llama-3.1-8b-instant` to generate a 4–10 word title.

### 8.5 Context Isolation — Layer 3 History Only

Only messages with `metadata.processing_layer = 3` are included in the RAG context. Layer 2 chitchat messages are excluded to prevent context poisoning and token waste.

```python
# Only Layer 3 messages in context
WHERE conversation_id = :id
  AND role IN ('USER', 'ASSISTANT')
  AND (metadata->>'processing_layer')::int = 3
ORDER BY created_at DESC
LIMIT :limit
```

### 8.6 Message Metadata Per Layer

```python
# Layer 2
metadata = {
    "processing_layer": 2,
    "intent": "SIMPLE",
    "layer1_latency_ms": 150,
    "layer2_latency_ms": 320,
}

# Layer 3
metadata = {
    "processing_layer": 3,
    "intent": "COMPLEX",
    "refined_query": "...",
    "layer1_latency_ms": 150,
    "layer2_latency_ms": 280,
    "layer3_latency_ms": 1200,
    "model_used": "groq/llama-70b",
    "retrieval_chunks_count": 5,
    "reranking_applied": True,
}
```

---

## 9. Feedback & Rating

**Owner**: `feedback-service` (port 8085)
**Schema**: `analytics`

### 9.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Submit feedback | User rates a message: LIKE or DISLIKE. Stored with tokens_prompt, tokens_completion, latency_ms, model_used |
| No duplicate | One feedback entry per user per message (enforced at DB level) |
| Delete own feedback | User can remove their own feedback |

### 9.2 RBAC

Any authenticated user can submit feedback on their own messages.

---

## 10. Analytics & Reporting

**Owner**: `feedback-service` (port 8085)
**Schema**: `analytics`
**RBAC**: Dashboard, analytics, reports → MANAGER+. Audit logs → ADMIN only.

### 10.1 Key Capabilities

| Capability | Design |
|-----------|--------|
| Dashboard overview | Today's questions, weekly questions, active users, unanswered count, satisfaction rate |
| Trends | Daily/weekly line charts: questions asked, feedback ratio, response time, unique users |
| Top questions | Most frequently asked questions (text-normalized) |
| Top documents | Most-cited documents (from message citations + liked citations) |
| Department stats | Per-department question counts and satisfaction |
| Unanswered questions | Manager+ views questions marked unanswered. Can mark as RESOLVED. |
| Audit logs | All significant system actions logged: login, upload, delete, status change, export, role change. Each log entry includes `department_id` to track the scope of operations for multi-department auditing. |
| Report export | Manager+ creates async export job (CSV, JSON) → PENDING → PROCESSING → COMPLETED/FAILED → downloadable link (expires 7 days) |

### 10.2 Data Flow

```
User → POST /api/v1/feedback (Gateway)
     → feedback-service (8085)
     → FeedbackService: validate (no duplicate user+message)
     → FeedbackRepository: save
     ← FeedbackResponse

Admin → POST /api/v1/analytics/reports (Gateway)
      → feedback-service
      → ReportExportService: create PENDING job
      → Background worker: generate CSV/JSON
      → Update job status = COMPLETED
      ← ReportDownloadResponse (download URL, expires 7 days)
```

### 10.3 Audit Logging with Department Context

All audit log entries capture the department scope in which the action was performed. This enables:

1. **Multi-department auditing**: Track which department a user was acting on behalf of
2. **Manager activity tracking**: Managers' document operations are logged with their department context
3. **Compliance reporting**: Generate department-specific audit trails

**Audit Log Schema (Updated)**:

```sql
CREATE TABLE analytics.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    username VARCHAR(50),
    user_role VARCHAR(20),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    resource_name VARCHAR(255),
    -- NEW: Department context
    department_id UUID,              -- Department scope of the action
    department_name VARCHAR(255),    -- Denormalized for reporting
    -- ... other existing fields ...
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Department Context Capture Rules**:

| Action Type | Department Captured | Example |
|------------|---------------------|---------|
| Document Upload | Uploader's department | Manager uploads to "Marketing" → logs `department_id = Marketing` |
| Document Edit | Editor's department | Manager edits "Sales" doc → logs `department_id = Sales` |
| Document View | Viewer's department | USER views doc → logs `department_id = USER's department` |
| Cross-dept Share | Sharing department | Marketing shares with Sales → logs `department_id = Marketing` |

---

## 11. RBAC — Role-Based Access Control

**Owner**: Distributed — API Gateway (enforcement), each service (data-level)
**Reference**: `contexts/authorization/rbac-matrix.md`

### 11.1 Design Overview

Poliwise uses a **3-layer RBAC enforcement strategy**:

```
Request → API Gateway (NestJS)
              │ JWT validation
              │ Role extraction
              │ Route-level role guard
              ▼
         Downstream Service (Spring Boot / FastAPI)
              │ Method-level annotation
              │ ACL check (document_access_rules)
              ▼
         Database (schema-level ownership)
```

### 11.2 Role Definitions

| Role | Focus | System Impact |
|------|-------|--------------|
| `USER` | AI consumer, knowledge reader | Low — read operations only |
| `MANAGER` | Analytics, reporting, team monitoring | Medium — read-heavy on analytics |
| `ADMIN` | Full system control, document management, user administration | High — write operations across schemas |

**No automatic role inheritance** — every protected endpoint must explicitly list all allowed roles.

### 11.3 Layer 1 — Gateway Route Enforcement (NestJS)

Every route declares which roles can access it:

```typescript
const routes: ProxyRoute[] = [
  // All authenticated users
  { path: '/api/v1/ai/chat', method: 'POST', target: AI_QA_SERVICE_URL,
    guards: [JwtAuthGuard], roles: ['USER', 'MANAGER', 'ADMIN'] },
  // Manager+ only
  { path: '/api/v1/analytics/dashboard', method: 'GET', target: FEEDBACK_SERVICE_URL,
    guards: [JwtAuthGuard], roles: ['MANAGER', 'ADMIN'] },
  // Admin only
  { path: '/api/v1/documents/upload', method: 'POST', target: KNOWLEDGE_SERVICE_URL,
    guards: [JwtAuthGuard], roles: ['ADMIN'] },
]
```

**JWT payload**:
```json
{ "sub": "user-uuid", "role": "USER", "department_id": "dept-uuid", "exp": 1735689600 }
```

**Gateway injects headers before proxying**: `X-User-Id`, `X-Role`, `X-Department-Id`, `X-Trace-ID`. Downstream services trust these headers as authoritative.

### 11.4 Layer 2 — Service-Level Method Enforcement (Spring Boot)

```java
@PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
public Document getDocument(UUID id) { ... }

@PreAuthorize("hasRole('ADMIN')")
public Document uploadDocument(MultipartFile file) { ... }

@PreAuthorize("hasRole('ADMIN') or @documentPermissionEvaluator.hasAccess(#documentId, authentication)")
public Document getDocument(UUID documentId) { ... }
```

### 11.5 Layer 3 — Data-Level ACL (Dual-Strategy Pattern)

**Source of truth**: `metadata.document_access_rules` — for real-time CRUD operations.
**Read-optimized**: Flattened arrays in `knowledge.chunks` — for fast AI vector search.

#### Rule Types

| Target Type | Permission | Meaning |
|-------------|------------|---------|
| `ROLE` | `VIEW` | All users with this role can view |
| `ROLE` | `DENY` | All users with this role are denied |
| `DEPARTMENT` | `VIEW` | Members of this department can view |
| `USER` | `VIEW` | This specific user can view |
| `USER` | `DENY` | This specific user is denied |

#### Priority Order

1. **Explicit DENY** for user/role/department → **always deny**
2. **Explicit VIEW** for user/role/department → **allow**
3. `access_level = 'PUBLIC'` → **allow all authenticated users**
4. `access_level = 'DEPARTMENT_ONLY'` + user in same department → **allow**
5. Default → **deny**

#### AI Vector Search ACL Filter

> **Note on Dual-Strategy Pattern**: For AI vector search performance, ACL filtering uses the flattened arrays in `knowledge.chunks` (`allowed_departments`). For CRUD ownership checks (who can edit/delete), the system uses the `department_documents` junction table. See [Section 2.3](#23-department-document-relationship-many-to-many).

```sql
WHERE (
    c.access_level = 'PUBLIC'
    OR c.allowed_roles @> ARRAY[:user_role]::TEXT[]
    OR c.allowed_departments @> ARRAY[:user_dept_id]::UUID[]
    OR c.allowed_users @> ARRAY[:user_id]::UUID[]
)
```

#### Department-Joined Query for Document Lists

For listing documents (not AI search), use the junction table for accurate department-scoped queries:

```sql
-- Get all documents accessible to a specific department
SELECT dm.* FROM metadata.document_metadata dm
JOIN metadata.department_documents dd ON dd.document_metadata_id = dm.id
WHERE dd.department_id = :user_department_id
  AND dm.deleted_at IS NULL
ORDER BY dm.updated_at DESC;
```

#### ACL Update on Permission Changes

When admin changes permissions: metadata-service updates `document_access_rules` → publishes `document.permissions.changed` event → ingestion-service batch-updates all `knowledge.chunks` for that document. This is eventual consistency (sub-second delay).

### 11.6 RBAC Matrix

| # | Functionality | USER | MANAGER | ADMIN |
|---|-------------|:----:|:-------:|:-----:|
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
| 13 | Upload Knowledge Documents | ❌ | ✅¹ | ✅ |
| 14 | Manage Document Metadata | ❌ | ✅¹ | ✅ |
| 15 | Create / Lock / Revoke User Accounts | ❌ | ❌ | ✅ |
| 16 | Manage Document Versions | ❌ | ✅¹ | ✅ |
| 17 | Create Single User | ❌ | ❌ | ✅ |
| 18 | Create Bulk Users | ❌ | ❌ | ✅ |
| 19 | View User Login History | ❌ | ❌ | ✅ |
| 20 | Deactivate / Reactivate Users | ❌ | ❌ | ✅ |
| 21 | Search Users | ❌ | ✅ | ✅ |
| 22 | View User Detail (full info) | ❌ | ✅ | ✅ |
| 23 | Update User Role | ❌ | ❌ | ✅ |
| 24 | Assign User to Department | ❌ | ❌ | ✅ |
| 25 | Soft Delete User | ❌ | ❌ | ✅ |
| 26 | View All Departments | ❌ | ❌ | ✅ |
| 27 | Create Department | ❌ | ❌ | ✅ |
| 28 | Edit Department | ❌ | ❌ | ✅ |
| 29 | Deactivate / Activate Department | ❌ | ❌ | ✅ |
| 30 | View Department Users | ❌ | ❌ | ✅ |

> ¹ **MANAGER**: Allowed only for documents linked to the Manager's department via `department_documents` junction table with sufficient `permission_level` (`CONTRIBUTE` or `MANAGE`). See [Section 2.3](#23-department-document-relationship-many-to-many) for details.

### 11.7 MANAGER Document Scope Rules

When a MANAGER performs document operations, the system enforces the following scope rules:

```sql
-- Example: Check if manager can edit a document
SELECT EXISTS (
    SELECT 1 FROM metadata.department_documents dd
    JOIN core.users u ON u.department_id = dd.department_id
    WHERE dd.document_metadata_id = :document_metadata_id
      AND u.id = :manager_user_id
      AND dd.permission_level IN ('CONTRIBUTE', 'MANAGE')
) AS can_edit;
```

**Scope Enforcement Rules:**

1. **Upload**: Manager can only upload documents to their own department (auto-linked with `MANAGE` permission). For ADMIN, see Section 11.9 for department selection.
2. **Edit Metadata**: Manager can edit if their department has relationship with `permission_level IN ('CONTRIBUTE', 'MANAGE')`
3. **Delete**: Manager can soft-delete only if their department is the `is_primary_owner`
4. **View**: Manager can view documents shared with their department (any `permission_level`)
5. **Share**: Manager can share documents with other departments (creates new relationship entries)

**Permission Promotion Rules:**

A department can promote a relationship's permission level under these conditions:
- From `VIEW` to `CONTRIBUTE`: Requires `MANAGE` permission on the document
- From `CONTRIBUTE` to `MANAGE`: Requires being `is_primary_owner`
- Cannot demote a `MANAGE` relationship unless you are the primary owner

**Cross-Department Visibility for Managers:**

Managers can SEE documents shared with their department but the visibility is based on:
- Direct department match via `department_documents` table
- The document's `lifecycle_status` is `PUBLISHED` (not DRAFT/REVIEW)
- The user has at least `VIEW` permission level

**Relationship Deletion Behavior:**

- Deleting a `department_documents` relationship removes that department's access
- Does NOT delete the document itself
- Does NOT affect other department relationships
- Original document remains accessible to other linked departments
- All relationship deletions are logged in audit_logs

### 11.8 Critical Invariants

1. **Gateway is the only public entry point** — services are never exposed directly to clients.
2. **JWT context headers are authoritative** — downstream services trust `X-User-Id`, `X-Role`, `X-Department-Id`.
3. **No automatic role inheritance** — endpoints must explicitly list all allowed roles.
4. **DENY rules take precedence** — a DENY for a role/department/user overrides any VIEW grant.
5. **Chunks are never modified directly** — ACL updates go through the ingestion-service background worker only.
6. **Soft deletes are mandatory** — all queries must include `WHERE deleted_at IS NULL` unless explicitly fetching deleted records.
7. **Department relationships are immutable history** — `department_documents` rows are never hard-deleted; they are soft-deleted with `deleted_at` for audit purposes.

### 11.9 ADMIN Department Selection for Upload (Option B)

Unlike USER and MANAGER, ADMIN users have the flexibility to upload documents on behalf of any department. This section defines the design for this capability.

**Behavior**:
- ADMIN upload UI shows a **required department dropdown** listing all active departments
- If no department is selected → API returns `400 BAD_REQUEST` with code `MISSING_DEPARTMENT`
- The selected department becomes the `is_primary_owner` with `MANAGE` permission
- ADMIN's own department does NOT automatically get a relationship unless ADMIN selects it

**API Contract**:

```
POST /api/v1/documents/upload
Headers:
  Authorization: Bearer <admin-token>
  X-Department-Id: <admin's department from JWT>  # For audit logging only
Body (multipart/form-data):
  file: <binary>
  departmentId: <uuid>  # REQUIRED for ADMIN
  metadata: {
    title: string,
    description: string
  }
```

**Validation Rules**:

| Condition | Response |
|-----------|----------|
| USER/MANAGER sends `departmentId` in body | `400 BAD_REQUEST` - `DEPARTMENT_ID_NOT_ALLOWED` (auto-assigned) |
| ADMIN omits `departmentId` | `400 BAD_REQUEST` - `MISSING_DEPARTMENT` |
| ADMIN sends invalid `departmentId` | `404 NOT_FOUND` - `DEPARTMENT_NOT_FOUND` |
| ADMIN sends inactive department ID | `400 BAD_REQUEST` - `DEPARTMENT_INACTIVE` |
| Any user uploads to a department they don't belong to (non-ADMIN) | `403 FORBIDDEN` - `CROSS_DEPARTMENT_UPLOAD_DENIED` |

**Audit Logging**:

Every upload logs the action with both:
- The uploader's department (`X-Department-Id` from JWT) - "who is performing the action"
- The target department (`departmentId` from body) - "on whose behalf"

```json
{
  "action": "DOCUMENT_UPLOAD",
  "user_id": "admin-uuid",
  "user_role": "ADMIN",
  "resource_id": "new-document-uuid",
  "department_id": "admin-own-dept-uuid",      // uploader's department
  "target_department_id": "marketing-uuid",    // target department (may differ)
  "metadata": {
    "upload_type": "ON_BEHALF_OF",
    "file_name": "policy.pdf"
  }
}
```

**Cross-Department Upload by ADMIN - Use Cases**:

1. **Centralized IT uploads for HR**: IT admin uploads policy document → linked to HR department
2. **New department setup**: ADMIN bootstraps a new department's knowledge base
3. **Department transition**: When moving documents from one department to another during org restructure

**Restrictions**:
- ADMIN cannot upload to a department that is in the process of being deactivated
- ADMIN cannot upload to a department marked as `is_deleted = true`
- All cross-department uploads by ADMIN require a justification note (optional but recommended)

**Implementation Notes**:

```java
// knowledge-service - UploadService
public DocumentResponse upload(MultipartFile file, UploadRequest request, JwtContext jwt) {
    UUID targetDepartmentId;
    
    if (jwt.getRole().equals("ADMIN")) {
        if (request.getDepartmentId() == null) {
            throw new BadRequestException("MISSING_DEPARTMENT", 
                "ADMIN must specify target department");
        }
        targetDepartmentId = request.getDepartmentId();
        departmentService.validateActiveDepartment(targetDepartmentId);
    } else {
        // USER/MANAGER - auto-assign to user's department
        targetDepartmentId = jwt.getDepartmentId();
    }
    
    Document doc = createDocument(file);
    departmentRelationshipService.createRelationship(
        documentId = doc.getId(),
        departmentId = targetDepartmentId,
        permissionLevel = "MANAGE",
        isPrimaryOwner = true,
        grantedBy = jwt.getUserId()
    );
    
    // Audit log
    auditLogger.logUpload(jwt, doc, targetDepartmentId);
    
    return new DocumentResponse(doc);
}
```

---

## 12. API Gateway Cross-Cutting Concerns

**Owner**: `api-gateway` (port 3000)
**Schemas**: None (routing only)

### 12.1 Capabilities

| Concern | Design |
|---------|--------|
| JWT validation | Every authenticated request → verify token → check account not DEACTIVATED/REVOKED → inject identity headers |
| RBAC | Per-route `RolesGuard` checks role against allowed roles list |
| Rate limiting | In-memory sliding window: PUBLIC 20/min, USER 100/min, MANAGER 200/min, ADMIN 500/min |
| Circuit breaker | Per-downstream-service: opens after 5 failures, 30s timeout, 30s recovery (opossum) |
| Tracing | `X-Trace-ID` propagated through all services |
| Response normalization | All responses wrapped: `{ success, data, message, timestamp }` |
| Exception filter | Error codes mapped: 400→BAD_REQUEST, 401→UNAUTHORIZED, 403→FORBIDDEN, 404→NOT_FOUND, 429→RATE_LIMITED, 500→INTERNAL_ERROR |
| Health checks | `/health` (basic), `/health/live` (liveness), `/health/ready` (checks all downstream services), `/health/circuit-breakers` |
| Security headers | Helmet middleware + CORS + compression |

---

## 13. Scheduled Background Jobs

### 13.1 Feedback Service Jobs

| Job | Schedule | Design |
|-----|---------|--------|
| `CleanupScheduler` | 01:00 AM daily | Delete audit logs > 90 days, expired report exports, resolved unanswered questions > 180 days |
| `StatsAggregationScheduler` | Hourly at :05 + daily 00:10 | Aggregate `usage_stats` into `hourly_aggregates`, `daily_aggregates`, `department_daily_stats` |

### 13.2 Knowledge Service Jobs

| Job | Schedule | Design |
|-----|---------|--------|
| Staging cleanup | Every 10 minutes | Remove STAGING documents with `created_at` > 10 minutes ago and no confirmation |

### 13.3 Metadata Service Jobs

| Job | Schedule | Design |
|-----|---------|--------|
| Auto-archive | 01:00 AM daily | Set `lifecycle_status = ARCHIVED` for documents where `expires_at < NOW()` |

---

## 14. User Behavior & Violation Management

> **Status**: ✅ **IMPLEMENTED** - Full implementation as of June 27, 2026

**Owner**: `feedback-service` (port 8085) — or a new `moderation-service`
**Schema**: `analytics` (new table)

### 14.1 Why It Is Needed

The current system has no mechanism to track, escalate, or act on user misbehavior. Specifically:

- Layer 1 (toxic filter) blocks toxic queries but **does not log them** — admins cannot review who is repeatedly sending harmful content.
- Account status (`DEACTIVATED` / `REVOKED`) can only be changed **manually** by an admin — there is no automated escalation path.
- There is no UI or API for an admin to review a user's behavioral history before making a ban decision.
- There is no strike/warning system to give users a chance to correct behavior before a permanent ban.

### 14.2 Key Capabilities

| Capability | Design |
|-----------|--------|
| Violation logging | Every time Layer 1 blocks a toxic query, a violation record is created automatically. Includes: user_id, violation_type, evidence (the blocked query content), severity, timestamp |
| Admin exemption | **ADMIN users are exempt from violation escalation**. Admins may test the toxic filter with edge cases, so violations are logged but never trigger strikes, warnings, or account actions. |
| Violation types | `TOXIC_QUERY` (blocked by Layer 1), `ABUSE` (hateful/harassing content past Layer 1), `SPAM` (repeated duplicate queries), `POLICY_BREAK` (attempts to extract sensitive info) |
| Severity levels | `LOW` (first offense, borderline content), `MEDIUM` (repeat offense), `HIGH` (severe toxicity, repeated after warning) |
| Strike system | Each violation increments a `strike_count` on the user's profile. Configurable thresholds: 3 strikes → warn, 5 strikes → auto-deactivate pending admin review, 10 strikes → auto-revoke |
| Admin review queue | ADMIN sees a list of users with pending violations. Can review evidence, dismiss (false positive), warn, deactivate, or revoke. |
| User-facing warning | When a user hits the warn threshold, they see a banner on next login: "Your account has received a warning due to policy violations. Further violations may result in account suspension." |
| Appeal process | User can submit an appeal (free text) for admin review. Appeal status tracked: `PENDING`, `APPEALED`, `OVERRULED` |

### 14.3 Data Model

**New table** — `analytics.user_violations`:
```sql
CREATE TABLE analytics.user_violations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES core.users(id),
    violation_type  VARCHAR(50) NOT NULL,  -- TOXIC_QUERY, ABUSE, SPAM, POLICY_BREAK
    severity        VARCHAR(10) NOT NULL,   -- LOW, MEDIUM, HIGH
    evidence        TEXT,                  -- The blocked/abusive content
    source          VARCHAR(20) NOT NULL,   -- 'SYSTEM' (Layer 1 auto) or 'ADMIN' (manual report)
    reported_by     UUID,                  -- NULL for SYSTEM; admin UUID for manual reports
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, REVIEWED, ACTIONED
    action_taken    VARCHAR(20),           -- NULL, WARNED, DEACTIVATED, REVOKED
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     UUID,
    appeal_status   VARCHAR(20),           -- NULL, PENDING, APPROVED, REJECTED
    appeal_text     TEXT,
    appeal_reviewed_at TIMESTAMPTZ,
    appeal_reviewed_by UUID,
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_violations_user ON analytics.user_violations(user_id);
CREATE INDEX idx_violations_status ON analytics.user_violations(status) WHERE deleted_at IS NULL;
```

**New table** — `analytics.user_warnings`:
```sql
CREATE TABLE analytics.user_warnings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES core.users(id),
    violation_id  UUID REFERENCES analytics.user_violations(id),
    message       TEXT NOT NULL,
    expires_at    TIMESTAMPTZ,  -- Warning expires after N days (configurable)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at       TIMESTAMPTZ   -- NULL until user acknowledges
);
```

**Column added to** `core.users`:
```sql
ALTER TABLE core.users ADD COLUMN strike_count INT NOT NULL DEFAULT 0;
ALTER TABLE core.users ADD COLUMN last_violation_at TIMESTAMPTZ;
```

### 14.4 Violation Logging Flow (Planned)

```
User sends toxic query
        │
        ▼
Layer 1 Toxic Filter detects JAILBREAK/INJECTION
        │
        ▼
PipelineResult(status="BLOCKED") returned to user
        │
        ▼
[NEW] ViolationLogger.publish_violation(
        user_id=X,
        violation_type="TOXIC_QUERY",
        severity="LOW",           # based on label: JAILBREAK=HIGH, INJECTION=HIGH
        evidence=query_text,
        source="SYSTEM"
)
        │
        ▼
ViolationService: INSERT into user_violations (status=PENDING)
        │
        ▼
UserService: INCREMENT strike_count on core.users
        │
        ▼
[NEW] EscalationChecker.evaluate(user_id):
  strike_count == 3 → send warning (user_warnings), send notification to admin
  strike_count == 5 → auto-set user status = DEACTIVATED, notify admin
  strike_count == 10 → auto-set user status = REVOKED, notify admin
```

### 14.5 Admin Review Flow (Planned)

```
Admin → GET /api/v1/admin/violations?status=PENDING&page=1
      → Returns paginated list of users with violations, grouped by user

Admin → GET /api/v1/admin/violations/users/{userId}
      → Returns full violation history for a user + current strike count

Admin → POST /api/v1/admin/violations/{id}/review
        body: { action: "DISMISS" | "WARNED" | "DEACTIVATED" | "REVOKED" }
      → Updates violation record: status=REVIEWED, action_taken=X, reviewed_at, reviewed_by
      → If action is WARNED/DEACTIVATED/REVOKED:
          → UserService: set account status accordingly
          → Decrement strike_count (dismissed strikes for wrongfully actioned cases)
          → Notify user via email/in-app

Admin → POST /api/v1/admin/users/{userId}/reset-strikes
      → strike_count = 0, notify user that their record has been cleared
```

### 14.6 Appeal Flow (Planned)

```
User → POST /api/v1/me/violations/{id}/appeal
        body: { appeal_text: "..." }
      → Sets appeal_status = PENDING on the violation record

Admin → GET /api/v1/admin/appeals?status=PENDING
      → Reviews the violation + user's appeal text

Admin → POST /api/v1/admin/appeals/{id}/review
        body: { decision: "APPROVED" | "REJECTED" }
      → If APPROVED: clears the violation (soft-delete), decrements strike_count, reactivates account if needed
      → If REJECTED: keeps the violation, notifies user
```

### 14.7 Configuration (Planned)

```env
# Violation escalation thresholds
VIOLATION_STRIKE_WARN_THRESHOLD=3
VIOLATION_STRIKE_DEACTIVATE_THRESHOLD=5
VIOLATION_STRIKE_REVOKE_THRESHOLD=10

# Auto-action on new violation
VIOLATION_AUTO_WARN=true
VIOLATION_AUTO_DEACTIVATE=true
VIOLATION_AUTO_REVOKE=true

# Violation logging
LAYER1_LOG_VIOLATIONS=true
VIOLATION_LOG_EVIDENCE=true   # Store the blocked query text (consider PII implications)
```

### 14.8 RBAC (Planned)

| Operation | USER | MANAGER | ADMIN |
|-----------|:----:|:-------:|:-----:|
| View own violation history | ✅ (own only) | ✅ (own only) | ✅ |
| Submit appeal | ✅ (own violations) | ✅ | ✅ |
| View all users' violations | ❌ | ❌ | ✅ |
| Review / dismiss violations | ❌ | ❌ | ✅ |
| Manual deactivation / revocation | ❌ | ❌ | ✅ |
| Reset strike count | ❌ | ❌ | ✅ |
| Review appeals | ❌ | ❌ | ✅ |

### 14.9 Dependencies

- Layer 1 (`layer1_toxic_filter.py`) must emit a violation event when it blocks a query.
- `user-service` must expose endpoints or events for updating `strike_count` and account status.
- A notification service (email/in-app) must be integrated for warning and ban notifications.
- PII considerations: `evidence` (the blocked query text) contains user input — ensure GDPR compliance if stored long-term.

---

## 15. Cross-Feature Interactions

### Deduplication × RBAC

- A duplicate document inherits the ACLs of the original document it links to.
- Users who could access the original document can access the duplicate's metadata (but no new chunks were created).
- Admin can view duplicate information in the document detail page (banner: "This document is a duplicate of [name]").
- The duplicate document maintains its own department relationships (separate from the original). Each department's access is determined by its own relationship to the duplicate, not the original.

### Upload × Department Selection (ADMIN Option B)

- ADMIN users must explicitly select a target department during upload (Option B)
- USER/MANAGER uploads are auto-assigned to their own department
- Cross-department uploads by ADMIN are recorded in audit logs with both source (admin's dept) and target (selected dept)
- See Section 11.9 for full design and validation rules

### Deletion × Department Relationships

- Soft-deleting a document does NOT automatically remove department relationships
- A document can be soft-deleted but remain accessible to specific departments via relationships (admin override)
- Department-level removal (removing one department's access) is a separate operation from document deletion
- See Section 3.6 for cascade rules

### AI Q&A × Department Relationships

- AI search uses dual-strategy pattern: flattened arrays + junction table
- Newly created relationships are immediately effective (junction table) but chunk propagation is eventually consistent
- A user can ask questions about any document their department has VIEW+ permission on
- Duplicate documents return chunks from the ORIGINAL document, not from the duplicate (duplicates have no chunks)

### Query Safeguard × RBAC

- Layer 1 (toxic filter) applies to **all authenticated users** regardless of role.
- The toxic filter is applied **before** RBAC checks — a toxic query from an ADMIN is still blocked.
- Rate limits on model selection apply equally to all roles.

### RBAC × Document Access Rules

- RBAC role checks (ADMIN/MANAGER/USER) gate **what operations** a user can perform.
- Document access rules determine **which documents** a user can see.
- Both must pass for a document to appear in AI search results or document lists.
- ADMIN role bypasses document access rules for **CRUD operations** but still requires access rules for **AI search visibility**.

### Document Processing × Deduplication

- Deduplication runs **before** chunk creation. If a document is marked `DUPLICATE`, no chunks are created for it.
- The duplicate reference is stored in `document_versions`, linking to the original document.

### AI Q&A × Document Processing

- AI Q&A searches only chunks where `is_latest = true` and `dm.status = 'PUBLISHED'`.
- Documents in DRAFT or REVIEW status are not visible in AI search results.
- Expired documents (`dm.expires_at < NOW()`) are excluded from results.

### Analytics × All Features

- All significant operations (login, upload, delete, status change, export, role change) emit audit log entries.
- Usage stats are tracked per request for analytics aggregation.
- Feedback (LIKE/DISLIKE) records model used, token counts, and latency for cost/quality analytics.

### User Behavior Management × Query Safeguard

- Every toxic query blocked by Layer 1 generates a violation record with `source=SYSTEM`.
- Violations accumulate strike counts on the user's profile, triggering automated escalation.
- Admin can also file manual violation reports (`source=ADMIN`) for abusive content that passes Layer 1.

### User Behavior Management × Authentication

- Strike count is tracked on `core.users.strike_count`.
- Automated account status changes (`DEACTIVATED` / `REVOKED`) are enforced by `auth-service` — revoked users cannot obtain new tokens.
- Login attempt logs (`login_history`) provide supplementary evidence of brute-force or credential-stuffing attacks alongside violation-based bans.
