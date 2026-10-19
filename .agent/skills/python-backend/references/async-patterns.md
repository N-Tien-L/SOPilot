# SOPilot Async Patterns

This document details the common asynchronous patterns used across SOPilot's Python microservices (`ai-qa-service` and `ingestion-service`).

## 1. Async Endpoint Pattern

Always use `async def` for FastAPI routes. Inject dependencies (like database sessions or service instances) using `Depends`. Handle domain exceptions gracefully.

```python
from fastapi import APIRouter, Depends, HTTPException, status
from src.schemas.document import DocumentCreate, DocumentResponse
from src.services.document_service import DocumentService
from src.api.dependencies import get_document_service
from src.exceptions import DomainError
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    request: DocumentCreate,
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        doc = await document_service.process_and_store(request)
        logger.info("document_created", document_id=doc.id)
        return doc
    except DomainError as e:
        logger.warning("document_creation_failed", reason=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

## 2. Async Database Session Management

Use context managers or FastAPI dependency injection for session management to ensure connections are returned to the `asyncpg` pool.

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://user:pass@host/db", pool_size=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Dependency for FastAPI
async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session
```

## 3. Async RabbitMQ (aio-pika) Patterns

### Publisher Pattern

Maintain a connection pool and publish messages to the topic exchange.

```python
import aio_pika
import structlog

logger = structlog.get_logger()

async def publish_event(channel_pool, routing_key: str, payload: dict):
    async with channel_pool.acquire() as channel:
        exchange = await channel.get_exchange("poliwise.events")
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        await exchange.publish(message, routing_key=routing_key)
        logger.debug("event_published", routing_key=routing_key)
```

### Consumer Pattern

Use background tasks to run consumers and always acknowledge or reject messages explicitly.

```python
async def process_message(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(ignore_processed=True):
        try:
            payload = json.loads(message.body)
            # Process logic here
            await message.ack()
        except Exception as e:
            logger.error("message_processing_failed", error=str(e))
            await message.reject(requeue=False) # Route to DLQ
```

## 4. SSE Streaming Pattern (ai-qa-service)

Use `sse-starlette` to stream responses, commonly used with Groq LLM streaming.

```python
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter

router = APIRouter()

@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    async def event_generator():
        try:
            async for chunk in llm_service.stream_response(request.prompt):
                yield {"event": "message", "data": chunk}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as e:
            yield {"event": "error", "data": str(e)}
            
    return EventSourceResponse(event_generator())
```

## 5. Background Tasks

Always handle exceptions in `asyncio.create_task` by attaching a callback.

```python
import asyncio
import structlog

logger = structlog.get_logger()

def handle_task_result(task: asyncio.Task):
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("background_task_failed", error=str(e), exc_info=True)

# Usage
task = asyncio.create_task(some_async_function())
task.add_done_callback(handle_task_result)
```

## 6. Testing Async Code

Use `pytest-asyncio` and mark async tests appropriately.

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_document(async_client: AsyncClient):
    response = await async_client.post("/api/v1/documents/", json={"title": "Test"})
    assert response.status_code == 201
```

## 7. Common Pitfalls
- **Blocking Calls**: Do not use `requests.get()` inside async code; use `httpx.AsyncClient().get()`.
- **Unhandled Task Exceptions**: A "fire and forget" task without an error callback will fail silently.
- **Connection Leaks**: Always use `async with` for DB sessions and RMQ channels to ensure they are returned to the pool.
