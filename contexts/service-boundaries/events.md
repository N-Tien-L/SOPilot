---
title: RabbitMQ Event Contracts
description: Complete catalog of RabbitMQ events, payload schemas, and queue configurations
type: service-boundaries
version: 1.0
---

# RabbitMQ Event Contracts

## Purpose

Defines all asynchronous events in the Poliwise system, their payload schemas, routing keys, and which services publish/consume them. This is the **single source of truth** for event-driven communication.

## When to Use

- Implementing new cross-service features with async communication
- Debugging event flows
- Adding new event consumers
- Designing new services

---

## Event Infrastructure

### Exchange Configuration

- **Exchange Name**: `poliwise.events`
- **Type**: Topic Exchange (`amq.topic`)
- **Durable**: true
- **Auto-delete**: false

All services connect using:
```env
RABBITMQ_URL=amqp://poliwise:poliwise_secure_password@rabbitmq:5672
RABBITMQ_EXCHANGE=poliwise.events
```

### Message Format Standard

All events must follow this envelope:

```json
{
  "event_type": "document.uploaded",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0",
  "payload": {
    // Event-specific fields
  }
}
```

**Field Requirements**:
- `event_type`: dot-separated noun.verb format (e.g., `document.uploaded`, `user.status.changed`)
- `timestamp`: ISO-8601 UTC
- `version`: schema version (increment on breaking changes)
- `payload`: typed JSON object (defined per event)

---

## Event Catalog

### 1. user.status.changed

**Description**: Notifies that a user's account status changed (ACTIVE → DEACTIVATED, etc.)

**Publisher**: `user-service`  
**Consumers**: `ai-qa-service`, `auth-service`, `feedback-service`  
**Routing Key**: `user.status.changed`

**Payload Schema**:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "old_status": "ACTIVE",
  "new_status": "DEACTIVATED",
  "changed_by": "admin-user-id",
  "reason": "Violation of policy"
}
```

**Consumer Actions**:
- `ai-qa-service`: Invalidate user-specific caches, mark conversations as archived
- `auth-service`: If status becomes DEACTIVATED/REVOKED, add to token blacklist
- `feedback-service`: Anonymize or delete user's feedback data (GDPR)

**Idempotency**: Safe to process multiple times (status transition is idempotent).

---

### 2. user.revoked

**Description**: High-privilege event that a user account has been revoked (extreme case: security breach, termination).

**Publisher**: `user-service`  
**Consumers**: **All services** (broadcast)  
**Routing Key**: `user.revoked`

**Payload Schema**:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "revoked_at": "2024-01-15T10:30:00Z",
  "reason": "Security breach",
  "revoked_by": "super-admin-id"
}
```

**Consumer Actions**:
- `auth-service`: Add user token to permanent blacklist, prevent re-login
- `knowledge-service`: Remove user from `allowed_users` arrays (requires re-chunking or separate ACL check)
- `metadata-service`: Remove user from any explicit access rules where they're the only grantee
- `feedback-service`: Anonymize all user-submitted data (keep aggregates)
- `ai-qa-service`: Delete user's conversations (soft delete first, then hard delete after backup period)

**Note**: This is a destructive operation. Ensure audit log is written before revocation.

---

### 3. document.uploaded

**Publisher**: `ingestion-service`  
**Consumers**: `ai-qa-service`, `feedback-service`, `knowledge-service`  
**Routing Key**: `document.uploaded`

**Payload Schema**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_version_id": "660e8400-e29b-41d4-a716-446655440001",
  "title": "HR Policy 2024",
  "department_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "PUBLISHED",
  "uploaded_by": "admin-user-id",
  "uploaded_at": "2024-01-15T10:30:00Z"
}
```

**Consumer Actions**:
- `ai-qa-service`: Index document in search cache, signal that document is ready for queries
- `feedback-service`: Create document popularity tracking entry
- `knowledge-service`: Update `knowledge.documents.status` from PROCESSING → PUBLISHED

**Idempotency**: Document may already be indexed if event redelivered. Consumer should handle gracefully:
```python
try:
    search_index.index_document(event.document_id)
except AlreadyIndexedError:
    pass  # Idempotent - document already indexed
```

---

### 4. document.deleted

**Publisher**: `knowledge-service`  
**Consumers**: `ingestion-service`, `ai-qa-service`, `feedback-service`  
**Routing Key**: `document.deleted`

**Payload Schema**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "reason": "Policy expired",
  "deleted_by": "admin-user-id",
  "deleted_at": "2024-01-15T10:30:00Z"
}
```

**Consumer Actions**:
- `ingestion-service`: Soft-delete chunks (`UPDATE knowledge.chunks SET is_latest = false WHERE document_id = X`)
- `ai-qa-service`: Remove document from search index (if separate from Postgres), exclude from future queries
- `feedback-service`: Anonymize document reference in usage stats, keep aggregates

---

### 5. ingestion.requested

**Publisher**: `knowledge-service`  
**Consumers**: `ingestion-service` (only)  
**Routing Key**: `ingestion.requested`  
**Queue**: `ingestion.requests` (durable)

**Payload Schema**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_version_id": "660e8400-e29b-41d4-a716-446655440001",
  "file_key": "documents/2024/01/550e8400.pdf",
  "bucket_name": "poliwise-documents",
  "job_id": "770e8400-e29b-41d4-a716-446655440002",
  "metadata": {
    "allowed_roles": ["USER", "MANAGER", "ADMIN"],
    "allowed_departments": ["dept-uuid-1", "dept-uuid-2"],
    "allowed_users": ["user-uuid-1"],
    "access_level": "PUBLIC",
    "title": "HR Policy 2024",
    "department_id": "dept-uuid-1",
    "document_metadata": {
      "category_id": "cat-uuid",
      "effective_date": "2024-01-01",
      "expiry_date": "2025-01-01"
    }
  }
}
```

**Consumer Processing** (`ingestion-service`):
1. Download file from MinIO using `file_key` and `bucket_name`
2. Extract text (PyMuPDF, python-docx, etc.)
3. Standardize (Vietnamese heading detection)
4. Chunk with parent-child strategy
5. Generate embeddings (BGE-M3)
6. Insert chunks with flattened ACL arrays from `metadata.allowed_*`
7. Update `knowledge.documents` with extraction metadata
8. Update `knowledge.processing_jobs` status → COMPLETED
9. Publish `document.uploaded` event

**Dead Letter Queue**:
- Queue: `ingestion.requests.dlq`
- Redelivery policy: 3 attempts (via `x-max-retries` or manual NACK tracking)
- After 3 failures, move to DLQ for manual investigation

---

### 6. unanswered.question

**Publisher**: `ai-qa-service`  
**Consumers**: `feedback-service` (only)  
**Routing Key**: `unanswered.question`

**Payload Schema**:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "880e8400-e29b-41d4-a716-446655440003",
  "conversation_id": "990e8400-e29b-41d4-a716-446655440004",
  "question": "Holiday bonus policy for contract employees?",
  "question_normalized": "chinh sach thuong le tet nhan vien hop dong",
  "search_query": "holiday bonus contract",
  "top_similarity_score": 0.35,
  "resolved": false,
  "priority": "MEDIUM",  // LOW, MEDIUM, HIGH
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Trigger Condition**: AI service cannot find sufficiently relevant chunks (similarity score below threshold, e.g., < 0.4) OR LLM indicates lack of information.

**Consumer Processing** (`feedback-service`):
1. Store in `analytics.unanswered_questions`
2. Surface in admin dashboard for knowledge gap analysis
3. Optionally notify content team via email/Slack
4. When admin resolves (adds missing document or updates existing), mark as `resolved = true`

---

## Queue Management

### Creating Queues (Python Example)

```python
import aio_pika

async def declare_queues(channel: aio_pika.Channel):
    # Main ingestion queue
    queue_ingest = await channel.declare_queue(
        "ingestion.requests",
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",  # DLX
            "x-dead-letter-routing-key": "ingestion.requests.dlq",
            "x-max-length": 10000,  # Max 10k messages
            "x-message-ttl": 86400000  # 24 hours (in ms)
        }
    )
    await queue_ingest.bind(exchange, routing_key="ingestion.requested")
    
    # DLQ
    queue_dlq = await channel.declare_queue(
        "ingestion.requests.dlq",
        durable=True
    )
    
    # Unanswered questions queue
    queue_unanswered = await channel.declare_queue(
        "feedback.unanswered.questions",
        durable=True
    )
    await queue_unanswered.bind(exchange, routing_key="unanswered.question")
```

### Consumer Acknowledgment Strategy

- **Successful processing**: `message.ack()`
- **Permanent failure** (invalid payload, unsupported file): `message.reject(requeue=False)` → DLQ
- **Transient failure** (DB timeout, network glitch): `message.nack(requeue=True)` → redeliver

---

## Event Schema Versioning

When adding new fields to event payloads:

1. **Additive changes** (new optional fields): Increment minor version (1.0 → 1.1). Backward compatible.
2. **Breaking changes** (remove/rename fields, change types): Increment major version (1.0 → 2.0). Requires coordinated deployment.

**Example Versioning**:

```json
// v1.0
{
  "event_type": "document.uploaded",
  "version": "1.0",
  "payload": {
    "document_id": "..."
  }
}

// v1.1 (backward compatible - new optional field)
{
  "event_type": "document.uploaded",
  "version": "1.1",
  "payload": {
    "document_id": "...",
    "uploaded_by": "user-id"  // New optional field
  }
}
```

Consumers should ignore unknown fields (JSON parsing libraries do this automatically).

---

## Testing Event Flows

### Unit Test (Consumer)

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_ingestion_requested_consumer():
    # Arrange
    message = Mock()
    message.body = json.dumps({
        "document_id": "doc-uuid",
        "file_key": "test.pdf",
        "bucket_name": "documents",
        "metadata": {"allowed_roles": ["USER"]}
    }).encode()
    
    # Act
    await on_ingestion_requested(message)
    
    # Assert
    assert processing_job.status == "COMPLETED"
    minio_service.download_file.assert_called_once_with("test.pdf", "documents")
```

### Integration Test (Full Event Flow)

```python
@pytest.mark.integration
async def test_document_upload_to_ai_indexing(e2e_services):
    # 1. Upload document via knowledge-service (HTTP)
    doc_id = await knowledge_client.upload_document("test.pdf")
    
    # 2. Wait for ingestion.requested event (listen on RabbitMQ)
    event = await rabbitmq_consumer.wait_for_event(
        routing_key="ingestion.requested",
        timeout=5
    )
    assert event.payload["document_id"] == doc_id
    
    # 3. Wait for document.uploaded event
    uploaded_event = await rabbitmq_consumer.wait_for_event(
        routing_key="document.uploaded",
        timeout=30
    )
    assert uploaded_event.payload["document_id"] == doc_id
    
    # 4. Query AI service to ensure document is searchable
    results = await ai_client.search("test query")
    assert any(r.document_id == doc_id for r in results)
```

---

## Monitoring & Observability

### Metrics to Track

| Metric | Service | Description |
|--------|---------|-------------|
| `events.published.total` | All | Counter of events published by type |
| `events.consumed.total` | All | Counter of events consumed by type |
| `events.dlq.size` | Ingestion | Number of messages in dead letter queue |
| `queue.depth` | All | Current message count per queue |
| `consumer.lag` | All | Messages waiting to be processed (unacknowledged) |

### Alerting Rules

- **DLQ not empty**: `events.dlq.size > 0` for > 5 minutes → PagerDuty
- **High consumer lag**: `consumer.lag > 1000` → Slack alert
- **Event processing failure rate**: `events.consumed.error / events.consumed.total > 0.05` → Alert

---

## Error Handling & Retry

### Consumer Failure Scenarios

| Error Type | Action | Max Retries |
|------------|--------|-------------|
| `JSONDecodeError` (malformed payload) | `reject(requeue=False)` → DLQ | 0 |
| `ValidationError` (missing required fields) | `reject(requeue=False)` → DLQ | 0 |
| `DatabaseConnectionError` | `nack(requeue=True)` | 3 (exponential backoff) |
| `ExternalServiceTimeout` (LLM, embedding) | `nack(requeue=True)` | 2 |
| `PermissionError` (ACL violation) | `ack()` but log warning | N/A (business logic) |

### Idempotency Requirements

**All consumers MUST be idempotent** because RabbitMQ may redeliver messages:
- Message redelivered if consumer crashes before ack
- At-least-once delivery guarantee (not exactly-once)

**Idempotent Pattern**:
```python
async def on_ingestion_requested(message):
    event = parse_event(message.body)
    
    # Check if already processed
    job = await job_repo.find_by_id(event.job_id)
    if job and job.status in ['COMPLETED', 'FAILED']:
        await message.ack()  # Skip duplicate
        return
    
    # Process with idempotent database operations
    try:
        await process_ingestion(event)
        await message.ack()
    except Exception:
        await message.nack(requeue=False)  # Don't infinite loop
```

---

## References

- **RabbitMQ Configuration**: See `docker-compose.yml` for broker setup
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md` - which services own which queues
- **Implementation Examples**: `contexts/development/extraction-plan.md` - full consumer implementation

---

**Last Updated**: 2026-04-08
**Maintained By**: Architecture Team
