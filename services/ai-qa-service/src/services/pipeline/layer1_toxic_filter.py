from pydantic import BaseModel
import structlog
import asyncio
from groq import AsyncGroq

logger = structlog.get_logger(__name__)


class ToxicFilterResult(BaseModel):
    is_toxic: bool
    label: str  # JAILBREAK | INJECTION | TOXIC | HARMFUL | SAFE
    jailbreak_score: float | None = None  # llama-prompt-guard score
    toxic_score: float | None = None      # llama-guard-3 score
    latency_ms: int = 0
    error: str | None = None

# =============================================================================
# Toxic Filter Service - Layer 1 Safety
# =============================================================================

class ToxicLLMDetector:
    """
    Toxic/abusive content detector using llama-3.1-8b-instant.
    
    Returns categories: TOXIC, HATE_SPEECH, VIOLENCE, SELF_HARM, SEXUAL, WEAPONS, SAFE
    
    If response contains any unsafe category → is_toxic = True
    """

    def __init__(
        self,
        groq_api_key: str,
        model: str = "llama-3.1-8b-instant",
        threshold: float = 0.5,
        fail_open: bool = True,
    ):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.model = model
        self.threshold = threshold
        self.fail_open = fail_open

    async def check(self, text: str) -> tuple[bool, float, str | None]:
        """
        Returns (is_toxic, score, unsafe_category)
        - is_toxic: True if any unsafe category detected
        - score: confidence 0.0-1.0
        - unsafe_category: category ID if unsafe, None otherwise
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a content safety classifier. Analyze the user input and respond with ONLY ONE category code:\n"
                            "O1 - Safe: The input is safe, respectful, and appropriate.\n"
                            "O2 - Toxic: The input contains profanity, insults, or abusive language.\n"
                            "O3 - Hate Speech: The input is hateful or discriminatory toward a group.\n"
                            "O4 - Self-Harm: The input promotes self-harm or suicide.\n"
                            "O5 - Sexual: The input is sexually inappropriate.\n"
                            "O6 - Violence: The input promotes violence or physical harm.\n"
                            "O7 - Weapons: The input discusses weapons or dangerous items.\n"
                            "O8 - Deception: The input is deceptive or manipulative.\n\n"
                            "Respond with ONLY the category code (e.g., O1, O2). No explanation."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=5,
                temperature=0.0,
            )
            raw = response.choices[0].message.content.strip()
            
            # Parse response
            if raw.startswith("O1"):
                return False, 0.0, None
            elif raw.startswith("O2"):
                return True, 1.0, "TOXIC"
            elif raw.startswith("O3"):
                return True, 1.0, "HATE_SPEECH"
            elif raw.startswith("O4"):
                return True, 1.0, "SELF_HARM"
            elif raw.startswith("O5"):
                return True, 1.0, "SEXUAL"
            elif raw.startswith("O6"):
                return True, 1.0, "VIOLENCE"
            elif raw.startswith("O7"):
                return True, 1.0, "WEAPONS"
            elif raw.startswith("O8"):
                return True, 1.0, "DECEPTION"
            else:
                # Unknown format - treat as unsafe if contains keywords
                is_unsafe = any(x in raw.upper() for x in [
                    "O2", "O3", "O4", "O5", "O6", "O7", "O8",
                    "TOXIC", "UNSAFE", "HARMFUL", "DANGEROUS"
                ])
                return is_unsafe, 1.0 if is_unsafe else 0.0, raw if is_unsafe else None

        except Exception as e:
            logger.warning(f"Toxic LLM check failed: {e}")
            if self.fail_open:
                return False, 0.0, None
            return True, 1.0, "ERROR"


# =============================================================================
# Toxic Filter Service - Layer 1 Safety
# =============================================================================

class ToxicFilterService:
    """
    Layer 1 - Safety Filter (Same for EN and VI):
    
    1. llama-prompt-guard-2-86m → JAILBREAK / INJECTION
    2. llama-guard-3-8b → TOXIC / HARMFUL / HATE_SPEECH / VIOLENCE / ...
    
    Both models run in parallel for optimal latency.
    """
    
    def __init__(
        self,
        groq_api_key: str,
        jailbreak_model: str = "meta-llama/llama-prompt-guard-2-86m",
        toxic_model: str = "meta-llama/llama-guard-3-8b",
        fail_open: bool = True,
    ):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.jailbreak_model = jailbreak_model
        self.fail_open = fail_open
        self.toxic_detector = ToxicLLMDetector(
            groq_api_key=groq_api_key,
            model=toxic_model,
            fail_open=fail_open,
        )

    async def check(self, user_input: str) -> ToxicFilterResult:
        """
        Run both safety checks in parallel:
        1. llama-prompt-guard-2-86m → JAILBREAK / INJECTION
        2. llama-guard-3-8b → TOXIC / HARMFUL / HATE_SPEECH / VIOLENCE / ...
        """
        import time
        start_time = time.time()
        
        # Run both LLM checks in parallel
        jailbreak_task = self._check_jailbreak(user_input)
        toxic_task = self.toxic_detector.check(user_input)
        
        jailbreak_result, toxic_result = await asyncio.gather(
            jailbreak_task, toxic_task,
            return_exceptions=True
        )
        
        # Parse jailbreak result
        if isinstance(jailbreak_result, Exception):
            logger.warning(f"Jailbreak check failed: {jailbreak_result}")
            jailbreak_unsafe = False
            jailbreak_score = 0.0
        else:
            jailbreak_unsafe, jailbreak_score = jailbreak_result
        
        # Parse toxic result
        if isinstance(toxic_result, Exception):
            logger.warning(f"Toxic check failed: {toxic_result}")
            toxic_unsafe = False
            toxic_score = 0.0
            toxic_category = "ERROR"
        else:
            toxic_unsafe, toxic_score, toxic_category = toxic_result
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Combine: if either is unsafe, block
        is_combined_unsafe = jailbreak_unsafe or toxic_unsafe
        
        if jailbreak_unsafe:
            combined_label = "JAILBREAK"
        elif toxic_unsafe:
            combined_label = toxic_category or "TOXIC"
        else:
            combined_label = "SAFE"
        
        logger.info(">>> LAYER 1: Safety check",
                    input=user_input[:50],
                    jailbreak_unsafe=jailbreak_unsafe,
                    jailbreak_score=jailbreak_score,
                    toxic_unsafe=toxic_unsafe,
                    toxic_category=toxic_category,
                    combined_label=combined_label,
                    latency_ms=latency_ms)
        
        return ToxicFilterResult(
            is_toxic=is_combined_unsafe,
            label=combined_label,
            jailbreak_score=jailbreak_score,
            toxic_score=toxic_score,
            latency_ms=latency_ms,
        )
    
    async def _check_jailbreak(self, user_input: str) -> tuple[bool, float]:
        """Check jailbreak/injection using llama-prompt-guard-2-86m."""
        try:
            response = await self.client.chat.completions.create(
                model=self.jailbreak_model,
                messages=[{"role": "user", "content": user_input}],
                max_tokens=20,
                temperature=0.0,
            )
            raw = response.choices[0].message.content.strip()
            try:
                score = float(raw)
                return score > 0.5, score
            except ValueError:
                is_unsafe = any(x in raw.upper() for x in ["JAILBREAK", "INJECTION", "UNSAFE"])
                return is_unsafe, 1.0 if is_unsafe else 0.0
        except Exception as e:
            logger.warning(f"Jailbreak check failed: {e}")
            return self.fail_open, 0.0