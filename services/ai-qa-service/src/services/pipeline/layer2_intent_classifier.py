from pydantic import BaseModel
from groq import AsyncGroq
import structlog

logger = structlog.get_logger(__name__)

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an AI policy assistant.
Your task: Classify the user query as [SIMPLE] or [COMPLEX].

[SIMPLE]: Questions that DO NOT require searching internal documents.
If an ordinary person without special knowledge could answer confidently, it is SIMPLE.
Examples:
- "Hello, how are you?" -> SIMPLE
- "What is 2 + 2?" -> SIMPLE
- "Thank you, goodbye!" -> SIMPLE
- "Who is the CEO of this company?" -> SIMPLE (general knowledge)
- "I hate you, you are bad" -> SIMPLE (emotional feedback, any person can respond)
- "Tôi ghét bạn" -> SIMPLE (venting, no document needed)
- "What's the weather today?" -> SIMPLE
- "What are you? Who made you?" -> SIMPLE (bot meta-talk)
- "Thanks, bye!" -> SIMPLE (closing talk)
- "How does it work?" -> SIMPLE (too vague, no document needed)
- "Can you help me?" -> SIMPLE (generic help)
- "How do I do this?" -> SIMPLE (no context)
- "oki thanks bye nhé" -> SIMPLE (viet-english closing)
- "hello bạn, help me với vấn đề này" -> SIMPLE (viet-english greeting)

[COMPLEX]: Questions that REQUIRE searching internal documents/policies.
If you would need to look up a document/policy to answer correctly, it is COMPLEX.
Examples:
- "What is our company's remote work policy?" -> COMPLEX
- "How many vacation days am I entitled to?" -> COMPLEX
- "What are the expense reimbursement procedures?" -> COMPLEX
- "What are the security requirements for passwords?" -> COMPLEX
- "How do I request time off?" -> COMPLEX
- "What is the dress code?" -> COMPLEX (company-specific)
- "Can I work from home?" -> COMPLEX (requires company policy)
- "How many sick days do I have?" -> COMPLEX (requires HR policy)
- "What is the travel policy?" -> COMPLEX (company rules)
- "What is the policy?" -> COMPLEX (explicit policy keyword)
- "Tell me about our company" -> COMPLEX (company-specific)
- "What are the rules?" -> COMPLEX (likely company rules)
- "What benefits do I get?" -> COMPLEX (benefits = likely company)
- "Who is the CEO of our company?" -> COMPLEX (company-specific CEO)

Note: Users may mix Vietnamese and English in the same sentence.
- "policy về remote work như thế nào?" -> COMPLEX
- "check timesheet ở đâu?" -> COMPLEX
- "có WFH policy không?" -> COMPLEX
- "cách submit expense report thế nào?" -> COMPLEX
- "có bao nhiêu ngày phép per year?" -> COMPLEX

Rule: If an ordinary person without special knowledge could answer confidently -> SIMPLE.
If you would need to look up a document/policy to answer correctly -> COMPLEX.

User Query: {query}

Recent conversation:
{recent_history}

Return ONLY one word: [SIMPLE] or [COMPLEX]"""

class IntentResult(BaseModel):
    intent: str
    raw_label: str
    latency_ms: int = 0

class IntentClassifierService:
    def __init__(self, groq_api_key: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 10,
                 fallback_intent: str = "COMPLEX"):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.fallback_intent = fallback_intent

    def _format_history(self, recent_history: list[str] | None) -> str:
        if not recent_history:
            return "None"
        return "\n".join(recent_history)

    async def classify(
        self,
        query: str,
        recent_history: list[str] | None = None  # Context-awareness only, not Layer 3 history
    ) -> IntentResult:
        import time
        start_time = time.time()
        
        history_text = self._format_history(recent_history)

        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            query=query,
            recent_history=history_text
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=0.0,  # Deterministic
            )
            latency_ms = int((time.time() - start_time) * 1000)

            label_text = response.choices[0].message.content.strip().upper()
            intent = "COMPLEX" if "COMPLEX" in label_text else "SIMPLE"

            logger.info(">>> LAYER 2 DEBUG:", 
                        input=query[:50], 
                        groq_raw_response=label_text, 
                        final_intent=intent,
                        latency_ms=latency_ms)

            return IntentResult(intent=intent, raw_label=label_text, latency_ms=latency_ms)
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Layer 2 intent classifier failed: {e}. Defaulting to {self.fallback_intent} (fail-safe).")
            return IntentResult(intent=self.fallback_intent, raw_label="ERROR_FAILSAFE", latency_ms=latency_ms)
