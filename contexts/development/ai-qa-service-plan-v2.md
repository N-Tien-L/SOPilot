# AI Q&A Service — Implementation Plan v2.0 (English)

> **Version**: 2.0 | **Based on**: v1.1 (2026-05-11) | **Updated**: 2026-05-13

---

## What Changed from v1.1 → v2.0

| Area | v1.1 | v2.0 |
|---|---|---|
| Input processing | Single step (Gemini Flash handles everything) | 3 independent, specialized layers |
| Toxic filter | Embedded in gateway prompt | Dedicated Layer 1 — specialized 22M-param model |
| Intent classification | Embedded in gateway prompt | Dedicated Layer 2 — fast 8B model |
| Simple query handling | None — all queries go through RAG | Answered directly at Layer 2, no RAG cost |
| Model selection | Hardcoded single model via env var | Multi-model dropdown, user selects at runtime |
| Rate limit handling | None | Detects HTTP 429, notifies user to switch model |
| Auto title generation | None | Generated at Layer 3 when conversation is new |
| Context building | All messages | Layer 3 messages only (avoids hallucination from chitchat) |
| Groq dependency | Single key for everything | Groq for Layers 1 & 2; Layer 3 is pluggable |

---

## 1. Executive Summary

v2 upgrades the processing pipeline from a "single gateway does everything" model to a **3-Layer Processing Architecture** with clear separation of concerns. The design optimizes cost by blocking harmful queries early, skipping heavy RAG/LLM calls for simple questions, and allowing users to select their own Layer 3 model with intelligent fallback when rate limits are hit.

---

## 2. Overall Architecture

### 2.1 Query Flow

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 1 — Toxic Filter                                   │
│ Model: llama-prompt-guard-2-22m (Groq API)               │
│ Target latency: < 200ms                                  │
└──────────────────────────────────────────────────────────┘
    │ TOXIC → Return "Inappropriate content". Stop.
    │ SAFE ↓
    ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 2 — Intent Classifier                              │
│ Model: llama-3.1-8b-instant (Groq API)                   │
│ Classification: [SIMPLE] or [COMPLEX]                    │
└──────────────────────────────────────────────────────────┘
    │ SIMPLE → Answer directly (8b-instant). Stop.
    │          Save to conversation with flag layer=2
    │ COMPLEX ↓
    │     → Query Refinement (de-contextualize + expand)
    ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 3 — Core Processing                                │
│ Model: User-selected from dropdown                       │
│   • Self-hosted: Qwen3-8B (local CPU)                    │
│   • Groq: qwen3-32b, llama-3.3-70b-versatile, ...       │
│   • OpenRouter: multiple models                          │
│   • Gemini: gemini-1.5-flash, gemini-2.0-flash, ...     │
│ → Hybrid RAG (vector + BM25 + rerank)                    │
│ → Generate response                                      │
│ → Auto-generate title (if new conversation)              │
│ → Save with flag layer=3                                 │
└──────────────────────────────────────────────────────────┘
    │ Rate limited → Notify user to switch model
    │ OK → Return response + sources + title (if generated)
    ▼
 Response
```

### 2.2 Context Isolation Strategy

Only `(user_query, assistant_response)` pairs with `processing_layer = 3` are included in the Layer 3 context window. Rationale:

- Layer 2 responses are chitchat/simple answers — they add no value to RAG context.
- Prevents **context poisoning**: a simple Layer 2 answer like "Hello!" can confuse the model when it later processes a complex RAG query.
- Reduces token count in long conversations.

---

## 3. Database Schema — Changes

### 3.1 Add `processing_layer` to `conversation.messages`

**Strategy**: Use the existing `metadata JSONB` column to avoid schema migration. No `ALTER TABLE` needed.

```python
# When saving a message, inject into metadata:

# Layer 2 message:
metadata = {
    "processing_layer": 2,
    "intent": "SIMPLE",
    "layer1_latency_ms": 150,
    "layer2_latency_ms": 320,
}

# Layer 3 message:
metadata = {
    "processing_layer": 3,
    "intent": "COMPLEX",
    "refined_query": "...",
    "layer1_latency_ms": 150,
    "layer2_latency_ms": 280,
    "layer3_latency_ms": 1200,
    "title_generated": True,   # True only for the first message in a conversation
}
```

### 3.2 Filter Context by Layer

```python
# context_builder.py — fetch Layer 3 messages only
async def get_layer3_context(
    self,
    conversation_id: UUID,
    limit: int = 10  # number of Q&A pairs, not individual messages
) -> list[Message]:
    query = """
        SELECT * FROM conversation.messages
        WHERE conversation_id = :conversation_id
          AND role IN ('USER', 'ASSISTANT')
          AND (metadata->>'processing_layer')::int = 3
        ORDER BY created_at DESC
        LIMIT :limit
    """
    # Return in ascending order for the prompt
    return reversed(results)
```

### 3.3 Title Generation Tracking in `conversation.conversations`

The `title` column already exists. Check logic:

```python
# A conversation needs title generation when:
# 1. title IS NULL, OR
# 2. title = 'New Conversation' (frontend default), OR
# 3. title = '' (empty string)

async def needs_title_generation(self, conversation_id: UUID) -> bool:
    conv = await self.conversation_repo.get(conversation_id)
    DEFAULT_TITLES = {None, "", "New Conversation", "Cuộc trò chuyện mới"}
    return conv.title in DEFAULT_TITLES
```

---

## 4. Project Structure — Changes

```
services/ai-qa-service/
├── src/
│   ├── services/
│   │   ├── pipeline/                        # NEW — replaces input_processing/
│   │   │   ├── layer1_toxic_filter.py       # Groq llama-prompt-guard-2-22m
│   │   │   ├── layer2_intent_classifier.py  # Groq llama-3.1-8b-instant
│   │   │   ├── layer2_responder.py          # Answers SIMPLE queries at Layer 2
│   │   │   ├── query_refiner.py             # Query rewriting (COMPLEX path)
│   │   │   └── pipeline_orchestrator.py     # Coordinates all 3 layers
│   │   ├── retrieval/                       # Unchanged from v1
│   │   │   ├── hybrid_search.py
│   │   │   ├── semantic_search.py
│   │   │   └── reranker.py
│   │   ├── generation/
│   │   │   ├── model_registry.py            # NEW — manages multi-model + status
│   │   │   ├── llm_client.py                # Updated: rate limit detection
│   │   │   ├── prompt_builder.py            # Unchanged
│   │   │   ├── stream_generator.py          # Unchanged
│   │   │   └── title_generator.py           # NEW — auto title generation
│   │   ├── conversation/
│   │   │   ├── manager.py                   # Updated: title logic
│   │   │   ├── message_service.py           # Updated: saves layer metadata
│   │   │   └── context_builder.py           # Updated: filters Layer 3 only
│   │   └── knowledge_gap.py                 # Unchanged
│   └── api/
│       └── routes/
│           ├── chat.py                      # Updated: model_id + rate limit response
│           └── models.py                    # Updated: returns status per model
```

**Delete**: `services/input_processing/gateway.py` (Gemini Flash gateway) and the old `services/input_processing/intent_classifier.py`.

**Remove dependency**: `google-generativeai` — Gemini Flash is no longer used as the gateway. Gemini is now called via its OpenAI-compatible endpoint using the `openai` client.

---

## 5. Layer 1 — Toxic Filter

```python
# services/pipeline/layer1_toxic_filter.py

from groq import AsyncGroq

class ToxicFilterService:
    """
    Uses llama-prompt-guard-2-22m — a 22M-param model specialized for prompt safety.
    Very lightweight, low latency, minimal Groq RPD usage.
    Output label: BENIGN or JAILBREAK / INJECTION (toxic).
    """

    TOXIC_LABELS = {"JAILBREAK", "INJECTION"}

    def __init__(self, groq_api_key: str):
        self.client = AsyncGroq(api_key=groq_api_key)

    async def check(self, user_input: str) -> ToxicFilterResult:
        try:
            response = await self.client.chat.completions.create(
                model="meta-llama/llama-prompt-guard-2-22m",
                messages=[{"role": "user", "content": user_input}],
                max_tokens=10,  # Only need a short label
            )
            label = response.choices[0].message.content.strip().upper()
            is_toxic = any(toxic in label for toxic in self.TOXIC_LABELS)

            return ToxicFilterResult(
                is_toxic=is_toxic,
                label=label,
                latency_ms=...,
            )
        except Exception as e:
            # If Layer 1 fails → fail open (allow through), log warning
            logger.warning(f"Layer 1 toxic filter failed: {e}. Failing open.")
            return ToxicFilterResult(is_toxic=False, label="ERROR", error=str(e))


class ToxicFilterResult(BaseModel):
    is_toxic: bool
    label: str
    latency_ms: int = 0
    error: str | None = None
```

**Important notes about `llama-prompt-guard-2-22m`**:
- This model is fine-tuned for prompt safety classification, **not** for general chat responses.
- Output is a label string (`BENIGN` / `JAILBREAK` / `INJECTION`), not a chat reply.
- Groq rate limits for this model are much more generous than for large models — ideal for a filter.
- **Fail-open strategy**: if Groq Layer 1 goes down → allow the query through rather than blocking the entire service.

---

## 6. Layer 2 — Intent Classifier + Simple Responder

### 6.1 Intent Classifier

```python
# services/pipeline/layer2_intent_classifier.py

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier. Analyze the following question and assign it to exactly one of two categories:

[SIMPLE]: Questions that do not require searching specialized documents. Includes:
  - Greetings and small talk (hello, how are you, thank you...)
  - Simple calculations (2+2, basic percentage math...)
  - Common general knowledge questions unrelated to internal documents
  - Requests to explain basic concepts that need no specialized context
  - Questions any ordinary person could answer immediately

[COMPLEX]: Questions that require looking up documents, policies, regulations, or internal data. Includes:
  - Questions about specific policies, procedures, or regulations
  - Questions about internal documentation
  - Questions requiring analysis, comparison, or synthesis
  - Any question that needs a document source to answer accurately

Question: {query}

Recent conversation history (if any):
{recent_history}

Return exactly one label: [SIMPLE] or [COMPLEX]"""


class IntentClassifierService:
    def __init__(self, groq_api_key: str):
        self.client = AsyncGroq(api_key=groq_api_key)

    async def classify(
        self,
        query: str,
        recent_history: list[str] = None  # Context-awareness only, not Layer 3 history
    ) -> IntentResult:
        history_text = self._format_history(recent_history) if recent_history else "None"

        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            query=query,
            recent_history=history_text
        )

        response = await self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,  # Deterministic
        )

        label_text = response.choices[0].message.content.strip().upper()
        intent = "COMPLEX" if "COMPLEX" in label_text else "SIMPLE"

        return IntentResult(intent=intent, raw_label=label_text)
```

### 6.2 Simple Responder (answers directly at Layer 2)

```python
# services/pipeline/layer2_responder.py

class Layer2Responder:
    """
    Reuses llama-3.1-8b-instant (already used in Layer 2) to answer SIMPLE queries.
    No additional API call needed — saves latency and RPD quota.
    No RAG — answers from general knowledge only.
    """

    SIMPLE_RESPONSE_SYSTEM = """You are a helpful AI assistant.
Respond concisely, in a friendly and natural tone.
If the question relates to specific policies, regulations, or internal documents — say you need to look it up and ask the user to rephrase (this handles cases where intent was misclassified).
Never hallucinate specific policy information."""

    def __init__(self, groq_api_key: str):
        self.client = AsyncGroq(api_key=groq_api_key)

    async def respond(self, query: str) -> Layer2Response:
        response = await self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": self.SIMPLE_RESPONSE_SYSTEM},
                {"role": "user", "content": query},
            ],
            max_tokens=256,
            temperature=0.7,
        )
        return Layer2Response(
            content=response.choices[0].message.content,
            model_used="groq/llama-3.1-8b-instant",
        )
```

> **Optimization note**: Some implementations combine intent classification + simple response into a single Groq API call (prompt asks for JSON `{"intent": "SIMPLE", "response": "..."}`). This cuts from 2 calls to 1 for the SIMPLE path. The trade-off is less reliable output — **recommended to keep 2 separate calls for stability**.

### 6.3 Query Refinement (COMPLEX path only)

```python
# services/pipeline/query_refiner.py

REFINEMENT_PROMPT = """You are an expert at improving questions for document retrieval.

Given the original question and conversation history (containing only document-lookup Q&A pairs), do the following:
1. De-contextualize: Rewrite the question so it is self-contained and understandable without conversation context.
2. Expand: Add related keywords to improve search recall.
3. Clarify: Resolve any ambiguity in the question.

Conversation history (Layer 3 only):
{layer3_history}

Original question: {original_query}

Return JSON:
{{
  "refined_query": "the improved question",
  "search_keywords": ["keyword1", "keyword2"],
  "filters_hint": {{"date_range": null, "category": null}}
}}"""


class QueryRefiner:
    def __init__(self, groq_api_key: str):
        self.client = AsyncGroq(api_key=groq_api_key)

    async def refine(
        self,
        original_query: str,
        layer3_history: list[Message],  # Layer 3 messages ONLY
    ) -> RefinedQuery:
        history_text = self._format_layer3_history(layer3_history)
        prompt = REFINEMENT_PROMPT.format(
            layer3_history=history_text,
            original_query=original_query
        )

        response = await self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)
        return RefinedQuery(
            original=original_query,
            refined=data.get("refined_query", original_query),
            keywords=data.get("search_keywords", []),
            filters_hint=data.get("filters_hint", {}),
        )
```

---

## 7. Layer 3 — Core Processing

### 7.1 Pipeline Orchestrator

```python
# services/pipeline/pipeline_orchestrator.py

class PipelineOrchestrator:
    """
    Coordinates the full 3-layer pipeline.
    This is the central service called from the /chat endpoint.
    """

    def __init__(
        self,
        toxic_filter: ToxicFilterService,
        intent_classifier: IntentClassifierService,
        layer2_responder: Layer2Responder,
        query_refiner: QueryRefiner,
        hybrid_search: HybridSearchService,
        model_registry: ModelRegistry,
        title_generator: TitleGenerator,
        conversation_manager: ConversationManager,
        knowledge_gap_detector: KnowledgeGapDetector,
    ):
        ...

    async def process(
        self,
        request: ChatRequest,
        user_context: UserContext,
    ) -> PipelineResult:

        # ── LAYER 1: Toxic Filter ────────────────────────────────
        layer1_result = await self.toxic_filter.check(request.message)
        if layer1_result.is_toxic:
            return PipelineResult(
                status="BLOCKED",
                layer_stopped=1,
                response="Inappropriate content. Please rephrase your question.",
            )

        # ── LAYER 2: Intent Classification ──────────────────────
        # Fetch recent history (any layer) so the classifier understands context
        recent_msgs = await self.conversation_manager.get_recent_messages(
            conversation_id=request.conversation_id,
            limit=4  # Last 2 Q&A pairs — only for classifier context awareness
        )
        intent_result = await self.intent_classifier.classify(
            query=request.message,
            recent_history=recent_msgs
        )

        if intent_result.intent == "SIMPLE":
            layer2_response = await self.layer2_responder.respond(request.message)
            # Save to DB with layer=2
            await self._save_layer2_exchange(
                request, layer2_response, user_context, layer1_result, intent_result
            )
            return PipelineResult(
                status="OK",
                layer_stopped=2,
                response=layer2_response.content,
                model_used=layer2_response.model_used,
                sources=None,
            )

        # ── COMPLEX path: Query Refinement → Layer 3 ────────────

        # Fetch Layer 3 history only for refinement and context
        layer3_history = await self.conversation_manager.get_layer3_context(
            conversation_id=request.conversation_id,
            limit=10  # Last 5 Layer 3 Q&A pairs
        )

        refined = await self.query_refiner.refine(
            original_query=request.message,
            layer3_history=layer3_history
        )

        # ── LAYER 3: RAG + Generation ────────────────────────────
        chunks = await self.hybrid_search.search(
            query=refined.refined,
            user_context=user_context,
            filters=RetrievalFilters(
                document_ids=request.context.document_ids if request.context else None,
                category_ids=request.context.category_ids if request.context else None,
            ),
            limit=10,
        )

        # Knowledge gap detection
        gap_result = await self.knowledge_gap_detector.evaluate(
            query=refined.refined,
            retrieved_chunks=chunks
        )

        # Generate — using user-selected model
        try:
            gen_result = await self.model_registry.generate(
                model_id=request.model_id,
                query=refined.refined,
                original_query=request.message,
                retrieved_chunks=chunks,
                layer3_history=layer3_history,  # Layer 3 context ONLY
            )
        except RateLimitError as e:
            await self.model_registry.mark_rate_limited(request.model_id)
            return PipelineResult(
                status="RATE_LIMITED",
                layer_stopped=3,
                rate_limited_model=request.model_id,
                message=f"Model '{request.model_id}' is rate limited. Please select another model.",
            )

        # Save Layer 3 exchange
        saved = await self._save_layer3_exchange(
            request, refined, gen_result, gap_result,
            user_context, layer1_result, intent_result
        )

        # Auto-generate title (background task — does not block response)
        asyncio.create_task(
            self._maybe_generate_title(
                conversation_id=request.conversation_id,
                user_query=request.message,
                assistant_response=gen_result.content,
            )
        )

        # Publish knowledge gap event if needed
        if gap_result.is_unanswered:
            asyncio.create_task(
                self.knowledge_gap_detector.publish_unanswered(
                    result=gap_result,
                    user_id=user_context.user_id,
                    message_id=saved.message_id,
                    conversation_id=request.conversation_id,
                )
            )

        return PipelineResult(
            status="OK",
            layer_stopped=3,
            response=gen_result.content,
            model_used=gen_result.model_used,
            sources=chunks_to_sources(chunks),
            refined_query=refined.refined,
        )
```

### 7.2 Model Registry with Status Management

```python
# services/generation/model_registry.py

from enum import Enum
from datetime import datetime, timedelta

class ModelStatus(str, Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


class ModelProfile(BaseModel):
    id: str                      # e.g. "local/qwen3-8b", "groq/qwen3-32b"
    name: str                    # Display name for the dropdown
    provider: str                # local, groq, openrouter, gemini
    model_name: str              # Actual model ID sent to the API
    base_url: str
    api_key: str | None
    description: str | None = None
    context_window: int = 8192
    is_default: bool = False
    # Runtime state (not persisted — resets on restart)
    status: ModelStatus = ModelStatus.AVAILABLE
    rate_limited_until: datetime | None = None


# Default model profiles — configurable via env/config
DEFAULT_MODEL_PROFILES = [
    ModelProfile(
        id="local/qwen3-8b",
        name="Qwen3 8B (Local)",
        provider="local",
        model_name="qwen3-8b",
        base_url="http://localhost:8080/v1",
        api_key=None,
        description="Self-hosted, free, best data privacy",
        is_default=True,
    ),
    ModelProfile(
        id="groq/qwen3-32b",
        name="Qwen3 32B (Groq)",
        provider="groq",
        model_name="qwen/qwen3-32b",
        base_url="https://api.groq.com/openai/v1",
        description="More powerful, free on Groq (rate limited)",
    ),
    ModelProfile(
        id="groq/llama-70b",
        name="Llama 3.3 70B (Groq)",
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        description="Large model, high quality (~1,000 RPD)",
    ),
    ModelProfile(
        id="gemini/flash-2",
        name="Gemini 2.0 Flash",
        provider="gemini",
        model_name="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        description="Google Gemini, fast and capable",
    ),
    ModelProfile(
        id="openrouter/mistral-7b",
        name="Mistral 7B (OpenRouter)",
        provider="openrouter",
        model_name="mistralai/mistral-7b-instruct",
        base_url="https://openrouter.ai/api/v1",
        description="Via OpenRouter, many model options",
    ),
]


class ModelRegistry:
    RATE_LIMIT_COOLDOWN = timedelta(minutes=5)  # Auto-resets after 5 minutes

    def __init__(self, profiles: list[ModelProfile]):
        self._profiles: dict[str, ModelProfile] = {p.id: p for p in profiles}

    def get_all(self) -> list[ModelProfile]:
        """Return all models after refreshing their rate limit status."""
        self._refresh_rate_limit_status()
        return list(self._profiles.values())

    def get_available(self) -> list[ModelProfile]:
        self._refresh_rate_limit_status()
        return [p for p in self._profiles.values() if p.status == ModelStatus.AVAILABLE]

    def get(self, model_id: str) -> ModelProfile | None:
        self._refresh_rate_limit_status()
        return self._profiles.get(model_id)

    def mark_rate_limited(self, model_id: str):
        if model_id in self._profiles:
            self._profiles[model_id].status = ModelStatus.RATE_LIMITED
            self._profiles[model_id].rate_limited_until = (
                datetime.utcnow() + self.RATE_LIMIT_COOLDOWN
            )
            logger.warning(f"Model {model_id} marked as RATE_LIMITED for 5 minutes.")

    def _refresh_rate_limit_status(self):
        now = datetime.utcnow()
        for profile in self._profiles.values():
            if (
                profile.status == ModelStatus.RATE_LIMITED
                and profile.rate_limited_until
                and now >= profile.rate_limited_until
            ):
                profile.status = ModelStatus.AVAILABLE
                profile.rate_limited_until = None
                logger.info(f"Model {profile.id} rate limit cooldown expired → AVAILABLE")

    async def generate(
        self,
        model_id: str,
        query: str,
        original_query: str,
        retrieved_chunks: list[RetrievalChunk],
        layer3_history: list[Message],
    ) -> GenerationResult:
        profile = self.get(model_id)
        if not profile:
            profile = self._get_default()
        if profile.status != ModelStatus.AVAILABLE:
            raise RateLimitError(f"Model {model_id} is {profile.status}")

        client = AsyncOpenAI(
            api_key=profile.api_key or "not-needed",
            base_url=profile.base_url,
        )

        messages = self.prompt_builder.build(
            query=query,
            original_query=original_query,
            context_chunks=retrieved_chunks,
            history=layer3_history,  # Layer 3 ONLY
        )

        try:
            response = await client.chat.completions.create(
                model=profile.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
            )
            return GenerationResult(
                content=response.choices[0].message.content,
                model_used=model_id,
                model_name_actual=profile.model_name,
                ...
            )
        except openai.RateLimitError:
            self.mark_rate_limited(model_id)
            raise RateLimitError(f"Model {model_id} hit rate limit")
```

### 7.3 Auto Title Generator

```python
# services/generation/title_generator.py

TITLE_GENERATION_PROMPT = """Based on the following Q&A pair, generate a short title for this conversation.

Requirements:
- Length: 4–10 words
- Style: natural, accurately describes the content (similar to how ChatGPT or Gemini name conversations)
- Language: match the language used by the user
- No quotes, no prefixes like "Title:" or "Conversation:"

Question: {user_query}
Answer (summary): {assistant_summary}

Title:"""


class TitleGenerator:
    def __init__(self, groq_api_key: str):
        self.client = AsyncGroq(api_key=groq_api_key)

    async def generate(
        self,
        user_query: str,
        assistant_response: str,
    ) -> str:
        # Truncate response if too long (avoid wasting tokens)
        summary = assistant_response[:300] if len(assistant_response) > 300 else assistant_response

        prompt = TITLE_GENERATION_PROMPT.format(
            user_query=user_query,
            assistant_summary=summary,
        )

        response = await self.client.chat.completions.create(
            model="llama-3.1-8b-instant",  # 8b-instant is sufficient for title generation
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.5,
        )

        title = response.choices[0].message.content.strip()
        # Sanitize: strip quotes if model adds them anyway
        title = title.strip('"\'')
        return title[:255]  # Ensure it fits the DB column limit


    # Inside PipelineOrchestrator:
    async def _maybe_generate_title(
        self,
        conversation_id: UUID,
        user_query: str,
        assistant_response: str,
    ):
        """Runs in the background — does not block the response."""
        try:
            needs_title = await self.conversation_manager.needs_title_generation(conversation_id)
            if not needs_title:
                return

            title = await self.title_generator.generate(user_query, assistant_response)
            await self.conversation_manager.update_title(conversation_id, title)
            logger.info(f"Title generated for conversation {conversation_id}: '{title}'")
        except Exception as e:
            # Title generation failure must NOT affect user experience
            logger.error(f"Title generation failed for {conversation_id}: {e}")
```

---

## 8. API Endpoints — Updates

### 8.1 GET /models — Returns per-model status

```python
class AIModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    description: str | None
    context_window: int
    is_default: bool
    status: ModelStatus      # NEW: available | rate_limited | unavailable
    rate_limited_until: datetime | None = None  # NEW: when the rate limit will expire

class ModelListResponse(BaseModel):
    models: list[AIModelResponse]
```

Frontend uses `status` to:
- Grey out `rate_limited` models in the dropdown
- Show a tooltip like "Available again at HH:MM" using `rate_limited_until`

### 8.2 POST /chat — Extended response

```python
class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    model_id: str = "local/qwen3-8b"  # From dropdown; defaults to local
    context: ChatContext | None = None

class ChatResponse(BaseModel):
    # Unchanged from v1
    message: Message
    conversation: Conversation
    sources: list[SourceDocument] | None = None
    # NEW
    processing_layer: int          # 1, 2, or 3
    model_used: str | None         # None if blocked at Layer 1
    refined_query: str | None      # Query after refinement (Layer 3 only)

class RateLimitResponse(BaseModel):
    """Returned when the selected model is rate limited at Layer 3."""
    status: Literal["RATE_LIMITED"] = "RATE_LIMITED"
    message: str                   # "Model X is rate limited. Please select another model."
    rate_limited_model: str
    available_models: list[str]    # Suggested available alternatives
```

**HTTP status codes**:
- `200 OK` — success (layer 2 or 3)
- `200 OK` with body `status="BLOCKED"` — blocked at Layer 1
- `429 Too Many Requests` — model rate limited (with `RateLimitResponse` body)

> **Note**: Using HTTP 429 for rate limits makes it easy for the frontend to intercept and render the appropriate UI.

### 8.3 POST /chat/stream — SSE with metadata event

```
event: metadata
data: {"processing_layer": 3, "model_used": "local/qwen3-8b", "refined_query": "..."}

event: token
data: {"content": "According to "}

event: token
data: {"content": "the policy..."}

event: sources
data: {"sources": [...]}

event: title
data: {"title": "Remote Work Policy Guidelines"}  ← NEW: sent after title is generated

event: done
data: {"total_tokens": 423, "latency_ms": 1850}
```

---

## 9. Environment Configuration — Updates

```env
# ══════════════════════════════════════════
# LAYER 1 & 2 — Groq (Pipeline Layers)
# ══════════════════════════════════════════
GROQ_API_KEY=gsk_your_groq_api_key_here

# Layer 1 — Toxic Filter
LAYER1_MODEL=meta-llama/llama-prompt-guard-2-22m
LAYER1_FAIL_OPEN=true        # true = allow through if Groq Layer 1 is down

# Layer 2 — Intent Classifier + Simple Responder
LAYER2_MODEL=llama-3.1-8b-instant
LAYER2_MAX_TOKENS_CLASSIFY=10
LAYER2_MAX_TOKENS_RESPOND=256

# ══════════════════════════════════════════
# LAYER 3 — Model Registry
# ══════════════════════════════════════════
DEFAULT_MODEL_ID=local/qwen3-8b

# Local self-hosted model
LOCAL_LLM_BASE_URL=http://localhost:8080/v1
LOCAL_LLM_MODEL_NAME=qwen3-8b

# Groq (Layer 3 models)
# GROQ_API_KEY already declared above — shared

# OpenRouter
OPENROUTER_API_KEY=sk-or-your_key_here

# Gemini (OpenAI-compatible endpoint)
GEMINI_API_KEY=your_gemini_key_here

# Rate limit cooldown (minutes)
MODEL_RATE_LIMIT_COOLDOWN_MINUTES=5

# ══════════════════════════════════════════
# TITLE GENERATION
# ══════════════════════════════════════════
TITLE_GENERATION_ENABLED=true
TITLE_DEFAULT_PATTERNS=New Conversation,Cuộc trò chuyện mới,  # Treated as "no title yet"

# ══════════════════════════════════════════
# CONTEXT ISOLATION
# ══════════════════════════════════════════
CONTEXT_LAYER3_ONLY=true       # Use only Layer 3 messages for RAG context
MAX_LAYER3_CONTEXT_PAIRS=5     # Max Layer 3 Q&A pairs in context window

# ══════════════════════════════════════════
# UNCHANGED FROM v1
# ══════════════════════════════════════════
HOST=0.0.0.0
PORT=8086
LOG_LEVEL=info
DATABASE_URL=postgresql+asyncpg://poliwise:poliwise_secure_password@postgres:5432/poliwise
DATABASE_SCHEMA=conversation
RABBITMQ_URL=amqp://poliwise:poliwise_secure_password@rabbitmq:5672
RABBITMQ_EXCHANGE=poliwise.events
EMBEDDING_URL=http://bge-m3-embedding:80
RERANKER_URL=http://reranker:8002
RETRIEVAL_LIMIT=10
RERANK_LIMIT=5
SIMILARITY_THRESHOLD=0.3
USE_RERANKER=false
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60
MAX_HISTORY_MESSAGES=20
CONVERSATION_TITLE_MAX_LENGTH=255
```

---

## 10. Dependencies — Updates

```toml
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

    # LLM Clients
    "openai>=1.50.0",       # OpenAI-compatible: Groq Layer 3, OpenRouter, local, Gemini
    "groq>=0.11.0",         # NEW: Groq SDK for Layers 1 & 2 (better async support)

    # HTTP Client
    "httpx>=0.27.0",

    # Observability
    "structlog>=24.1.0",
    "prometheus-client>=0.21.0",
]

# REMOVED: "google-generativeai>=0.8.0" — Gemini is no longer used as the gateway.
# Gemini is now called via its OpenAI-compatible endpoint → use the openai client.
```

---

## 11. Docker Compose — Updates

```yaml
ai-qa-service:
  environment:
    # Layer 1 & 2
    GROQ_API_KEY: ${GROQ_API_KEY}
    LAYER1_MODEL: meta-llama/llama-prompt-guard-2-22m
    LAYER2_MODEL: llama-3.1-8b-instant

    # Layer 3 — Local
    LOCAL_LLM_BASE_URL: ${LOCAL_LLM_BASE_URL:-http://host.docker.internal:8080/v1}
    LOCAL_LLM_MODEL_NAME: ${LOCAL_LLM_MODEL_NAME:-qwen3-8b}
    DEFAULT_MODEL_ID: ${DEFAULT_MODEL_ID:-local/qwen3-8b}

    # Layer 3 — Remote APIs
    OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
    GEMINI_API_KEY: ${GEMINI_API_KEY:-}

    # Title Generation
    TITLE_GENERATION_ENABLED: "true"

    # Unchanged from v1...
    HOST: 0.0.0.0
    PORT: 8086
    DATABASE_URL: postgresql+asyncpg://...
    EMBEDDING_URL: http://bge-m3-embedding:80
    RABBITMQ_URL: amqp://...
```

---

## 12. Implementation Checklist v2

### Phase 1: Project Setup (unchanged from v1)
- [ ] FastAPI app, database session, health check
- [ ] Gateway header extraction

### Phase 2: 3-Layer Pipeline (NEW — replaces old Phase 2)
- [ ] **Layer 1**: Implement `ToxicFilterService` with `llama-prompt-guard-2-22m`
  - [ ] Async Groq client
  - [ ] Fail-open fallback
  - [ ] Unit tests with toxic + clean inputs
- [ ] **Layer 2**: Implement `IntentClassifierService` with `llama-3.1-8b-instant`
  - [ ] Prompt engineering for SIMPLE/COMPLEX classification
  - [ ] Unit tests with diverse query types
- [ ] **Layer 2**: Implement `Layer2Responder`
  - [ ] System prompt for simple responses
  - [ ] Must not hallucinate policy information
- [ ] **Query Refiner**: De-contextualize + expand (uses Layer 3 history only)
- [ ] **PipelineOrchestrator**: Wire everything together with proper error handling
- [ ] End-to-end pipeline tests

### Phase 3: Model Registry (NEW)
- [ ] Implement `ModelRegistry` with default model profiles
- [ ] Status management: `AVAILABLE` / `RATE_LIMITED` / `UNAVAILABLE`
- [ ] Rate limit detection from `openai.RateLimitError`
- [ ] Auto-reset after cooldown period
- [ ] `GET /models` endpoint returning per-model status
- [ ] Configure model profiles via env vars

### Phase 4: Core API (updated from v1)
- [ ] `POST /chat` with `model_id` field
- [ ] `POST /chat/stream` with metadata + title SSE events
- [ ] HTTP 429 response for rate limits
- [ ] `RateLimitResponse` body with list of available models

### Phase 5: RAG (unchanged from v1)
- [ ] Semantic search with RBAC
- [ ] BM25 full-text search
- [ ] RRF fusion
- [ ] Optional reranker

### Phase 6: Title Generation (NEW)
- [ ] Implement `TitleGenerator`
- [ ] `needs_title_generation()` check logic
- [ ] Background task via `asyncio.create_task` — must not block response
- [ ] SSE `title` event for streaming
- [ ] Test: title generation only runs when conversation has no title yet

### Phase 7: Context Isolation (NEW)
- [ ] Save `processing_layer` in message metadata
- [ ] `get_layer3_context()` filter in `context_builder.py`
- [ ] Verify: Layer 2 messages do not appear in Layer 3 context

### Phase 8: Conversation Management (updated from v1)
- [ ] Save messages with layer metadata
- [ ] `update_title()` method
- [ ] `needs_title_generation()` with default title pattern matching

### Phase 9: Knowledge Gap Detection (unchanged from v1)
- [ ] Similarity threshold detection
- [ ] Unanswered question storage
- [ ] RabbitMQ publish

### Phase 10: Integration & Testing
- [ ] End-to-end pipeline test (all 3 paths: TOXIC, SIMPLE, COMPLEX)
- [ ] Rate limit simulation test
- [ ] Title generation integration test
- [ ] Load test: ensure Layers 1+2 do not introduce meaningful bottleneck

---

## 13. Groq Rate Limit Budget (Reference)

| Model | Used for | Free Tier (estimated) | Notes |
|---|---|---|---|
| `llama-prompt-guard-2-22m` | Layer 1 | Very high | Small model, generous limits |
| `llama-3.1-8b-instant` | Layer 2 (classify + respond + refine + title) | ~14,400 RPD | Shared across all Layer 2 tasks |
| `qwen/qwen3-32b` | Layer 3 (if user selects) | ~1,000 RPD | User-controlled |
| `llama-3.3-70b-versatile` | Layer 3 (if user selects) | ~1,000 RPD | User-controlled |

**Layer 2 budget estimate**: 14,400 RPD ÷ 4 calls/request (classify + respond/refine + title) ≈ **3,600 SIMPLE requests/day** before further optimization is needed. For COMPLEX requests, Layer 2 only uses 2 calls (classify + refine), not 4.

**Optional optimization**: Combine title generation into the same call as Layer 3 generation (prompt the Layer 3 model to return JSON `{response: ..., title: ...}`). Saves ~1 Groq call per COMPLEX request.

---

## 14. Key Design Decisions

### 14.1 Why remove Gemini Flash as the gateway?

v1 used Gemini Flash as an all-in-one "brain" (safety + intent + rewrite in a single call). This approach:
- Created a hard dependency on a single provider (Google AI Studio)
- Made individual steps hard to test in isolation
- Made tuning difficult: changing one task affected all three tasks in the same prompt

v2 splits into 3 specialized layers → easier to optimize, debug, and replace each layer independently.

### 14.2 Why use `metadata JSONB` instead of a new column?

Avoids a schema migration in production. `processing_layer` is an implementation detail — it doesn't need to be a first-class DB column. If more complex queries are needed in the future, a generated column or index on `(metadata->>'processing_layer')` can be added then.

### 14.3 Is context isolation actually necessary?

**Recommendation: Yes, keep it.** Reasons:
- Layer 2 responses are short and generic (greetings, simple math) — including them in RAG context wastes tokens.
- Worse: a Layer 2 response like "2 + 2 = 4" in the context of a complex RAG query about company policy can confuse the model.
- For long conversations (20+ turns), filtering significantly reduces context window usage.

If you want to simplify early on: set `CONTEXT_LAYER3_ONLY=false` — the context builder will include all messages like v1. Can be re-enabled later with no code changes.

### 14.4 Why a 5-minute rate limit cooldown?

Groq rate limit windows are typically 1 minute (RPM) or 1 day (RPD). A 5-minute cooldown is a conservative value that ensures the RPM window has reset. In production, monitor the Groq `x-ratelimit-reset-requests` response header and use the actual reset time instead of a hardcoded value.

---

## 15. Unchanged from v1

The following sections are **unchanged from v1.1** — refer to the original document:

- **Section 6.1** Retrieval Service (Hybrid Search) — SQL, RRF fusion, RBAC filtering
- **Section 6.2** Reranker Service
- **Section 6.4** RAG Prompt Template (minor update to accept `layer3_history`)
- **Section 6.6** Unanswered Question Detection
- **Section 7** API Endpoints (except `/models` and `/chat` updated above)
- **Section 8** Event-Driven Integration (RabbitMQ)
- **Section 13** API Gateway Integration
- **Database schemas** — no changes; uses existing `metadata JSONB`
