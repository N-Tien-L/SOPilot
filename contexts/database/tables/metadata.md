---
title: Metadata Schema Tables
description: Database tables for the metadata schema (metadata-service ownership)
schema: metadata
owner: metadata-service
---

# Metadata Schema Tables

**Owner Service**: `metadata-service`  
**Purpose**: Document metadata management, categorization, tagging, and access control rules

---

## Table of Contents

- [metadata.categories](#categories)
- [metadata.tags](#tags)
- [metadata.document_metadata](#document-metadata)
- [metadata.document_tags](#document-tags)
- [metadata.document_access_rules](#document-access-rules)

---

## categories

**Description**: Document category hierarchy for organizing documents

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Category unique identifier |
| `name` | VARCHAR(255) | NOT NULL | Category name (e.g., "HR Policies") |
| `slug` | VARCHAR(100) | UNIQUE, NOT NULL | URL-friendly slug (e.g., "hr-policies") |
| `description` | TEXT | NULLABLE | Category description |
| `parent_id` | UUID | NULLABLE, FOREIGN KEY → metadata.categories(id) | Parent category for hierarchy |
| `icon` | VARCHAR(50) | NULLABLE | Icon name (e.g., "FileText", "Folder") |
| `display_order` | INT | DEFAULT 0 | Sort order for UI |
| `is_active` | BOOLEAN | DEFAULT true | Whether category is active |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

### Indexes

- `idx_categories_parent_id` on `parent_id`
- `idx_categories_slug` on `slug`
- `idx_categories_display_order` on `display_order`

### Notes

- Hierarchical categories allow multi-level organization (Category → Subcategory → Sub-subcategory)
- Used for document navigation and filtering in UI
- Active categories only shown in dropdowns (filter by `is_active = true`)
- **GitLab Mapping**: Matches top-level directories or sections (e.g., "Engineering", "Marketing"). The nested structure `parent_id` perfectly models the folder depth of the handbook repository.

---

## tags

**Description**: Flexible document tags for ad-hoc categorization

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Tag unique identifier |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL | Tag name (e.g., "confidential", "template") |
| `slug` | VARCHAR(100) | UNIQUE, NOT NULL | URL slug |
| `color` | VARCHAR(7) | DEFAULT '#6B7280' | Hex color code for UI display |
| `usage_count` | INT | DEFAULT 0 | Number of documents using this tag (denormalized) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### Indexes

- `idx_tags_name` on `name`
- `idx_tags_usage_count` on `usage_count` DESC

### Notes

- **Usage Count Update**: Trigger `AFTER INSERT/DELETE` on `document_tags` to increment/decrement `usage_count`
- **Color Management**: Admin-configurable colors for visual organization in UI
- Popular tags (high `usage_count`) shown in tag cloud

---

## document_metadata

**Description**: Core document metadata - the "business card" of each document

**Primary Key**: `id` (UUID)  
**Foreign Key**: `document_id` → `knowledge.documents(id)` (one-to-one)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Metadata record ID |
| `document_id` | UUID | UNIQUE, NOT NULL, FOREIGN KEY → knowledge.documents(id) | Linked document |
| `title` | VARCHAR(500) | NOT NULL | Document title |
| `description` | TEXT | NULLABLE | Document description/summary |
| `document_type` | VARCHAR(100) | NOT NULL | Type (e.g., "HR_POLICY", "CONTRACT", "GUIDELINE") |
| `category_id` | UUID | NULLABLE, FOREIGN KEY → metadata.categories(id) | Primary category |
| `department_id` | UUID | NOT NULL, FOREIGN KEY → core.departments(id) | Owning department |
| `access_level` | ENUM('PUBLIC','DEPARTMENT_ONLY') | DEFAULT 'PUBLIC' | Default access level |
| `effective_date` | DATE | NOT NULL | Date policy becomes effective |
| `expiry_date` | DATE | NULLABLE | Date policy expires (NULL = indefinite) |
| `status` | ENUM('DRAFT','PUBLISHED','ARCHIVED') | DEFAULT 'DRAFT' | Publication status |
| `current_version` | INT | DEFAULT 1 | Current version number (syncs with knowledge.document_versions) |
| `created_by` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Who created metadata |
| `updated_by` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | Who last updated |
| `published_by` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | Who published (if status = PUBLISHED) |
| `published_at` | TIMESTAMP | NULLABLE | Publication timestamp |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |
| `deleted_at` | TIMESTAMP | NULLABLE | Soft delete timestamp |

### Indexes

- `idx_document_metadata_document_id` on `document_id` (unique)
- `idx_document_metadata_status` on `status`
- `idx_document_metadata_department_id` on `department_id`
- `idx_document_metadata_effective_date` on `effective_date`
- `idx_document_metadata_expiry_date` on `expiry_date`
- Composite: `idx_doc_meta_deleted_status` on `(deleted_at, status)` for queries like `WHERE deleted_at IS NULL AND status = 'PUBLISHED'`

### Notes

- **One-to-One with documents**: Every row in `knowledge.documents` must have exactly one corresponding `document_metadata` row (enforced by application logic)
- **Status Workflow**:
  - `DRAFT` → Only creator and admins can edit, not searchable
  - `PUBLISHED` → Visible to all users with permission, searchable
  - `ARCHIVED` → Hidden from search, kept for audit trail
- **Access Level**:
  - `PUBLIC`: All authenticated users can access (subject to additional rules)
  - `DEPARTMENT_ONLY`: Only users in `department_id` can access (unless specific override rules exist)
- **Expiry Auto-Update**: Scheduled job (daily) sets status to `ARCHIVED` if `expiry_date < CURRENT_DATE` and not NULL. **CRITICAL:** When archiving, this job MUST publish a `document.status.changed` event so AI/RAG services can exclude its chunks from future searches.
- **GitLab Mapping**: In the context of the GitLab Handbook, one `document_metadata` record represents one markdown file (`.md`) from the repository. The chunking of that document handles the internal sections (`<h2>`, `<h3>`).

---

## document_tags

**Description**: Many-to-many relationship between documents and tags

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Relationship ID |
| `document_metadata_id` | UUID | NOT NULL, FOREIGN KEY → metadata.document_metadata(id) ON DELETE CASCADE | Document |
| `tag_id` | UUID | NOT NULL, FOREIGN KEY → metadata.tags(id) ON DELETE CASCADE | Tag |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### Indexes

- Unique: `UNIQUE(document_metadata_id, tag_id)` prevents duplicate tag assignments
- `idx_document_tags_document_id` on `document_metadata_id`
- `idx_document_tags_tag_id` on `tag_id`

### Notes

- **Cascade Delete**: When document is soft-deleted, tags remain; when hard-deleted, relationship rows cascade
- **Tag Usage Counter**: Trigger to update `metadata.tags.usage_count` on INSERT/DELETE
- **Tag Limit**: Application may enforce max X tags per document (e.g., 10)

---

## document_access_rules

**Description**: Fine-grained access control rules - **SOURCE OF TRUTH** for document permissions

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Rule unique identifier |
| `document_metadata_id` | UUID | NOT NULL, FOREIGN KEY → metadata.document_metadata(id) ON DELETE CASCADE | Document this rule applies to |
| `target_type` | ENUM('ROLE','DEPARTMENT','USER') | NOT NULL | Type of access target |
| `target_role` | ENUM('USER','MANAGER','ADMIN') | NULLABLE (required if target_type = 'ROLE') | Role if target_type is ROLE |
| `target_department_id` | UUID | NULLABLE (required if target_type = 'DEPARTMENT') | Department FK if target_type is DEPARTMENT |
| `target_user_id` | UUID | NULLABLE (required if target_type = 'USER') | User FK if target_type is USER |
| `permission` | VARCHAR(255) | DEFAULT 'VIEW' | Permission granted (VIEW, DENY) |
| `created_by` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | Admin who created rule |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

### Indexes

- `idx_doc_access_rules_doc_meta_id` on `document_metadata_id`
- `idx_doc_access_rules_target_user` on `target_user_id`
- `idx_doc_access_rules_target_dept` on `target_department_id`
- Composite: `idx_doc_access_rules_lookup` on `(document_metadata_id, permission, target_type)` for efficient access checks

### Check Constraints

```sql
-- Ensure correct target field is set based on target_type
ALTER TABLE metadata.document_access_rules ADD CONSTRAINT chk_target_consistency
CHECK ( ... );

-- Ensure correct permissions
ALTER TABLE metadata.document_access_rules ADD CONSTRAINT document_access_rules_permission_check
CHECK (permission IN ('VIEW', 'DENY'));
```

### Notes

- **Permission Resolution Priority** (when checking access):
  1. `DENY` rules for specific user/role/department override all
  2. `VIEW` rules for specific user/role/department grant access (OR algorithm — any matching VIEW grants access)
  3. `metadata.document_metadata.access_level` fallback:
     - `PUBLIC` → all authenticated users
     - `DEPARTMENT_ONLY` → only users in `department_id`
     - `RESTRICTED` → only ADMIN (default on new upload)
  4. Default: DENY

- **Default on Upload**: New documents start with no access rules and `accessLevel = RESTRICTED`. Only ADMIN can access until rules are added.

- **Flattening**: During ingestion, `ingestion-service` reads these rules and flattens them into `knowledge.chunks.allowed_roles`, `allowed_departments`, `allowed_users` arrays for fast AI search. See `contexts/authorization/dual-strategy.md`.

- **Rule Pruning**: When a rule is deleted, corresponding entries in flattened chunks must be updated (event-driven sync via `document.permissions.changed` event)

- **Example Rules**:
  ```sql
  -- Grant VIEW to all authenticated users (effective wildcard)
  INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_role, permission)
  VALUES (?, 'ROLE', 'USER', 'VIEW');  -- applies to USER, MANAGER, ADMIN roles
  
  -- Grant VIEW to specific department
  INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_department_id, permission)
  VALUES (?, 'DEPARTMENT', 'dept-uuid', 'VIEW');
  
  -- Explicitly DENY a specific user
  INSERT INTO metadata.document_access_rules (document_metadata_id, target_type, target_user_id, permission)
  VALUES (?, 'USER', 'user-uuid', 'DENY');
  ```

---

## Enum Types

### document_status

```sql
CREATE TYPE document_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED');
```

### access_level

```sql
CREATE TYPE access_level AS ENUM ('PUBLIC', 'DEPARTMENT_ONLY', 'RESTRICTED');
```

### rule_target_type

```sql
CREATE TYPE rule_target_type AS ENUM ('ROLE', 'DEPARTMENT', 'USER');
```

### rule_permission

```sql
CREATE TYPE rule_permission AS ENUM ('VIEW', 'EDIT', 'MANAGE', 'DENY');
```

---

## Related References

- **Authorization Pattern**: `contexts/authorization/dual-strategy.md` - how access_rules are flattened
- **RBAC**: `contexts/authorization/rbac-matrix.md` - role definitions
- **Service Ownership**: `contexts/service-boundaries/responsibilities.md` - metadata-service responsibilities
- **Event Contracts**: `contexts/service-boundaries/events.md` - permission change events

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
