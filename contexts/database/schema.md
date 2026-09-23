# Source: contexts/database_schema.md

# SYSTEM INSTRUCTION: Database Schema & Architecture

<purpose>
Provide system context on the PostgreSQL database architecture, schema boundaries, and strict data fetching rules for the Poliwise project.
</purpose>

<source_of_truth>
WARNING: For FULL column definitions, exact data types, constraints, and relationships, ALWAYS use your file reading tools to read `docs/database.md`. DO NOT guess the schema.
</source_of_truth>

<architecture>
The system uses a SINGLE PostgreSQL database separated into 5 logical schemas to maintain domain boundaries.
</architecture>

<table_map>
Here is the high-level overview of available tables to guide your queries.

1. **Schema: `core` (User & Auth Management)**
   - `core.departments`: Company department hierarchy.
   - `core.users`: User accounts, login status, roles (USER, MANAGER, ADMIN).
   - `core.user_profiles`: Detailed user biological and employee info.
   - `core.refresh_tokens`: JWT refresh token tracking.
   - `core.login_history`: Audit log for user logins.

2. **Schema: `metadata` (Document Info & Permissions)**
   - `metadata.categories`: Document categories hierarchy.
   - `metadata.tags`: Tags attached to documents.
   - `metadata.document_metadata`: Core document info (title, description, access_level, status).
   - `metadata.document_tags`: Many-to-Many mapping for documents and tags.
   - `metadata.document_access_rules`: SOURCE OF TRUTH for document permissions (VIEW/DENY for Roles/Depts/Users).

3. **Schema: `knowledge` (RAG & Vector Search)**
   - `knowledge.documents`: Physical file tracking and extraction status.
   - `knowledge.document_versions`: Version history of document files.
   - `knowledge.chunks`: Chunked text and vector embeddings for AI semantic search.
   - `knowledge.processing_jobs`: Tracking ETL extraction/chunking status.

4. **Schema: `conversation` (AI Chat System)**
   - Includes chat history, messages, and citations (Refer to database.md if details are needed).

5. **Schema: `analytics` (System Tracking)**
   - Includes feedback, usage statistics, and unanswered AI questions.
</table_map>

<critical_rules>
- **Soft Deletions**: ALWAYS append `WHERE deleted_at IS NULL` when querying `metadata`, `core`, or `knowledge` tables if the column exists.
- **Vector Search**: ALWAYS use the `<=>` operator (cosine similarity) for `pgvector` operations on `knowledge.chunks.embedding_vector`.
- **Knowledge Schema Modification**: Do NOT modify `knowledge.chunks` manually in feature code. It is strictly managed by the document ingestion pipeline.
</critical_rules>

<schema_details>
## Table Special Focus: `knowledge.chunks`
This is the most critical table for AI operations. It uses a "Read-Optimized" strategy. It contains "flattened" access controls to optimize vector search speed without joining `metadata` tables during AI queries.
- `allowed_roles TEXT[]`: Derived from metadata access rules.
- `allowed_departments UUID[]`: Derived from metadata access rules.
- `allowed_users UUID[]`: Array of explicitly allowed user IDs.
- `access_level VARCHAR`: 'PUBLIC' or 'DEPARTMENT_ONLY'.
(Read `contexts/authorization_strategy.md` for understanding how to use these in queries).
</schema_details>

# Source: context/domain/database-schema.md

# Database Schema & Critical Query Rules

## Purpose
Provides essential database schema information and strict query rules that AI agents MUST follow when working with the Poliwise database. This is a condensed reference - for full column definitions, see `docs/database.md`.

## When to Use
Always consult this file before writing any SQL queries or making database schema changes.

## Database Architecture
The system uses a SINGLE PostgreSQL database separated into 5 logical schemas to maintain domain boundaries:
- `core`: auth-service (users, roles, permissions)
- `public` (default): user-service (user profiles, departments)
- `knowledge`: knowledge-service (documents, chunks, embeddings)
- `metadata`: metadata-service (categories, tags, access rules)
- `conversation`: ai-qa-service (chat history, messages)
- `analytics`: feedback-service (feedback, usage logs)

## Critical Query Rules (ALWAYS FOLLOW)

### 1. Soft Deletions
Always append `WHERE deleted_at IS NULL` when querying these tables if the column exists:
- `metadata.*`
- `core.*`
- `knowledge.*`

### 2. Vector Search
Always use the `<=>` operator (cosine similarity) for `pgvector` operations:
```sql
SELECT * FROM knowledge.chunks 
WHERE embedding_vector <=> :query_embedding < :threshold
ORDER BY embedding_vector <=> :query_embedding
LIMIT :limit;
```

### 3. Knowledge.chunks Modification
**NEVER** modify `knowledge.chunks` directly in feature code. This table is managed exclusively by the ingestion-service.

## Knowledge.chunks - Read-Optimized ACL Fields
This table uses flattened access controls for fast AI vector search:
- `allowed_roles TEXT[]`: Derived from metadata access rules
- `allowed_departments UUID[]`: Derived from metadata access rules  
- `allowed_users UUID[]`: Explicitly allowed user IDs
- `access_level VARCHAR`: 'PUBLIC' or 'DEPARTMENT_ONLY'

**When querying knowledge.chunks for AI retrieval, ALWAYS apply this filter**:
```sql
AND (
  access_level = 'PUBLIC' 
  OR allowed_users @> ARRAY[:user_id]::UUID[] 
  OR allowed_departments @> ARRAY[:department_id]::UUID[] 
  OR allowed_roles @> ARRAY[:user_role]::TEXT[]
)
```

## Table Reference by Schema

### core (auth-service)
- `core.departments`: Company department hierarchy
- `core.users`: User accounts, login status, roles
- `core.user_profiles`: Detailed user info
- `core.refresh_tokens`: JWT refresh token tracking
- `core.login_history`: Audit log for user logins

### public (user-service) 
*(No tables explicitly listed - inherits from core patterns)*

### knowledge (knowledge-service)
- `knowledge.documents`: Physical file tracking and extraction status
- `knowledge.document_versions`: Version history of document files
- `knowledge.chunks`: Chunked text and vector embeddings for AI search
- `knowledge.processing_jobs`: Tracking ETL extraction/chunking status

### conversation (ai-qa-service)
- Includes chat history, messages, and citations

### analytics (feedback-service)
- Includes feedback, usage statistics, and unanswered AI questions

## Schema Ownership Verification
Before implementing database changes, verify service ownership in:
- `domain/service-responsibilities.md`
- `docs/database.md` (full schema)

# Source: docs/database.md

*(Note: The full detailed database schema documentation (with exact column definitions) has been extracted to docs/database.md. Please refer to that file for complete constraints and types.)*
