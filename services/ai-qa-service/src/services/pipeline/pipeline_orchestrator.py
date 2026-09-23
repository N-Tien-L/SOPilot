from typing import Any, Optional
from uuid import UUID
import asyncio
import structlog
from pydantic import BaseModel

from .layer1_toxic_filter import ToxicFilterService, ToxicFilterResult
from .layer2_intent_classifier import IntentClassifierService, IntentResult
from .layer2_responder import Layer2Responder, Layer2Response
from .query_refiner import QueryRefiner, RefinedQuery

logger = structlog.get_logger(__name__)


class PipelineResult(BaseModel):
    status: str
    layer_stopped: int
    response: Optional[str] = None
    model_used: Optional[str] = None
    sources: Optional[list[Any]] = None
    refined_query: Optional[str] = None
    rate_limited_model: Optional[str] = None
    message: Optional[str] = None
    chunks: Optional[list[Any]] = None
    gap_result: Optional[Any] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None
    latency_ms: Optional[int] = None
    confidence: Optional[str] = None
    is_unanswered: bool = False


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
        hybrid_search: Any,
        llm_client: Any,
        prompt_builder: Any,
        conversation_service: Any,
        message_repository: Any,
        knowledge_gap_detector: Any,
        reranker_service: Optional[Any] = None,
        settings: Optional[Any] = None,
    ):
        self.toxic_filter = toxic_filter
        self.intent_classifier = intent_classifier
        self.layer2_responder = layer2_responder
        self.query_refiner = query_refiner
        self.hybrid_search = hybrid_search
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.conversation_service = conversation_service
        self.message_repository = message_repository
        self.knowledge_gap_detector = knowledge_gap_detector
        self.reranker_service = reranker_service
        self.settings = settings

    def _detect_and_translate_warning(self, message: str) -> str:
        """Detect user language and return appropriate warning message."""
        vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")
        if any(c in vietnamese_chars for c in message.lower()):
            return "Tin nhắn của bạn chứa nội dung không phù hợp. Vui lòng diễn đạt lại câu hỏi."
        return "Your message contains inappropriate content. Please rephrase your question."

    async def _save_layer2_exchange(
        self, conversation_id: UUID, response: Layer2Response, model_requested: str = "default"
    ) -> Any:
        """Save Layer 2 (simple) response to conversation history."""
        return await self.conversation_service.add_message(
            conversation_id,
            role="ASSISTANT",
            content=response.content,
            model_used=response.model_used,
            latency_ms=response.latency_ms,
            has_sources=False,
            is_layer2_response=True,
            metadata={"model_requested": model_requested}
        )

    async def _save_layer3_exchange(
        self,
        conversation_id: UUID,
        content: str,
        sources: list[Any],
        model_used: str,
        tokens_prompt: int,
        tokens_completion: int,
        tokens_total: int,
        latency_ms: int,
        has_sources: bool,
        confidence: str,
        model_requested: str = "default",
    ) -> Any:
        """Save Layer 3 (RAG) response to conversation history."""
        return await self.conversation_service.add_message(
            conversation_id,
            role="ASSISTANT",
            content=content,
            sources=[s.model_dump() for s in sources] if sources else [],
            model_used=model_used,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_total,
            latency_ms=latency_ms,
            has_sources=has_sources,
            confidence=confidence,
            metadata={"model_requested": model_requested}
        )

    async def _maybe_generate_title(
        self, conversation_id: UUID, user_query: str, assistant_response: str
    ):
        """Auto-generate conversation title from first exchange using LLM."""
        if not self.settings or not self.settings.title_generation_enabled:
            return

        try:
            from .title_generator import TitleGenerator
            tg = TitleGenerator(
                groq_api_key=self.settings.groq_api_key,
                model=getattr(self.settings, "layer2_model", "llama-3.3-70b-versatile")
            )
            title = await tg.generate(user_query, assistant_response)
            
            if title:
                await self.conversation_service.conv_repo.update_title(conversation_id, title)
                logger.info("conversation_title_auto_generated", conversation_id=str(conversation_id), title=title)
        except Exception as e:
            logger.error("failed_to_auto_generate_title", error=str(e), conversation_id=str(conversation_id))



    async def process(
        self,
        request: Any,
        user_context: Any,
    ) -> PipelineResult:
        """Execute the full 3-layer pipeline."""

        # ── LAYER 1: Toxic Filter ────────────────────────────────
        layer1_result = await self.toxic_filter.check(request.message)
        if layer1_result.is_toxic:
            logger.warning("toxic_query_blocked", user_id=str(user_context.user_id), label=layer1_result.label)
            return PipelineResult(
                status="BLOCKED",
                layer_stopped=1,
                response="Inappropriate content. Please rephrase your question.",
            )

        # ── LAYER 2: Intent Classification ──────────────────────
        recent_msgs = await self.message_repository.get_by_conversation(
            request.conversation_id, user_context.user_id, limit=4,
            exclude_layer2=True, exclude_toxic=True
        ) if request.conversation_id else []
        recent_history = [msg.content for msg in recent_msgs] if recent_msgs else None

        intent_result = await self.intent_classifier.classify(
            query=request.message,
            recent_history=recent_history,
        )

        if intent_result.intent == "SIMPLE":
            layer2_response = await self.layer2_responder.respond(request.message)
            await self._save_layer2_exchange(
                request.conversation_id, layer2_response, model_requested=getattr(request, "model_id", "default")
            )
            return PipelineResult(
                status="OK",
                layer_stopped=2,
                response=layer2_response.content,
                model_used=layer2_response.model_used,
                latency_ms=layer2_response.latency_ms,
            )

        # ── COMPLEX path: Query Refinement → Layer 3 ────────────
        # Load conversation history for the query refiner (de-contextualize follow-up questions)
        layer3_history = []
        if request.conversation_id:
            history_limit = self.settings.query_refiner_history_limit if self.settings else 10
            layer3_history = await self.message_repository.get_by_conversation(
                request.conversation_id, user_context.user_id, limit=history_limit,
                exclude_layer2=True, exclude_toxic=True
            )

        refined = await self.query_refiner.refine(
            original_query=request.message,
            layer3_history=layer3_history,
        )
        search_query = refined.refined

        # Build filters
        filters = None
        if hasattr(request, "context") and request.context:
            from ...models.retrieval import RetrievalFilters
            filters = RetrievalFilters(
                document_ids=request.context.document_ids,
                category_ids=request.context.category_ids,
            )

        # Hybrid search
        chunks = await self.hybrid_search.search(
            query=search_query,
            user_id=str(user_context.user_id),
            user_role=user_context.role,
            user_department_id=str(user_context.department_id) if user_context.department_id else None,
            filters=filters,
            limit=self.settings.retrieval_limit if self.settings else 10,
        )

        # Reranker
        if self.reranker_service and self.settings and self.settings.use_reranker:
            chunks = await self.reranker_service.rerank(
                search_query, chunks, self.settings.rerank_limit
            )

        # Knowledge gap detection
        gap_result = await self.knowledge_gap_detector.evaluate(search_query, chunks)

        # Get conversation history for LLM context
        messages = await self.message_repository.get_by_conversation(
            request.conversation_id, user_context.user_id, limit=20,
            exclude_layer2=True, exclude_toxic=True
        )
        history = [
            {"role": "user" if m.role.value == "USER" else "assistant", "content": m.content}
            for m in messages
        ]

        # Build prompt and generate
        messages_for_llm = self.prompt_builder.build(
            query=request.message,
            context_chunks=chunks,
            history=history,
        )

        metadata = {}
        content, prompt_tokens, completion_tokens, total_tokens, latency = await self.llm_client.generate(
            messages=messages_for_llm,
            model_id=getattr(request, "model_id", "default"),
            metadata=metadata,
        )

        # Strip thinking tags
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # Build sources
        has_sources = len(chunks) > 0
        sources_data = None
        if has_sources:
            from src.api.routes.chat import build_sources
            sources_data = await build_sources(chunks)

        # Compute confidence
        confidence = (
            "HIGH" if gap_result.top_similarity >= 0.7
            else "MEDIUM" if gap_result.top_similarity >= 0.4
            else "LOW"
        )

        # Save to conversation history
        assistant_msg = await self._save_layer3_exchange(
            conversation_id=request.conversation_id,
            content=content,
            sources=sources_data or [],
            model_used=metadata.get("model_used", getattr(request, "model_id", "default")),
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            tokens_total=total_tokens,
            latency_ms=latency,
            has_sources=has_sources,
            confidence=confidence,
            model_requested=getattr(request, "model_id", "default"),
        )

        # Auto-generate title (background)
        if request.conversation_id:
            asyncio.create_task(
                self._maybe_generate_title(
                    conversation_id=request.conversation_id,
                    user_query=request.message,
                    assistant_response=content,
                )
            )

        # Publish unanswered question event if needed
        if gap_result.is_unanswered:
            await self.knowledge_gap_detector.publish_unanswered(
                gap_result,
                user_context.user_id,
                request.conversation_id,
                request.message,
                message_id=assistant_msg.id if assistant_msg else None,
                user_department_id=user_context.department_id,
                user_role=user_context.role,
            )

        return PipelineResult(
            status="OK",
            layer_stopped=3,
            response=content,
            model_used=metadata.get("model_used", getattr(request, "model_id", "default")),
            sources=sources_data,
            refined_query=refined.refined,
            chunks=chunks,
            gap_result=gap_result,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
            tokens_total=total_tokens,
            latency_ms=latency,
            confidence=confidence,
            is_unanswered=gap_result.is_unanswered,
        )

    async def process_stream(
        self,
        request: Any,
        user_context: Any,
    ):
        """Execute the pipeline for streaming response. Yields content chunks."""
        import re
        import time
        import json

        # ── LAYER 1: Toxic Filter ────────────────────────────────
        layer1_result = await self.toxic_filter.check(request.message)
        if layer1_result.is_toxic:
            logger.warning("toxic_query_blocked_stream", user_id=str(user_context.user_id), label=layer1_result.label)
            # Mark the last USER message as toxic
            if request.conversation_id:
                await self.message_repository.mark_last_user_message_toxic(
                    request.conversation_id, user_context.user_id
                )
                # Detect user language and send appropriate warning
                warning_msg = self._detect_and_translate_warning(request.message)
                # Save ASSISTANT warning message to DB
                await self.message_repository.create(
                    conversation_id=request.conversation_id,
                    role="ASSISTANT",
                    content=warning_msg,
                    model_used="system",
                    tokens_prompt=0,
                    tokens_completion=0,
                    tokens_total=0,
                    latency_ms=0,
                )
            yield f"data: {json.dumps({'conversationId': str(request.conversation_id)})}\n\n"
            yield f"data: {json.dumps({'content': warning_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ── LAYER 2: Intent Classification ──────────────────────
        recent_msgs = await self.message_repository.get_by_conversation(
            request.conversation_id, user_context.user_id, limit=4,
            exclude_layer2=True, exclude_toxic=True
        ) if request.conversation_id else []
        recent_history = [msg.content for msg in recent_msgs] if recent_msgs else None

        intent_result = await self.intent_classifier.classify(
            query=request.message,
            recent_history=recent_history,
        )

        if intent_result.intent == "SIMPLE":
            layer2_response = await self.layer2_responder.respond(request.message)
            await self._save_layer2_exchange(
                request.conversation_id, layer2_response, model_requested=getattr(request, "model_id", "default")
            )
            if request.conversation_id:
                asyncio.create_task(
                    self._maybe_generate_title(
                        conversation_id=request.conversation_id,
                        user_query=request.message,
                        assistant_response=layer2_response.content,
                    )
                )
            yield f"data: {json.dumps({'conversationId': str(request.conversation_id)})}\n\n"
            yield f"data: {json.dumps({'content': layer2_response.content})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ── COMPLEX path: Query Refinement → Layer 3 ────────────
        # Load conversation history for the query refiner (de-contextualize follow-up questions)
        layer3_history = []
        if request.conversation_id:
            history_limit = self.settings.query_refiner_history_limit if self.settings else 10
            layer3_history = await self.message_repository.get_by_conversation(
                request.conversation_id, user_context.user_id, limit=history_limit,
                exclude_layer2=True, exclude_toxic=True
            )

        refined = await self.query_refiner.refine(
            original_query=request.message,
            layer3_history=layer3_history,
        )
        search_query = refined.refined

        filters = None
        if hasattr(request, "context") and request.context:
            from ...models.retrieval import RetrievalFilters
            filters = RetrievalFilters(
                document_ids=request.context.document_ids,
                category_ids=request.context.category_ids,
            )

        chunks = await self.hybrid_search.search(
            query=search_query,
            user_id=str(user_context.user_id),
            user_role=user_context.role,
            user_department_id=str(user_context.department_id) if user_context.department_id else None,
            filters=filters,
            limit=self.settings.retrieval_limit if self.settings else 10,
        )

        if self.reranker_service and self.settings and self.settings.use_reranker:
            chunks = await self.reranker_service.rerank(
                search_query, chunks, self.settings.rerank_limit
            )

        gap_result = await self.knowledge_gap_detector.evaluate(search_query, chunks)

        has_sources = len(chunks) > 0
        sources_data = None
        if has_sources:
            from src.api.routes.chat import build_sources
            sources_data = await build_sources(chunks)

        messages = await self.message_repository.get_by_conversation(
            request.conversation_id, user_context.user_id, limit=20,
            exclude_layer2=True, exclude_toxic=True
        )
        history = [
            {"role": "user" if m.role.value == "USER" else "assistant", "content": m.content}
            for m in messages
        ]

        messages_for_llm = self.prompt_builder.build(
            query=request.message,
            context_chunks=chunks,
            history=history,
        )

        # Stream generation
        full_content = ""
        start_time = time.time()

        yield f"data: {json.dumps({'conversationId': str(request.conversation_id)})}\n\n"

        if sources_data:
            yield f"data: {json.dumps({'sources': [s.model_dump(mode='json') for s in sources_data]})}\n\n"

        try:
            in_thinking = False
            buffer = ""
            metadata = {}

            first_chunk = True
            async for chunk_content in self.llm_client.generate_streaming(
                messages=messages_for_llm,
                model_id=getattr(request, "model_id", "default"),
                temperature=0.3,
                max_tokens=1024,
                metadata=metadata,
            ):
                if first_chunk:
                    first_chunk = False
                    if "model_used" in metadata:
                        yield f"data: {json.dumps({'modelUsed': metadata['model_used']})}\n\n"
                buffer += chunk_content
                if not in_thinking:
                    if "<think" in buffer:
                        in_thinking = True
                        buffer = ""
                        continue
                    yield f"data: {json.dumps({'content': chunk_content})}\n\n"
                    full_content += chunk_content
                else:
                    if "</think>" in buffer:
                        in_thinking = False
                        buffer = ""
                    else:
                        buffer = ""

            full_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL).strip()
            latency_ms = int((time.time() - start_time) * 1000)

            confidence = (
                "HIGH" if gap_result.top_similarity >= 0.7
                else "MEDIUM" if gap_result.top_similarity >= 0.4
                else "LOW"
            )

            assistant_msg = await self._save_layer3_exchange(
                conversation_id=request.conversation_id,
                content=full_content,
                sources=sources_data or [],
                model_used=metadata.get("model_used", getattr(request, "model_id", "default")),
                tokens_prompt=0,
                tokens_completion=0,
                tokens_total=0,
                latency_ms=latency_ms,
                has_sources=has_sources,
                confidence=confidence,
                model_requested=getattr(request, "model_id", "default"),
            )

            if gap_result.is_unanswered:
                await self.knowledge_gap_detector.publish_unanswered(
                    gap_result,
                    user_context.user_id,
                    request.conversation_id,
                    request.message,
                    message_id=assistant_msg.id if assistant_msg else None,
                    user_department_id=user_context.department_id,
                    user_role=user_context.role,
                )

            if request.conversation_id:
                asyncio.create_task(
                    self._maybe_generate_title(
                        conversation_id=request.conversation_id,
                        user_query=request.message,
                        assistant_response=full_content,
                    )
                )

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("streaming_generation_failed", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
