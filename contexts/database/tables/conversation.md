---
title: Conversation Schema Tables
description: Database tables for the conversation schema (ai-qa-service ownership)
schema: conversation
owner: ai-qa-service
---

# Conversation Schema Tables

**Owner Service**: `ai-qa-service`  
**Purpose**: AI chat history, messages, citations, and unanswered questions tracking

---

## Table of Contents

- [conversation.conversations](#conversations)
- [conversation.messages](#messages)
- [conversation.unanswered_questions](#unanswered-questions)

---

## conversations

**Description**: Chat conversation sessions. Each time a user starts a new chat topic, a conversation record is created.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Conversation unique identifier |
| `user_id` | UUID | NOT NULL, FOREIGN KEY → core.users(id) | Conversation owner |
| `title` | VARCHAR(500) | NULLABLE | Auto-generated or user-provided title (first query or summary) |
| `message_count` | INT | DEFAULT 0 | Number of messages in conversation (cached) |
| `last_message_at` | TIMESTAMP | NULLABLE | Timestamp of most recent message |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Conversation creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update (when new message added) |
| `deleted_at` | TIMESTAMP | NULLABLE | Soft delete timestamp |

### Indexes

- `idx_conversations_user_id` on `user_id`
- `idx_conversations_created_at` on `created_at` DESC
- `idx_conversations_deleted_at` on `deleted_at` (for cleanup of soft-deleted)
- Composite: `idx_conversations_user_active` on `(user_id, deleted_at)` WHERE `deleted_at IS NULL`

### Notes

- **Soft Delete**: When user deletes conversation, set `deleted_at = NOW()`. Hide from UI but keep for audit/recovery for 30 days.
- **Title Generation**:
  - First message content truncated to 50 chars
  - Or use LLM: "Generate a short title for this conversation based on: {first_query}"
- **Message Count Denormalization**: Update `message_count` via trigger on `messages` insert/delete to avoid COUNT(*) queries.
- **Archival**: After 1 year, move old conversations to `conversations_archive` table (partition by year) or export to cold storage.

---

## messages

**Description**: Individual chat messages within a conversation. Supports both user and AI messages.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Message unique identifier |
| `conversation_id` | UUID | NOT NULL, FOREIGN KEY → conversation.conversations(id) ON DELETE CASCADE | Parent conversation |
| `role` | ENUM('USER','ASSISTANT') | NOT NULL | 'USER' for human, 'ASSISTANT' for AI |
| `content` | TEXT | NOT NULL | Message text content |
| `sources` | JSONB | NULLABLE | Array of cited sources: `[{document_id, title, section, page, score}]` |
| `model_used` | VARCHAR(100) | NULLABLE | LLM model name (e.g., "qwen/qwen-2.5-7b-instruct") |
| `tokens_prompt` | INT | NULLABLE | Number of tokens in prompt sent to LLM |
| `tokens_completion` | INT | NULLABLE | Number of tokens in LLM response |
| `tokens_total` | INT | NULLABLE | Total tokens (prompt + completion) |
| `latency_ms` | INT | NULLABLE | End-to-end response time (ms) |
| `confidence` | ENUM('HIGH','MEDIUM','LOW') | NULLABLE | AI confidence based on retrieval scores |
| `has_sources` | BOOLEAN | DEFAULT false | Whether response included citations |
| `is_streaming` | BOOLEAN | DEFAULT false | True while assistant is actively typing |
| `streaming_completed` | BOOLEAN | DEFAULT true | True when stream finishes or for non-streamed |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Message timestamp |

### Indexes

- `idx_messages_conversation_id` on `conversation_id`
- `idx_messages_created_at` on `created_at` DESC
- `idx_messages_role` on `role`

### Constraints

```sql
-- If role = 'ASSISTANT', model_used should be present
ALTER TABLE conversation.messages
ADD CONSTRAINT assistant_has_model
CHECK (role != 'ASSISTANT' OR model_used IS NOT NULL);

ALTER TABLE conversation.messages
ADD CONSTRAINT chk_tokens
CHECK (tokens_total IS NULL OR tokens_total >= 0);
```

### Notes

- **Source Tracking**: `sources` JSONB array stores which document chunks were cited:
  ```json
  [
    {
      "chunk_id": "chunk-uuid",
      "document_id": "doc-uuid",
      "title": "Chính Sách Nhân Sự 2024",
      "section_title": "Điều 15: Nghỉ phép",
      "page_number": 12,
      "similarity_score": 0.92,
      "reranker_score": 0.95
    }
  ]
  ```
- **Token Counting**: Use `tiktoken` (cl100k_base) or model-specific tokenizer to count tokens for billing/analytics.
- **Confidence Scoring**: Set based on:
  - `HIGH`: Top chunk similarity > 0.8, reranker > 0.8
  - `MEDIUM`: Top chunk similarity 0.6-0.8
  - `LOW`: Top chunk similarity < 0.6 or no sources (`has_sources = false`)
- **Streaming Responses**: For SSE streams, create message record after streaming completes with final `content`.
- **Soft-Delete Cascade**: A DB trigger should monitor `conversations.deleted_at`. When a conversation is soft-deleted, the trigger must set `deleted_at = NOW()` for all its messages. This allows querying `messages` with `WHERE deleted_at IS NULL` without joining the `conversations` table.

---

## unanswered_questions

**Description**: Tracks questions that AI could not answer adequately. Used for knowledge gap analysis and content improvement.

**Primary Key**: `id` (UUID)

### Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, NOT NULL | Record ID |
| `user_id` | UUID | NOT NULL | User who asked the question |
| `message_id` | UUID | NULLABLE, FOREIGN KEY → conversation.messages(id) ON DELETE SET NULL | Original AI message that failed |
| `conversation_id` | UUID | NULLABLE, FOREIGN KEY → conversation.conversations(id) ON DELETE SET NULL | Conversation context |
| `question` | TEXT | NOT NULL | Original user question |
| `question_normalized` | TEXT | NULLABLE | Lowercase, no diacritics for deduplication |
| `search_query` | TEXT | NULLABLE | Query actually sent to vector search |
| `attempted_context` | JSONB | DEFAULT '{}' | Snapshot of the chunks AI attempted to use |
| `top_similarity_score` | DECIMAL(5,4) | NULLABLE | Highest similarity score found |
| `user_department_id` | UUID | NULLABLE | Extracted from user profile at time of asking |
| `user_role` | VARCHAR(20) | NULLABLE | E.g. USER, MANAGER for context |
| `resolved` | BOOLEAN | DEFAULT false | Whether admins have addressed this gap |
| `resolved_by` | UUID | NULLABLE, FOREIGN KEY → core.users(id) | Admin who marked resolved |
| `resolved_at` | TIMESTAMP | NULLABLE | Resolution timestamp |
| `resolution_notes` | TEXT | NULLABLE | Admin notes |
| `related_document_id` | UUID | NULLABLE | The document the admin uploaded to resolve this |
| `category` | VARCHAR(100) | NULLABLE | Thematically grouped category of question |
| `priority` | VARCHAR(20) | DEFAULT 'NORMAL' | Priority: LOW, NORMAL, HIGH, CRITICAL |
| `created_at` | TIMESTAMP | DEFAULT NOW() | When question was asked |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update |

### Indexes

- `idx_unanswered_questions_resolved` on `resolved` (for filtering unresolved)
- `idx_unanswered_questions_priority` on `priority`
- `idx_unanswered_questions_created_at` on `created_at` DESC
- `idx_unanswered_question_normalized` on `question_normalized` (for deduplication)
- `idx_unanswered_user_id` on `user_id`

### Notes

- **Population Logic**: AI service sets `resolved = false` automatically when:
  - Top similarity score < threshold (e.g., 0.4)
  - LLM indicates "I don't have enough information" (via structured output)
- **Resolution Workflow**:
  1. Admin reviews unanswered questions in dashboard
  2. Admin uploads new document or updates existing to cover gap
  3. Admin marks question as resolved, adds notes
  4. System could optionally notify original user (future feature)
- **Deduplication**: Normalize questions (lowercase, remove diacritics, strip punctuation) to cluster similar questions. Show count of "asked 5 times" for high-priority gaps.
- **Priority Algorithm** (automatic scoring):
  - `HIGH`: Score < 0.2, asked by > 3 unique users, or from MANAGER/ADMIN
  - `MEDIUM`: Score 0.2-0.4, or repeated by same user
  - `LOW`: Score 0.4-0.5, single occurrence
- **Dangling Reference Prevention**: `message_id` and `conversation_id` use `ON DELETE SET NULL`. If the original conversation is permanently archived/hard-deleted after 1 year, the unanswered question record remains intact since the required context (`question` and `search_query`) is already denormalized.

---

## Enums

### message_role

```sql
CREATE TYPE message_role AS ENUM ('USER', 'ASSISTANT');
```

### confidence_level

```sql
CREATE TYPE confidence_level AS ENUM ('HIGH', 'MEDIUM', 'LOW');
```

### priority_level

```sql
CREATE TYPE priority_level AS ENUM ('LOW', 'MEDIUM', 'HIGH');
```

---

## Common Queries

### Get User's Active Conversations

```sql
SELECT c.id, c.title, c.message_count, c.last_message_at, COUNT(m.id) as total_messages
FROM conversation.conversations c
LEFT JOIN conversation.messages m ON m.conversation_id = c.id
WHERE c.user_id = :user_id
  AND c.deleted_at IS NULL
GROUP BY c.id
ORDER BY c.last_message_at DESC
LIMIT :limit OFFSET :offset;
```

### Get Conversation with Messages (Paginated)

```sql
SELECT * FROM conversation.conversations
WHERE id = :conversation_id AND user_id = :user_id AND deleted_at IS NULL;

SELECT * FROM conversation.messages
WHERE conversation_id = :conversation_id
ORDER BY created_at ASC
LIMIT :limit OFFSET :offset;
```

### Unanswered Questions Dashboard

```sql
SELECT uq.*, u.full_name, u.email
FROM conversation.unanswered_questions uq
JOIN core.users u ON u.id = uq.user_id
WHERE uq.resolved = false
ORDER BY
  CASE uq.priority
    WHEN 'HIGH' THEN 1
    WHEN 'MEDIUM' THEN 2
    WHEN 'LOW' THEN 3
  END,
  uq.created_at DESC
LIMIT 100;
```

### Archive Old Conversations (Monthly Job)

```sql
-- Move conversations older than 1 year to archive table
INSERT INTO conversation.conversations_archive
SELECT * FROM conversation.conversations
WHERE created_at < NOW() - INTERVAL '1 year'
  AND deleted_at IS NOT NULL;  -- Only archive soft-deleted

DELETE FROM conversation.conversations
WHERE created_at < NOW() - INTERVAL '1 year'
  AND deleted_at IS NOT NULL;
```

---

## Data Retention Policy

| Table | Retention | Cleanup Strategy |
|-------|-----------|------------------|
| `conversations` | Keep indefinitely (unless user deletes) | Soft delete → archive after 1 year |
| `messages` | Same as parent conversation | Cascade delete on conversation hard delete |
| `unanswered_questions` | Keep resolved for 2 years, then delete | Cron: `DELETE FROM ... WHERE resolved = true AND resolved_at < NOW() - INTERVAL '2 years'` |

---

## Related References

- **AI Architecture**: `contexts/architecture/ai-service-architecture.md` - conversation management component
- **Service Ownership**: `contexts/service-boundaries/responsibilities.md` - ai-qa-service owns these tables
- **API Contracts**: `contexts/service-boundaries/api-contracts.md` - chat endpoints
- **Event Contracts**: `contexts/service-boundaries/events.md` - `unanswered.question` event

---

**Last Updated**: 2026-04-08
**Documentation Version**: 1.0
