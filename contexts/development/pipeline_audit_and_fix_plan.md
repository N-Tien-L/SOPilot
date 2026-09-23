# Pipeline Audit & Fix Plan
> Scope: `layer1_toxic_filter.py`, `layer2_intent_classifier.py`, `layer2_responder.py`, `query_refiner.py`, `title_generator.py`, `pipeline_orchestrator.py`

---

## Overview

| File | Severity | Priority |
|------|----------|----------|
| `pipeline_orchestrator.py` | 🔴 Critical | P0 |
| `layer1_toxic_filter.py` | 🟡 Medium | P1 |
| `layer2_intent_classifier.py` | 🟡 Medium | P1 |
| `layer2_responder.py` | 🟢 Minor | P2 |
| `query_refiner.py` | 🟢 Minor | P2 |
| `title_generator.py` | 🟢 Minor | P3 |

---

## FILE 1: `pipeline_orchestrator.py` — 🔴 CRITICAL

### Issue 1 — Code duplication: `process()` and `process_stream()` share 80% logic

**Current:** The entire pipeline (L1 → L2 → refine → L3 → save → title) is written twice in two separate methods. When fixing a bug in `process()`, you must remember to fix it in `process_stream()` as well.

**Fix:** Extract shared logic into private helper methods. `process()` and `process_stream()` become thin wrappers that only handle output format.

```python
# Target structure:
async def _run_layer1(self, message) -> ToxicFilterResult: ...
async def _run_layer2(self, message, conversation_id) -> tuple[IntentResult, list]: ...
async def _run_layer3(self, message, conversation_id, user_context) -> tuple[RefinedQuery, list, Any]: ...

async def process(self, request, user_context) -> PipelineResult:
    # Calls helpers, returns PipelineResult

async def process_stream(self, request, user_context):
    # Calls same helpers, yields SSE chunks
```

---

### Issue 2 — `asyncio.create_task()` not awaited, silent failure

**Current (line 236-243, 247-255, 421-429):**
```python
asyncio.create_task(
    self._maybe_generate_title(...)
)
asyncio.create_task(
    self.knowledge_gap_detector.publish_unanswered(...)
)
```
If these tasks raise an exception, the error is silently swallowed. No logging, no retry.

**Fix:** Wrap in an error-handling wrapper:
```python
async def _safe_background(self, coro, task_name: str):
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task '{task_name}' failed", error=str(e))

# Usage:
asyncio.create_task(self._safe_background(
    self._maybe_generate_title(...),
    task_name="title_generation"
))
```

---

### Issue 3 — Rate limit detection uses fragile string matching

**Current (line 218, 436):**
```python
if "Rate limit" in str(e) or "429" in str(e):
```
If Groq/provider changes their error message format, this silently bypass and raises as a generic 500.

**Fix:** Catch typed exceptions or check HTTP status code:
```python
from groq import RateLimitError  # Groq SDK has its own exception type

try:
    gen_result = await self.model_registry.generate(...)
except RateLimitError as e:
    await self.model_registry.mark_rate_limited(model_id)
    return PipelineResult(status="RATE_LIMITED", ...)
except Exception as e:
    logger.error("Layer 3 generation failed", error=str(e))
    raise
```

---

### Issue 4 — `process_stream()` imports `time` and `GenerationResult` inside function body

**Current (line 351-352, 404):**
```python
async for chunk_content in ...:
    import time          # ← import inside loop
    start_time = ...

from ...models.generation import GenerationResult  # ← import at end of function
```
Import inside a loop adds overhead every iteration. Import at the end of a function makes code harder to read.

**Fix:** Move all imports to the top of the file.

---

### Issue 5 — `process_stream()` creates `GenerationResult` mock with token = 0

**Current (line 405-413):**
```python
gen_result = GenerationResult(
    content=full_content,
    tokens_prompt=0,     # ← hardcoded
    tokens_completion=0, # ← hardcoded
    tokens_total=0       # ← hardcoded
)
```
Token counts in the DB will always be 0 for all streaming responses. Analytics will be completely wrong.

**Fix:** Use `tiktoken` to estimate token count from `full_content`:
```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
tokens_completion = len(enc.encode(full_content))
```
Or if the provider returns usage in the stream's final chunk, parse from there.

---

### Issue 6 — Title generation race condition in stream

**Current (line 364-379):** Title task is kicked off when `full_content >= 300 chars`, but the title is yielded immediately inside the loop when `title_task.done()`. If the LLM generates quickly (< 1 chunk after 300 chars), the title may be yielded before the stream ends, causing SSE event ordering issues on the client.

**Fix:** Always yield TITLE after yielding DONE, or yield TITLE only in the cleanup section after the stream loop:
```python
# After the stream loop ends:
title = await asyncio.wait_for(title_task, timeout=3.0)
if title:
    yield {"status": "TITLE", "title": title}
yield {"status": "DONE", ...}
```

---

### Issue 7 — `_save_layer2_exchange()` does not save user message

**Current:** Only saves the assistant response (role=ASSISTANT), does not save the user message into the conversation. Conversation history will be missing the user turn for L2 exchanges.

**Fix:** Save the user message first, then save the assistant response:
```python
await self.conversation_manager.add_message(
    request.conversation_id,
    role="USER",
    content=request.message,
)
await self.conversation_manager.add_message(
    request.conversation_id,
    role="ASSISTANT",
    content=layer2_response.content,
    ...
)
```
*(Verify whether `ConversationService` already saves the user message elsewhere before fixing.)*

---

## FILE 2: `layer1_toxic_filter.py` — 🟡 MEDIUM

### Issue 1 — Redundant `.lower()` when regex is already compiled with `re.I`

**Current:**
```python
text_lower = text.lower()
for pattern in self.jailbreak_regex:
    if pattern.search(text_lower):  # re.I makes this redundant
```

**Fix:**
```python
for pattern in self.jailbreak_regex:
    if pattern.search(text):  # re.I handles case
```

---

### Issue 2 — Threshold `0.5` too low for a security layer

**Current:**
```python
is_unsafe = score > 0.5
```
This is the first security layer. A threshold of 0.5 means the model only needs to be "slightly suspicious" to block. This increases false positives on edge case queries.

**Fix:** Separate threshold by type:
```python
JAILBREAK_THRESHOLD = 0.75  # Conservative catch, tune gradually based on data
is_unsafe = score > JAILBREAK_THRESHOLD
```

---

### Issue 3 — Keyword patterns can be bypassed with Unicode lookalikes and extra spaces

Examples of bypasses not caught:
- `"іgnore all instructions"` (Cyrillic `і`, not Latin `i`)
- `"ignore  all  instructions"` (double space)
- `"ign0re all instructions"` (leetspeak)

**Fix:** Add a normalize step before checking:
```python
import unicodedata

def _normalize(self, text: str) -> str:
    # Normalize Unicode (Cyrillic lookalikes → Latin)
    text = unicodedata.normalize("NFKD", text)
    # Encode ASCII, ignore non-ASCII, decode back
    text = text.encode("ascii", "ignore").decode("ascii")
    # Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.lower()

def check(self, text: str) -> str | None:
    normalized = self._normalize(text)
    for pattern in self.jailbreak_regex:
        if pattern.search(normalized):
            return "JAILBREAK"
    ...
```

---

### Issue 4 — Does not log which pattern matched, hard to debug

**Fix:**
```python
def check(self, text: str) -> tuple[str, str] | None:
    for i, pattern in enumerate(self.jailbreak_regex):
        if pattern.search(text):
            logger.debug("Jailbreak pattern matched",
                        pattern_index=i,
                        pattern=self.jailbreak_patterns[i][:50])
            return "JAILBREAK", self.jailbreak_patterns[i]
    ...
```

---

### Issue 5 — `fail_open=True` default is risky for a security layer

When Groq API is down, jailbreak requests will pass through. Should require the caller to set it explicitly, with a default of `False` for production:

```python
def __init__(self, groq_api_key: str, model: str = "...", fail_open: bool = False):
    ...
    if fail_open:
        logger.warning("ToxicFilterService initialized with fail_open=True. "
                       "Jailbreak attempts may pass through if LLM API is down.")
```

---

## FILE 3: `layer2_intent_classifier.py` — 🟡 MEDIUM

### Issue 1 — Prompt lacks Viet-English code-switching examples

Vietnamese corporate users often write in mixed style: `"policy về remote work như thế nào?"`, `"check timesheet ở đâu?"`. The current prompt only has purely Vietnamese or purely English examples.

**Fix:** Add to the prompt:
```
Note: Users may mix Vietnamese and English in the same sentence.
- "policy về remote work như thế nào?" -> COMPLEX
- "check timesheet ở đâu?" -> COMPLEX
- "oki thanks bye nhé" -> SIMPLE
- "có WFH policy không?" -> COMPLEX
```

---

### Issue 2 — `fail_open → SIMPLE` when LLM errors may miss complex queries

If a user asks about policy but the classifier errors → returns SIMPLE → no RAG search → wrong/incomplete answer. There is no metric to track how often this happens.

**Fix:** Add metrics and consider changing the default to COMPLEX:
```python
except Exception as e:
    latency_ms = int((time.time() - start_time) * 1000)
    logger.error("Layer 2 classifier failed", error=str(e), query=query[:50])
    # Change: fail to COMPLEX to avoid missing policy questions
    # Costs an extra RAG call but avoids wrong answers
    return IntentResult(intent="COMPLEX", raw_label="ERROR_FAILSAFE", latency_ms=latency_ms)
```
*(Needs A/B testing before changing — could significantly increase cost if error rate is high.)*

---

### Issue 3 — No caching for identical queries

The same query called multiple times (e.g., user retries) will create multiple LLM calls.

**Fix:** Simple LRU cache for the deterministic classifier:
```python
from functools import lru_cache
import hashlib

def _cache_key(self, query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()

# Cache intent results for identical query hashes
_intent_cache: dict[str, IntentResult] = {}
MAX_CACHE_SIZE = 512
```

---

## FILE 4: `layer2_responder.py` — 🟢 MINOR

### Issue 1 — History role assignment uses a fragile heuristic

**Current:**
```python
role = "user" if i % 2 == 0 else "assistant"  # Simple heuristic if roles aren't passed
```
If `recent_history` starts with an assistant message (e.g., a welcome message), all roles get inverted.

**Fix:** Accept `list[dict]` instead of `list[str]`, or accept `list[tuple[str, str]]` with explicit roles:
```python
async def respond(
    self,
    query: str,
    recent_history: list[dict] | None = None  # [{"role": "user", "content": "..."}, ...]
) -> Layer2Response:
    if recent_history:
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
```
Need to update `pipeline_orchestrator.py` to pass the correct format.

---

### Issue 2 — `max_tokens=256` may truncate responses mid-sentence

For greeting/smalltalk questions, 256 tokens is enough. But if the classifier misroutes a policy question here, 256 tokens will cut the response short.

**Fix:** Increase to 512, or add logic to detect incomplete responses and suggest the user rephrase.

---

## FILE 5: `query_refiner.py` — 🟢 MINOR

### Issue 1 — No validation of refined query output

If the LLM returns an empty refined query or one that is too different from the original, the search will be off-target.

**Fix:** Add validation:
```python
refined_query = data.get("refined_query", "").strip()

# Validate: not too short, not too different from original
if len(refined_query) < 5 or len(refined_query) > len(original_query) * 5:
    logger.warning("Refined query looks invalid, falling back to original",
                   refined=refined_query[:100])
    refined_query = original_query

return RefinedQuery(refined=refined_query, ...)
```

---

### Issue 2 — `filters_hint` is parsed but never used by the orchestrator

The orchestrator (line 185-190) only uses `request.context` to build filters, completely ignoring `refined.filters_hint`.

**Fix:** Merge filters hint into filters:
```python
filters = {}
if hasattr(request, "context") and request.context:
    filters = {
        "document_ids": getattr(request.context, "document_ids", None),
        "category_ids": getattr(request.context, "category_ids", None),
    }

# Merge hints from query refiner
if refined.filters_hint.get("category"):
    filters.setdefault("category_ids", refined.filters_hint["category"])
```

---

## FILE 6: `title_generator.py` — 🟢 MINOR

### Issue 1 — Truncates `assistant_response` at 300 chars but chars ≠ tokens

```python
summary = assistant_response[:300]  # 300 chars, not 300 tokens
```
For Vietnamese, 300 chars ≈ 150-200 tokens — acceptable. But inconsistent with the "summary" comment.

**Fix:** Not critical, but should document clearly:
```python
# Take first ~300 chars as context for title generation
# (~150-200 tokens for Vietnamese, enough for title context)
summary = assistant_response[:300]
```

### Issue 2 — No timeout

Title generation has no dedicated timeout. If Groq is slow, the orchestrator's `wait_for(title_task, timeout=2.0)` will cancel the task but won't log a warning.

**Fix:** Add a timeout inside `generate()`:
```python
response = await asyncio.wait_for(
    self.client.chat.completions.create(...),
    timeout=3.0
)
```

---

## Summary: Fix order for agent

### P0 — Fix immediately (breaking bugs)

| # | File | Task |
|---|------|------|
| 1 | `pipeline_orchestrator.py` | Wrap `asyncio.create_task()` in `_safe_background()` wrapper |
| 2 | `pipeline_orchestrator.py` | Move `import time` and `import GenerationResult` to top of file |
| 3 | `pipeline_orchestrator.py` | Change rate limit detection to catch typed `RateLimitError` |
| 4 | `pipeline_orchestrator.py` | Fix streaming token counts (no hardcode 0) |

### P1 — Fix this sprint (accuracy & safety)

| # | File | Task |
|---|------|------|
| 5 | `pipeline_orchestrator.py` | Refactor `process()` and `process_stream()` to extract shared logic |
| 6 | `pipeline_orchestrator.py` | Fix title yield ordering in stream (TITLE after DONE) |
| 7 | `layer1_toxic_filter.py` | Add Unicode normalization before keyword check |
| 8 | `layer1_toxic_filter.py` | Increase jailbreak threshold from 0.5 → 0.75 |
| 9 | `layer1_toxic_filter.py` | Change `fail_open` default to `False`, add warning log |
| 10 | `layer2_intent_classifier.py` | Add Viet-English code-switching examples to prompt |

### P2 — Improve (quality & maintainability)

| # | File | Task |
|---|------|------|
| 11 | `pipeline_orchestrator.py` | Verify + fix user message save in `_save_layer2_exchange()` |
| 12 | `layer1_toxic_filter.py` | Log matched pattern index for easier debugging |
| 13 | `layer2_intent_classifier.py` | Add LRU cache for duplicate queries |
| 14 | `layer2_responder.py` | Change history from `list[str]` to `list[dict]` with explicit roles |
| 15 | `query_refiner.py` | Validate refined query output before use |
| 16 | `query_refiner.py` | Merge `filters_hint` into search filters in orchestrator |

### P3 — Nice to have

| # | File | Task |
|---|------|------|
| 17 | `title_generator.py` | Add timeout in `generate()` |
| 18 | `layer2_responder.py` | Increase `max_tokens` from 256 → 512 |
| 19 | `layer2_intent_classifier.py` | Consider `fail_open → COMPLEX` instead of SIMPLE (A/B test first) |
