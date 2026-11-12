"""LLM provider for generation and rewrite (TECH-V2-ai-service §4.2, §7.1; V2-10 milestone 2).

One adapter: OpenAI-compatible chat completions (vLLM on Modal, ADR-006 §4.4). Endpoint, model id
and key come from ``config/models.yaml`` and the environment; no model id is written in code.

- :class:`OpenAICompatibleLLM` talks to one endpoint (``complete`` or ``stream``).
- :class:`RateLimiter` enforces RPM and TPM over a sliding minute.
- :class:`LLMChain` tries providers in order. It falls back only before the first ``delta``;
  after that a failure is ``LLM_UNAVAILABLE`` and nothing is switched.
- :func:`check_model` reads ``/models`` at startup and warns when the configured model is missing.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog

from sopilot_ai.providers.registry import ModelsConfig

log = structlog.get_logger(__name__)

Message = Mapping[str, str]


class LLMError(Exception):
    """Provider failure. ``code`` is the stable client-facing code (TECH §7.2)."""

    def __init__(self, code: str = "LLM_UNAVAILABLE") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class LLMSpec:
    provider: str  # key under ``providers`` in models.yaml, e.g. "modal"
    model: str
    base_url: str
    api_key: str | None = field(repr=False)  # never in repr() or a log line
    rpm: int
    tpm: int
    context_max_tokens: int | None
    temperature: float
    max_output_tokens: int
    extra_body: dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Conservative prompt-size estimate: one token per two characters.

    TECH §7.4 asks for the active model's own tokenizer when declared. Until one is wired, this
    over-estimates (Vietnamese text is roughly 3-4 characters per token), so it never lets an
    oversized prompt through the context ceiling.
    """
    return math.ceil(len(text) / 2)


class RateLimiter:
    """Sliding one-minute window of requests and tokens. Waits for a slot, up to ``max_wait``."""

    def __init__(self, rpm: int, tpm: int, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, max_wait: float = 30.0) -> None:
        if rpm <= 0 or tpm <= 0:
            raise ValueError("rpm and tpm must be positive")
        self.rpm, self.tpm = rpm, tpm
        self._clock, self._sleep, self._max_wait = clock, sleep, max_wait
        self._events: list[tuple[float, int]] = []
        self._lock = threading.Lock()

    def acquire(self, tokens: int) -> None:
        if tokens > self.tpm:
            raise LLMError("RATE_LIMITED")
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                self._events = [e for e in self._events if now - e[0] < 60.0]
                used = sum(t for _, t in self._events)
                if len(self._events) < self.rpm and used + tokens <= self.tpm:
                    self._events.append((now, tokens))
                    return
                wait = 60.0 - (now - self._events[0][0]) if self._events else 1.0
            wait = max(wait, 0.05)
            if waited + wait > self._max_wait:
                raise LLMError("RATE_LIMITED")
            self._sleep(wait)
            waited += wait


class OpenAICompatibleLLM:
    """``POST {base_url}/chat/completions`` and ``GET {base_url}/models``."""

    def __init__(self, spec: LLMSpec, *, transport: Any = None, timeout: float = 120.0) -> None:
        import httpx

        self.spec = spec
        headers = {"Authorization": f"Bearer {spec.api_key}"} if spec.api_key else {}
        self._client = httpx.Client(base_url=spec.base_url.rstrip("/"), headers=headers,
                                    timeout=timeout, transport=transport)

    def _body(self, messages: Sequence[Message], *, stream: bool,
              temperature: float | None = None) -> dict[str, Any]:
        body: dict[str, Any] = dict(self.spec.extra_body)
        body.update({
            "model": self.spec.model,
            "messages": [dict(m) for m in messages],
            "temperature": self.spec.temperature if temperature is None else temperature,
            "max_tokens": self.spec.max_output_tokens,
            "stream": stream,
        })
        return body

    def complete(self, messages: Sequence[Message], *, temperature: float | None = None) -> str:
        import httpx

        try:
            resp = self._client.post("/chat/completions",
                                     json=self._body(messages, stream=False,
                                                     temperature=temperature))
            _raise_for_status(resp.status_code)
            return str(resp.json()["choices"][0]["message"]["content"] or "")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError,
                AttributeError) as exc:
            raise LLMError("LLM_UNAVAILABLE") from exc

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        """Yield text deltas. Errors before the first delta are raised as :class:`LLMError`."""
        import httpx

        try:
            with self._client.stream("POST", "/chat/completions",
                                     json=self._body(messages, stream=True)) as resp:
                _raise_for_status(resp.status_code)
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        return
                    text = _delta_text(payload)
                    if text:
                        yield text
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError,
                AttributeError) as exc:
            raise LLMError("LLM_UNAVAILABLE") from exc

    def list_models(self) -> set[str]:
        import httpx

        try:
            resp = self._client.get("/models")
            _raise_for_status(resp.status_code)
            return {str(m["id"]) for m in resp.json()["data"]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise LLMError("LLM_UNAVAILABLE") from exc


def _delta_text(payload: str) -> str:
    """Text of one SSE ``data:`` event; a malformed event is ``LLM_UNAVAILABLE``."""
    obj = json.loads(payload)
    if not isinstance(obj, dict):
        raise LLMError("LLM_UNAVAILABLE")
    choices = obj["choices"]
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LLMError("LLM_UNAVAILABLE")
    delta = choices[0].get("delta")
    if delta is None:
        return ""
    if not isinstance(delta, dict):
        raise LLMError("LLM_UNAVAILABLE")
    return str(delta.get("content") or "")


def _raise_for_status(status: int) -> None:
    if status == 429:
        raise LLMError("RATE_LIMITED")
    if status >= 400:
        raise LLMError("LLM_UNAVAILABLE")


def check_model(client: OpenAICompatibleLLM) -> bool:
    """Startup check (V2-10): warn, do not fail, when the model is not served."""
    try:
        served = client.list_models()
    except LLMError:
        log.warning("llm_models_unreachable", provider=client.spec.provider)
        return False
    if client.spec.model not in served:
        log.warning("llm_model_missing", provider=client.spec.provider, model=client.spec.model)
        return False
    return True


class LLMChain:
    """Providers for one task, tried in order. Fallback only before the first delta (V2-10)."""

    def __init__(self, entries: Sequence[tuple[OpenAICompatibleLLM, RateLimiter]]) -> None:
        if not entries:
            raise ValueError("an LLM chain needs at least one provider")
        self._entries = list(entries)

    @property
    def clients(self) -> list[OpenAICompatibleLLM]:
        return [client for client, _ in self._entries]

    @property
    def context_budget(self) -> int | None:
        """Smallest context ceiling in the chain: build the prompt for this, not the first model."""
        caps = [c.spec.context_max_tokens for c, _ in self._entries
                if c.spec.context_max_tokens is not None]
        return min(caps) if caps else None

    def _eligible(self, tokens: int) -> list[tuple[OpenAICompatibleLLM, RateLimiter]]:
        out = []
        for client, limiter in self._entries:
            cap = client.spec.context_max_tokens
            if cap is None or tokens <= cap:
                out.append((client, limiter))
        if not out:
            raise LLMError("LLM_UNAVAILABLE")
        return out

    def stream(self, messages: Sequence[Message], *, tokens: int,
               on_start: Callable[[str], None] | None = None) -> Iterator[str]:
        """``on_start(model)`` runs once, when the first delta arrives: the model that answers."""
        last: LLMError | None = None
        for client, limiter in self._eligible(tokens):
            try:
                limiter.acquire(tokens)
            except LLMError as exc:
                last = exc
                continue
            started = False
            gen = client.stream(messages)
            try:
                for delta in gen:
                    if not started and on_start is not None:
                        on_start(client.spec.model)
                    started = True
                    yield delta
                return
            except LLMError as exc:
                if started:  # never switch model after the first delta
                    raise LLMError("LLM_UNAVAILABLE") from exc
                last = exc
            finally:
                gen.close()  # releases the HTTP connection when the consumer stops early
        raise last or LLMError("LLM_UNAVAILABLE")

    def complete(self, messages: Sequence[Message], *, tokens: int,
                 temperature: float | None = None,
                 on_start: Callable[[str], None] | None = None) -> str:
        last: LLMError | None = None
        for client, limiter in self._eligible(tokens):
            try:
                limiter.acquire(tokens)
                out = client.complete(messages, temperature=temperature)
                if on_start is not None:
                    on_start(client.spec.model)
                return out
            except LLMError as exc:
                last = exc
        raise last or LLMError("LLM_UNAVAILABLE")


def _spec_from(entry: Mapping[str, Any], endpoint: Mapping[str, Any], section: Mapping[str, Any],
               env_key: str | None, provider: str) -> LLMSpec:
    base_url = str(endpoint.get("base_url") or "")
    model = str(entry.get("model") or "")
    if not base_url:
        raise ValueError(f"providers.{provider}.base_url is empty (set SOPILOT_LLM_BASE_URL)")
    if not model:
        raise ValueError(f"llm model for provider {provider} is empty (set SOPILOT_LLM_MODEL)")
    cap = entry.get("context_max_tokens")
    return LLMSpec(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=env_key or None,
        rpm=int(entry.get("rpm") or 60),
        tpm=int(entry.get("tpm") or 200_000),
        context_max_tokens=None if cap in (None, "") else int(cap),
        temperature=float(section.get("temperature", 0.0)),
        max_output_tokens=int(section.get("max_output_tokens", 800)),
        extra_body=dict(entry.get("extra_body") or {}),
    )


def build_chain(config: ModelsConfig, task: str, *, transport: Any = None) -> LLMChain:
    """Build the chain of one task (``generate`` or ``rewrite``) from ``models.yaml``.

    ``config`` is loaded from the process environment (``${VAR}`` expansion), and the key is read
    from the environment too, so one source defines everything.
    """
    section = config.raw["llm"][task]
    # Optional per-task HTTP timeout (V2-25 suggestions use 20 s); other tasks keep the default.
    timeout = float(section.get("timeout_s", 120.0))
    entries = []
    for entry in section["chain"]:
        provider = str(entry["provider"])
        endpoint = config.provider_endpoint(provider)
        key_name = endpoint.get("api_key_env")
        key = os.environ.get(str(key_name), "") if key_name else ""
        spec = _spec_from(entry, endpoint, section, key, provider)
        client = OpenAICompatibleLLM(spec, transport=transport, timeout=timeout)
        entries.append((client, RateLimiter(spec.rpm, spec.tpm)))
    return LLMChain(entries)
