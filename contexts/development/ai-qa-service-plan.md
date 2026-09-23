---
title: AI Q&A Service MVP Implementation Plan
description: Complete implementation plan for Poliwise ai-qa-service (Python FastAPI)
type: development
version: 1.0
---

# AI Q&A Service MVP Implementation Plan

## Purpose

This document provides the complete technical implementation plan for building the ai-qa-service (Python FastAPI) that handles retrieval-augmented generation (RAG), conversation management, and knowledge gap detection for the Poliwise AI platform.

## When to Use

- Implementing the ai-qa-service from scratch
- Understanding the Q&A pipeline flow
- Reference for architecture decisions and technical specifications
- Onboarding developers to the AI layer

---

## 1. Executive Summary

The current Poliwise system has a production-ready ingestion service (port 8088) that processes documents, creates chunks, and generates embeddings. However, the ai-qa-service (port 8086) referenced in the architecture is not implemented. This plan outlines the complete implementation of the Q&A Service MVP.

## 2. Current System State Analysis

### What's Ready

| Component | Status | Details |
|-----------|--------|---------|
| **Ingestion Pipeline** | Complete | Full ETL: download → extract → dedup → standardize → chunk → embed → persist |
| **Vector Storage** | Ready | `knowledge.chunks` with pgvector (1024-dim BGE-M3 embeddings), HNSW index |
| **Full-text Search** | Ready | GIN index on `content_tsv` (TSVECTOR), GIN on `allowed_roles`, `allowed_departments` |
| **Conversation Schema** | Ready | `conversation.conversations`, `conversation.messages`, `conversation.unanswered_questions` |
| **API Gateway** | Configured | Routes `/api/v1/ai/*` → `ai-qa-service:8086` (JWT+RBAC validated by gateway, user context forwarded via `X-User-Id`, `X-Role`, `X-Department-Id` headers) |
| **Embedding Model** | Running | BGE-M3 on port 8001 (HuggingFace TEI) |
| **LLM Provider** | Configured | Groq API key in docker-compose |

### What's Missing

- **ai-qa-service** (port 8086) - Does not exist
- **Retrieval** - Semantic search over chunks
- **Reranking** - Configured but not wired
- **Generation** - LLM integration
- **Conversation API** - Chat, history, management

---

## 3. Architecture Overview

### System Flow

```
                         Frontend (Next.js)
              Chat UI │ History │ Unanswered Questions
                              │
                              │ /api/v1/ai/* (JWT+RBAC)
                              ▼
                    API Gateway (NestJS :3001)
              Routes to ai-qa-service:8086
                              │
                          ai-qa-service (FastAPI :8086)

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ AI Input     │───▶│  Retrieval   │───▶│   Reranker   │───▶│   LLM Gen    │
  │ Gateway      │    │   (Hybrid)   │    │   (Optional) │    │   (Groq)     │
  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
    (Gemini Flash)           │                   │                   │
          │                  ▼                   ▼                   ▼
          ▼           ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   ┌──────────────┐   │ Conversation │    │   Results    │    │   Feedback   │
   │ Intent/Safety│   │   Manager    │    │   Formatter  │    │   Loop       │
   └──────────────┘   └──────────────┘    └──────────────┘    └──────────────┘
          ▼                   ▼
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ Conversation │    │   LLM Gen    │    │   Results    │
  │   Manager    │    │   (Groq)     │    │   Formatter  │
  └──────────────┘    └──────────────┘    └──────────────┘

                              │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
  PostgreSQL          BGE-M3 Embedding        RabbitMQ
  (conversation)           (:8001)           (Events)
        │                    │
        ▼                    ▼
  PostgreSQL          MinIO
  (knowledge)       (Documents)
```

---

## 4. Database Schema Requirements

### Reference Schemas (Source of Truth)

| Schema | Table | Purpose |
|--------|-------|---------|
| `knowledge` | `chunks` | Vector search + full-text retrieval |
| `knowledge` | `documents` | Technical file metadata (size, type, status) |
| `metadata` | `document_metadata` | Business metadata (title, description, category) |
| `conversation` | `conversations` | Chat session management |
| `conversation` | `messages` | Message history with sources, tokens, latency |
| `conversation` | `unanswered_questions` | Knowledge gap tracking |

### Key Columns for Retrieval

**knowledge.chunks** (critical):
```sql
id UUID PRIMARY KEY,
document_id UUID,
document_version_id UUID,
content TEXT,
embedding_vector vector(1024),
allowed_roles core.user_role[],
allowed_departments UUID[],
allowed_users UUID[],
access_level VARCHAR(20),
is_latest BOOLEAN,
section_title VARCHAR(500),
section_path TEXT[],
metadata JSONB
```

**conversation.messages**:
```sql
id UUID PRIMARY KEY,
conversation_id UUID,
role message_role (USER/ASSISTANT/SYSTEM),
content TEXT,
sources JSONB,
model_used VARCHAR(50),
tokens_prompt INT,
tokens_completion INT,
tokens_total INT,
latency_ms INT,
confidence confidence_level,
has_sources BOOLEAN,
is_streaming BOOLEAN,
streaming_completed BOOLEAN,
created_at TIMESTAMPTZ
```

---

## 5. Project Structure

```
services/ai-qa-service/
├── Dockerfile
├── pyproject.toml
├── .env.example
├── src/
│   ├── main.py                          # FastAPI app entry point
│   ├── config/
│   │   ├── settings.py                  # Pydantic settings
│   │   └── rabbitmq.py                  # RabbitMQ connection
│   ├── api/
│   │   ├── dependencies.py              # Gateway header extraction (X-User-Id, X-Role, X-Department-Id)
│   │   └── routes/
│   │       ├── health.py                # GET /health
│   │       ├── chat.py                  # POST /chat, POST /chat/stream
│   │       ├── conversations.py          # CRUD for conversations
│   │       ├── messages.py              # GET messages, DELETE messages
│   │       └── unanswered.py            # Mark/resolve unanswered
│   ├── services/
│   │   ├── input_processing/
│   │   │   ├── gateway.py               # AI Input Gateway (Gemini Flash)
│   │   │   ├── query_refiner.py         # Query rewriting & expansion
│   │   │   └── intent_classifier.py     # Intent & Safety detection
│   │   ├── retrieval/
│   │   │   ├── hybrid_search.py         # Hybrid (vector + BM25)
│   │   │   ├── semantic_search.py       # Vector search
│   │   │   └── reranker.py              # Cross-encoder reranking
│   │   ├── generation/
│   │   │   ├── llm_client.py            # Multi-provider LLM client (OpenAI-compatible)
│   │   │   ├── prompt_builder.py        # RAG prompt construction
│   │   │   └── stream_generator.py      # SSE streaming
│   │   ├── conversation/
│   │   │   ├── manager.py               # Conversation CRUD
│   │   │   ├── message_service.py       # Message storage
│   │   │   └── context_builder.py       # Chat history context
│   │   └── knowledge_gap.py             # Unanswered question detection
│   ├── models/
│   │   ├── conversation.py              # Pydantic conversation models
│   │   ├── message.py                   # Pydantic message models
│   │   ├── retrieval.py                 # Retrieval result models
│   │   └── generation.py                # Generation result models
│   ├── db/
│   │   ├── session.py                   # AsyncPG session (search_path: conversation,knowledge,metadata,core,public)
│   │   └── repositories/
│   │       ├── conversation_repo.py
│   │       ├── message_repo.py
│   │       ├── chunk_repo.py            # Knowledge chunks read
│   │       └── document_repo.py         # Document metadata read
│   └── events/
│       ├── publisher.py                 # Publish unanswered.question
│       └── consumer.py                  # Consume user.status.changed
└── tests/
    ├── test_retrieval.py
    ├── test_generation.py
    └── test_conversation.py
```

### Authentication Strategy

> **IMPORTANT**: The ai-qa-service sits BEHIND the API Gateway. The gateway already validates JWT tokens and enforces RBAC. It then forwards the authenticated user context via HTTP headers. The ai-qa-service must NOT validate JWT tokens directly — it should extract user context from these gateway-injected headers.

**Gateway Header Extraction** (`api/dependencies.py`):
```python
from fastapi import Request, HTTPException, status
from pydantic import BaseModel
from uuid import UUID

class UserContext(BaseModel):
    user_id: UUID
    role: str  # USER, MANAGER, ADMIN
    department_id: UUID | None = None

def get_user_context(request: Request) -> UserContext:
    """Extract authenticated user context from gateway-injected headers."""
    user_id = request.headers.get("X-User-Id")
    role = request.headers.get("X-Role")
    department_id = request.headers.get("X-Department-Id")

    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user context headers (request must pass through API Gateway)"
        )

    return UserContext(
        user_id=UUID(user_id),
        role=role,
        department_id=UUID(department_id) if department_id else None
    )
```

Usage in routes:
```python
from fastapi import Depends
from src.api.dependencies import get_user_context, UserContext

@router.post("/chat")
async def chat(request: ChatRequest, user: UserContext = Depends(get_user_context)):
    ...
```

---

## 6. Core Services Implementation

### 6.0 AI Input Gateway (Orchestration)

**Strategy**: Use **Gemini 1.5 Flash** (via Google AI Studio) as a lightweight, fast, and cheap "Brain" at the entry point to handle input validation and optimization.

**Key Functions**:
1. **Safety/Toxic Filtering**: Reject queries that are harmful or nonsense.
2. **Intent Classification**: Decide if the query needs RAG, a direct response (chitchat), or is irrelevant.
3. **Query Refinement**: Rewrite the query to include conversation context (De-contextualization) and expand it for better retrieval.
4. **Metadata Extraction**: Extract potential filters (date, category) from the query.

```python
class InputGatewayService:
    def __init__(self, api_key: str):
        self.client = AsyncGenerativeModel("gemini-1.5-flash")
        
    async def process_input(
        self, 
        user_input: str, 
        history: list[Message]
    ) -> GatewayResult:
        # Prompt engineering for strict JSON output
        prompt = self._build_gateway_prompt(user_input, history)
        
        response = await self.client.generate_content(prompt)
        result = json.loads(response.text)
        
        return GatewayResult(
            action=result["action"], # "forward", "reject", "respond_directly"
            refined_query=result.get("refined_query", user_input),
            explanation=result.get("explanation"),
            suggested_filters=result.get("filters")
        )
```

### 6.1 Retrieval Service (Hybrid Search)

**Strategy**: Combine dense vector search (BGE-M3) with sparse BM25 for robust retrieval.

```python
class HybridSearchService:
    def __init__(
        self,
        embedding_url: str = "http://bge-m3-embedding:80",
        reranker_url: str = None
    ):
        self.embedding_url = embedding_url
        self.reranker_url = reranker_url

    async def search(
        self,
        query: str,
        user_context: UserContext,
        filters: RetrievalFilters,
        limit: int = 10,
        use_reranker: bool = False
    ) -> list[RetrievalChunk]:
        # 1. Generate query embedding
        query_embedding = await self._embed_query(query)

        # 2. Vector search (HNSW)
        vector_results = await self._vector_search(
            query_embedding, user_context, filters, limit * 2
        )

        # 3. BM25 full-text search
        bm25_results = await self._bm25_search(
            query, user_context, filters, limit * 2
        )

        # 4. Merge and deduplicate (RRF)
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)

        # 5. Optional: Rerank
        if use_reranker and self.reranker_url:
            fused = await self._rerank(query, fused, limit)
        else:
            fused = fused[:limit]

        return fused
```

**SQL for Vector Search**:
```sql
SELECT
    c.id, c.content, c.document_id, dm.title as document_name,
    (c.embedding_vector <=> :query_embedding::vector) as distance,
    c.section_title, c.metadata
FROM knowledge.chunks c
JOIN metadata.document_metadata dm ON dm.document_id = c.document_id
WHERE c.is_latest = true
  AND c.deleted_at IS NULL
  AND (c.access_level = 'PUBLIC'
       OR c.allowed_roles && :user_roles::core.user_role[]
       OR c.allowed_departments && :user_departments::uuid[]
       OR c.allowed_users && :user_ids::uuid[])
  AND (:document_ids IS NULL OR c.document_id = ANY(:document_ids))
ORDER BY distance ASC
LIMIT :limit;
```

**SQL for BM25 Search**:
```sql
SELECT
    c.id, c.content, c.document_id, dm.title as document_name,
    ts_rank(c.content_tsv, plainto_tsquery('english', :query)) as rank,
    c.section_title, c.metadata
FROM knowledge.chunks c
JOIN metadata.document_metadata dm ON dm.document_id = c.document_id
WHERE c.content_tsv @@ plainto_tsquery('english', :query)
  AND c.is_latest = true
  AND c.deleted_at IS NULL
  AND (c.access_level = 'PUBLIC'
       OR c.allowed_roles && :user_roles::core.user_role[]
       OR c.allowed_departments && :user_departments::uuid[]
       OR c.allowed_users && :user_ids::uuid[])
  AND (:document_ids IS NULL OR c.document_id = ANY(:document_ids))
ORDER BY rank DESC
LIMIT :limit;
```

> **NOTE on text search language**: Since the primary dataset (GitLab Handbook) is 100% English, the `content_tsv` column using `to_tsvector('english', content)` is optimal. While the underlying schema supports multiple languages, the system is currently tuned for English-language retrieval.

> **IMPORTANT: Distance vs Similarity Conversion**: The vector search SQL returns cosine distance (`<=>` operator, range 0–2, lower = more similar). You MUST convert this to a similarity score before using it elsewhere: `similarity_score = 1.0 - distance`. The `RetrievalChunk` model should store `similarity_score` (0–1, higher = better), not raw distance.

### 6.2 Reranker Service (Optional)

> **NOTE**: If using HuggingFace TEI reranker (consistent with the embedding model), the endpoint is `/rerank` and the request/response format is as shown below. Adjust if using a different reranker.

```python
class RerankerService:
    def __init__(self, reranker_url: str):
        self.reranker_url = reranker_url

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievalChunk],
        limit: int = 5
    ) -> list[RetrievalChunk]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.reranker_url}/rerank",
                json={
                    "query": query,
                    "texts": [chunk.content for chunk in chunks],
                    "truncate": True
                }
            )
            results = response.json()  # [{"index": 0, "score": 0.95}, ...]

        ranked = sorted(results, key=lambda x: x["score"], reverse=True)
        return [chunks[r["index"]] for r in ranked[:limit]]
```
```

### 6.3 Generation Service (Dynamic Model Registry)

**Strategy**: Maintain a registry of available model profiles and initialize the appropriate client per request.

```python
class ModelProfile(BaseModel):
    id: str              # Unique ID (e.g., "groq/llama-70b")
    name: str            # Display name
    provider: str        # groq, openrouter, local, etc.
    model_name: str      # Actual model ID for the provider
    base_url: str
    api_key: str | None

class LLMGenerationService:
    def __init__(self, registry: dict[str, ModelProfile]):
        self.registry = registry
        self.prompt_builder = PromptBuilder()

    def _get_client(self, model_id: str):
        profile = self.registry.get(model_id) or self.registry["default"]
        return AsyncOpenAI(
            api_key=profile.api_key,
            base_url=profile.base_url
        ), profile.model_name

    async def generate(
        self,
        query: str,
        retrieved_chunks: list[RetrievalChunk],
        conversation_history: list[Message],
        model_id: str = "default",
        system_prompt: str = None
    ) -> GenerationResult:
        client, actual_model = self._get_client(model_id)
        messages = self.prompt_builder.build(
            query=query,
            context_chunks=retrieved_chunks,
            history=conversation_history,
            system_prompt=system_prompt
        )

        start_time = time.time()
        response = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024
        )
        latency_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            content=response.choices[0].message.content,
            model_used=actual_model,
            tokens_prompt=response.usage.prompt_tokens,
            tokens_completion=response.usage.completion_tokens,
            tokens_total=response.usage.total_tokens,
            latency_ms=latency_ms
        )

    async def generate_streaming(
        self,
        query: str,
        retrieved_chunks: list[RetrievalChunk],
        conversation_history: list[Message],
        model_id: str = "default",
        system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        client, actual_model = self._get_client(model_id)
        messages = self.prompt_builder.build(
            query=query,
            context_chunks=retrieved_chunks,
            history=conversation_history,
            system_prompt=system_prompt
        )

        stream = await client.chat.completions.create(
            model=actual_model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### 6.4 RAG Prompt Template

```
You are a helpful AI assistant for Poliwise, a policy management platform.
Answer the user's question based ONLY on the provided context from the knowledge base.

## Context (Retrieved Documents)
{formatted_chunks}

## Conversation History
{formatted_history}

## Question
{query}

## Instructions
- Answer based only on the provided context
- If the context doesn't contain enough information to answer the question, say "I don't have enough information to answer this question based on the available documents."
- Cite sources by mentioning document titles when relevant
- Keep answers concise and helpful
- If unsure, acknowledge uncertainty rather than hallucinating
```

### 6.5 Conversation Management

```python
class ConversationManager:
    async def create_conversation(
        self,
        user_id: UUID,
        title: str = None
    ) -> Conversation:
        # Auto-generate title from first message if not provided
        ...

    async def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        sources: list[SourceDocument] = None,
        generation_result: GenerationResult = None
    ) -> Message:
        # Store message with metadata
        ...

    async def get_conversation_history(
        self,
        conversation_id: UUID,
        limit: int = 20
    ) -> list[Message]:
        # Return recent messages for context
        ...
```

### 6.6 Unanswered Question Detection

```python
class KnowledgeGapDetector:
    def __init__(self, similarity_threshold: float = 0.3):
        self.threshold = similarity_threshold

    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[RetrievalChunk]
    ) -> UnansweredQuestionResult:
        if not retrieved_chunks:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="no_chunks_retrieved",
                top_similarity=0.0
            )

        top_similarity = retrieved_chunks[0].similarity_score

        if top_similarity < self.threshold:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="low_relevance",
                top_similarity=top_similarity,
                search_query=query,
                priority=self._determine_priority(top_similarity)
            )

        return UnansweredQuestionResult(
            is_unanswered=False,
            top_similarity=top_similarity
        )

    async def publish_unanswered(
        self,
        result: UnansweredQuestionResult,
        user_id: UUID,
        message_id: UUID,
        conversation_id: UUID
    ):
        event = UnansweredQuestionEvent(
            user_id=user_id,
            message_id=message_id,
            conversation_id=conversation_id,
            question=query,
            search_query=result.search_query,
            top_similarity_score=result.top_similarity,
            priority=result.priority
        )
        await event_publisher.publish("unanswered.question", event)
```

---

## 7. API Endpoints

### Route Registration

> **CRITICAL**: The API Gateway (`proxy.controller.ts` line 363) strips the `/api/v1/ai` prefix before forwarding to ai-qa-service:
> ```typescript
> const path = request.url.replace('/api/v1/ai', '');
> // /api/v1/ai/chat → /chat
> // /api/v1/ai/conversations/123 → /conversations/123
> ```
> Therefore, the ai-qa-service must register routes WITHOUT `/api/v1/ai`. The table below shows both the public (gateway) path and the internal (service) path.

### Core Endpoints

| Method | Public Path (via Gateway) | Internal Path (ai-qa-service) | Description | RBAC |
|--------|--------------------------|-------------------------------|-------------|------|
| `GET` | `/api/v1/ai/models` | `/models` | List available models for dropdown | USER+ |
| `POST` | `/api/v1/ai/chat` | `/chat` | Send message, get response | USER+ |
| `POST` | `/api/v1/ai/chat/stream` | `/chat/stream` | Streaming chat response | USER+ |
| `GET` | `/api/v1/ai/conversations` | `/conversations` | List user conversations | USER+ |
| `GET` | `/api/v1/ai/conversations/{id}` | `/conversations/{id}` | Get conversation details | USER+ |
| `DELETE` | `/api/v1/ai/conversations/{id}` | `/conversations/{id}` | Delete conversation | USER+ |
| `GET` | `/api/v1/ai/conversations/{id}/messages` | `/conversations/{id}/messages` | Get message history | USER+ |
| `DELETE` | `/api/v1/ai/conversations/{id}/messages` | `/conversations/{id}/messages` | Clear conversation history | USER+ |
| `POST` | `/api/v1/ai/conversations/{id}/messages/{msg_id}/unanswered` | `/conversations/{id}/messages/{msg_id}/unanswered` | Mark as unanswered | MANAGER+ |

### Request/Response Models

**POST /chat**:

Request:
```python
class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    model_id: str = "default"  # Selection from dropdown (see NOTE below)
    context: ChatContext | None = None

class ChatContext(BaseModel):
    document_ids: list[UUID] | None = None
    category_ids: list[UUID] | None = None
```

> **NOTE on `model_id`**: The current frontend `SendMessageRequest` in `frontend/web/services/ai.service.ts` does NOT include a `modelId` field. The backend should treat `model_id` as optional with a safe default of `"default"`. A separate frontend task is needed to add the model selector dropdown and pass `modelId` in the request body.

Response:
```python
class ChatResponse(BaseModel):
    message: Message
    conversation: Conversation
    sources: list[SourceDocument] | None = None
```

**GET /conversations**:

```python
class ConversationListResponse(BaseModel):
    items: list[Conversation]
    page: int
    size: int
    total: int
```

**GET /models**:

Response:
```python
class AIModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    description: str | None
    is_default: bool

class ModelListResponse(BaseModel):
    models: list[AIModelResponse]
```

---

## 8. Event-Driven Integration

### Events Published

| Event | Routing Key | Purpose |
|-------|-------------|---------|
| `unanswered.question` | `unanswered.question` | Notify feedback-service of knowledge gaps |

### Events Consumed

| Event | Handler |
|-------|---------|
| `user.status.changed` | Invalidate user session caches |

### Event Payload

```json
{
  "event_type": "unanswered.question",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0",
  "payload": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "message_id": "660e8400-e29b-41d4-a716-446655440001",
    "conversation_id": "770e8400-e29b-41d4-a716-446655440002",
    "question": "What is the remote work policy?",
    "search_query": "remote work policy",
    "top_similarity_score": 0.25,
    "priority": "HIGH",
    "user_department_id": "dept-uuid",
    "user_role": "USER"
  }
}
```

---

## 9. Environment Configuration

```env
# Server
HOST=0.0.0.0
PORT=8086
LOG_LEVEL=info
INTERNAL_API_KEY=secret-key-for-internal-services

# Database
DATABASE_URL=postgresql+asyncpg://poliwise:poliwise_secure_password@postgres:5432/poliwise
DATABASE_SCHEMA=conversation

# RabbitMQ
RABBITMQ_URL=amqp://poliwise:poliwise_secure_password@rabbitmq:5672
RABBITMQ_EXCHANGE=poliwise.events

# Embedding & Reranking
EMBEDDING_URL=http://bge-m3-embedding:80
RERANKER_URL=http://reranker:8002

# LLM Provider Configuration (Generation - Groq)
# Options: groq, openrouter, openai, gemini, local
LLM_PROVIDER=groq
LLM_API_KEY=gsk_your_groq_api_key_here
LLM_MODEL=llama-3.3-70b-versatile
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.3

# AI Input Gateway (Gemini 1.5 Flash)
GATEWAY_API_KEY=your_google_ai_studio_api_key_here
GATEWAY_MODEL=gemini-1.5-flash
GATEWAY_ENABLED=true

# Local LLM Example (llama-server)
# LLM_PROVIDER=local
# LLM_API_KEY=not-needed
# LLM_MODEL=qwen3-8b
# LLM_BASE_URL=http://localhost:8080/v1

# Retrieval
RETRIEVAL_LIMIT=10
RERANK_LIMIT=5
SIMILARITY_THRESHOLD=0.3
USE_RERANKER=false

# Rate Limiting
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60

# Conversation
MAX_HISTORY_MESSAGES=20
CONVERSATION_TITLE_MAX_LENGTH=255
```

---

## 10. Dependencies

```toml
[project]
name = "poliwise-ai-qa"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # FastAPI & Web
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sse-starlette>=2.0.0",

    # Database
    "asyncpg>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "pgvector>=0.3.0",

    # Message Queue
    "aio-pika>=9.4.0",

    # Configuration
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",

    # LLM (OpenAI-compatible client for Groq, OpenRouter, local, etc.)
    "openai>=1.50.0",

    # AI Input Gateway (Gemini Flash)
    "google-generativeai>=0.8.0",

    # HTTP Client
    "httpx>=0.27.0",

    # Observability
    "structlog>=24.1.0",
    "prometheus-client>=0.21.0",
]
```

> **NOTE**: `PyJWT` is NOT needed — the API Gateway handles JWT validation. User context is received via forwarded HTTP headers.

---

## 11. Implementation Checklist

### Phase 1: Project Setup
- [ ] Create `services/ai-qa-service/` directory
- [ ] Initialize FastAPI project with pyproject.toml
- [ ] Configure logging and health checks (`/health` endpoint)
- [ ] Set up database session with `search_path` for multi-schema access
- [ ] Implement gateway header extraction (`X-User-Id`, `X-Role`, `X-Department-Id`)
- [ ] Add to docker-compose.yml (see Section 11.1)

### Phase 2: AI Input Gateway (Gemini Flash)
- [ ] Implement Gemini Flash client for Gateway
- [ ] Design Gateway Prompt (Intent + Safety + Rewriting)
- [ ] Implement query de-contextualization from history
- [ ] Add guardrails to reject toxic/irrelevant queries

### Phase 3: Core API
- [ ] Implement `/chat` endpoint (non-streaming)
- [ ] Implement `/chat/stream` endpoint (streaming)
- [ ] Implement `/models` endpoint (list available LLM models)
- [ ] Add rate limiting

### Phase 4: Retrieval
- [ ] Implement semantic search (vector) with RBAC filtering
- [ ] Implement BM25 full-text search with RBAC filtering
- [ ] Implement hybrid RRF fusion
- [ ] Add distance-to-similarity conversion (`1.0 - distance`)
- [ ] Add document/category filters

### Phase 5: Generation
- [ ] Implement model registry with multi-provider support
- [ ] Build RAG prompt template
- [ ] Implement response formatting with sources
- [ ] Add SSE streaming support

### Phase 6: Conversation Management
- [ ] Implement conversation CRUD
- [ ] Implement message storage with metadata
- [ ] Build conversation context for prompt

### Phase 7: Knowledge Gap Detection
- [ ] Implement similarity threshold detection
- [ ] Implement unanswered question storage
- [ ] Publish `unanswered.question` events

### Phase 8: Integration & Testing
- [ ] Verify API Gateway routing works (gateway strips `/api/v1/ai`)
- [ ] Verify gateway health check compatibility (see NOTE below)
- [ ] Integration tests with real services
- [ ] Load testing

> **NOTE on Health Checks**: The API Gateway's `proxy.service.ts` uses `/actuator/health` for health checking (Java convention). Since ai-qa-service is Python/FastAPI, either:
> - (a) Add an alias route `GET /actuator/health` in the ai-qa-service that returns the same response as `/health`, OR
> - (b) Update `services.indicator.ts` in the gateway to use `/health` for the AI_QA service.

### 11.1 Docker-Compose Service Block

```yaml
  ai-qa-service:
    build:
      context: ./services/ai-qa-service
      dockerfile: Dockerfile
    container_name: poliwise-ai-qa-service
    restart: unless-stopped
    environment:
      HOST: 0.0.0.0
      PORT: 8086
      LOG_LEVEL: info
      DATABASE_URL: postgresql+asyncpg://poliwise:${POSTGRES_PASSWORD:-poliwise_secure_password}@postgres:5432/poliwise
      DATABASE_SCHEMA: conversation
      RABBITMQ_URL: amqp://poliwise:${RABBITMQ_PASSWORD:-poliwise_secure_password}@rabbitmq:5672
      RABBITMQ_EXCHANGE: poliwise.events
      EMBEDDING_URL: http://bge-m3-embedding:80
      RERANKER_URL: ${RERANKER_URL:-http://host.docker.internal:8002}
      LLM_PROVIDER: ${LLM_PROVIDER:-groq}
      LLM_API_KEY: ${GROQ_API_KEY}
      LLM_MODEL: ${GROQ_MODEL:-llama-3.3-70b-versatile}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.groq.com/openai/v1}
      GATEWAY_API_KEY: ${GATEWAY_API_KEY:-}
      GATEWAY_MODEL: ${GATEWAY_MODEL:-gemini-1.5-flash}
      GATEWAY_ENABLED: ${GATEWAY_ENABLED:-true}
    ports:
      - "8086:8086"
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      bge-m3-embedding:
        condition: service_healthy
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8086/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          memory: 512M
    networks:
      - poliwise
```

---

## 12. Frontend API Contract (Reference)

The frontend expects these endpoints (from `services/ai.service.ts`):

```typescript
interface SendMessageRequest {
  message: string;
  conversationId?: string;
  context?: {
    documentIds?: string[];
    categoryIds?: string[];
  };
}

interface SendMessageResponse {
  message: Message;
  conversation: Conversation;
  sources?: {
    documentId: string;
    documentName: string;
    relevanceScore: number;
    excerpt: string;
  }[];
}

interface ConversationSearchParams {
  page?: number;
  size?: number;
  keyword?: string;
}

// Expected endpoints:
POST /api/v1/ai/chat -> SendMessageResponse
GET /api/v1/ai/conversations -> PaginatedResponse<Conversation>
GET /api/v1/ai/conversations/{id} -> Conversation
GET /api/v1/ai/conversations/{id}/messages -> Message[]
DELETE /api/v1/ai/conversations/{id} -> void
DELETE /api/v1/ai/conversations/{id}/messages -> void
POST /api/v1/ai/conversations/{id}/messages/{messageId}/unanswered -> UnansweredQuestion
```

---

## 13. API Gateway Integration

From `services/api-gateway/src/proxy/proxy.controller.ts`:

```typescript
// AI Q&A endpoints — route to ai-qa-service
@UseGuards(JwtAuthGuard, RolesGuard)
@All('ai/*path')
@Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
handleAI(@Req() request: Request) {
  const path = request.url.replace('/api/v1/ai', '');
  return this.proxyService.forward(ServiceName.AI_QA, request, path);
}
```

The service name `AI_QA` maps to `ai-qa-service:8086` in `proxy.service.ts`.

---

## 14. Design Decisions (Resolved)

1. **LLM Provider**: Multi-provider supported via model registry (OpenAI-compatible API). Groq is the default. OpenRouter, local models (Qwen3, etc.) can be added by registering new profiles — no code changes needed.

2. **Reranking**: Implemented as optional feature. Activated only when `USE_RERANKER=true` AND `RERANKER_URL` is configured. Skipped for MVP but wired for easy activation.

3. **Streaming**: Both non-streaming (`POST /chat`) and streaming (`POST /chat/stream` via SSE) are implemented from the start. The frontend can use either.

4. **System Prompt**: Configurable via environment variable with a sensible default (see Section 6.4). Can be overridden per-request if needed.

---

## References

- **Database Schema**: `docs/supbase_sql/conversation_and_message_store.sql`
- **Knowledge Chunks Schema**: `docs/supbase_sql/knowledge_management.sql`
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md`
- **Event Contracts**: `contexts/service-boundaries/events.md`
- **Ingestion Service**: `contexts/development/extraction-plan.md`
- **Frontend AI Service**: `frontend/web/services/ai.service.ts`
- **Conversation Models**: `frontend/web/interfaces/models/conversation/`

---

**Last Updated**: 2026-05-11
**Version**: 1.1 (reviewed and corrected)