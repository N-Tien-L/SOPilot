"""LLM provider (V2-10 milestone 2): wire format, rate limits, fallback before the first delta.

No network: the HTTP side is an ``httpx.MockTransport``; provider failures are a fake client.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from sopilot_ai.providers.llm import (
    LLMChain,
    LLMError,
    LLMSpec,
    OpenAICompatibleLLM,
    RateLimiter,
    build_chain,
    check_model,
    estimate_tokens,
)
from sopilot_ai.providers.registry import ModelsConfig

MODELS = Path(__file__).resolve().parents[2] / "config" / "models.yaml"


def spec(**overrides) -> LLMSpec:
    base = dict(provider="modal", model="qwen-test", base_url="http://llm.test/v1", api_key="k",
                rpm=60, tpm=200_000, context_max_tokens=None, temperature=0.2,
                max_output_tokens=800,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    base.update(overrides)
    return LLMSpec(**base)


def sse(*deltas: str) -> bytes:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': d}}]})}\n\n" for d in deltas]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def client_with(handler, **overrides) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(spec(**overrides), transport=httpx.MockTransport(handler))


# --- wire format ------------------------------------------------------------------------------


def test_stream_yields_deltas_and_sends_the_expected_body():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse("Xin ", "chào"))

    out = list(client_with(handler).stream([{"role": "user", "content": "hi"}]))
    assert out == ["Xin ", "chào"]
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    body = seen["body"]
    assert body["model"] == "qwen-test" and body["stream"] is True
    assert body["temperature"] == 0.2 and body["max_tokens"] == 800
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


def test_extra_body_cannot_override_model_or_messages():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = client_with(handler, extra_body={"model": "evil", "messages": []})
    client.complete([{"role": "user", "content": "q"}])
    assert seen["body"]["model"] == "qwen-test"
    assert seen["body"]["messages"] == [{"role": "user", "content": "q"}]


def test_complete_returns_the_message_content_and_accepts_temperature_zero():
    seen = {}

    def handler(request):
        seen["temperature"] = json.loads(request.content)["temperature"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "viết lại"}}]})

    assert client_with(handler).complete([{"role": "user", "content": "x"}],
                                         temperature=0) == "viết lại"
    assert seen["temperature"] == 0


def test_no_auth_header_without_a_key():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"id": "m"}]})

    client_with(handler, api_key=None).list_models()
    assert seen["auth"] is None


@pytest.mark.parametrize("status, code", [(429, "RATE_LIMITED"), (500, "LLM_UNAVAILABLE"),
                                          (404, "LLM_UNAVAILABLE")])
def test_http_errors_map_to_stable_codes(status, code):
    client = client_with(lambda r: httpx.Response(status))
    with pytest.raises(LLMError) as err:
        list(client.stream([{"role": "user", "content": "q"}]))
    assert err.value.code == code


def test_a_network_error_is_llm_unavailable():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMError) as err:
        client_with(handler).complete([{"role": "user", "content": "q"}])
    assert err.value.code == "LLM_UNAVAILABLE"


def test_list_models_reads_the_served_ids():
    client = client_with(lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]}))
    assert client.list_models() == {"a", "b"}


def test_check_model_returns_false_when_missing_or_unreachable():
    present = client_with(lambda r: httpx.Response(200, json={"data": [{"id": "qwen-test"}]}))
    gone = client_with(lambda r: httpx.Response(200, json={"data": [{"id": "other"}]}))
    down = client_with(lambda r: httpx.Response(500))
    assert check_model(present) is True
    assert check_model(gone) is False
    assert check_model(down) is False


# --- rate limits ------------------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.now += seconds


def test_rpm_limit_waits_for_the_window_to_free_a_slot():
    clock = FakeClock()
    limiter = RateLimiter(rpm=2, tpm=10_000, clock=clock, sleep=clock.sleep, max_wait=120.0)
    limiter.acquire(10)
    limiter.acquire(10)
    limiter.acquire(10)  # third request in the same minute waits
    assert clock.slept == pytest.approx(60.0, abs=1.0)


def test_tpm_limit_counts_tokens_in_the_window():
    clock = FakeClock()
    limiter = RateLimiter(rpm=100, tpm=100, clock=clock, sleep=clock.sleep, max_wait=120.0)
    limiter.acquire(60)
    limiter.acquire(40)
    limiter.acquire(10)  # 110 > 100: waits until the first 60 leave the window
    assert clock.slept == pytest.approx(60.0, abs=1.0)


def test_a_limit_that_would_take_longer_than_max_wait_is_rate_limited():
    clock = FakeClock()
    limiter = RateLimiter(rpm=1, tpm=10_000, clock=clock, sleep=clock.sleep, max_wait=5.0)
    limiter.acquire(1)
    with pytest.raises(LLMError) as err:
        limiter.acquire(1)
    assert err.value.code == "RATE_LIMITED"


def test_a_request_larger_than_the_tpm_is_refused_at_once():
    limiter = RateLimiter(rpm=10, tpm=100, sleep=lambda s: pytest.fail("must not wait"))
    with pytest.raises(LLMError):
        limiter.acquire(101)


# --- chain: fallback only before the first delta ---------------------------------------------


class FakeLLM:
    """Stands in for a client: scripted deltas, optionally failing after ``fail_after`` deltas."""

    def __init__(self, name, deltas=(), *, fail_before=None, fail_after=None, cap=None):
        self.name = name
        self.deltas = list(deltas)
        self.fail_before = fail_before
        self.fail_after = fail_after
        self.calls = 0
        self.spec = spec(provider=name, context_max_tokens=cap)

    def stream(self, messages):
        self.calls += 1
        if self.fail_before:
            raise LLMError(self.fail_before)
        for i, d in enumerate(self.deltas):
            if self.fail_after is not None and i == self.fail_after:
                raise LLMError("RATE_LIMITED")
            yield d

    def complete(self, messages, *, temperature=None):
        self.calls += 1
        if self.fail_before:
            raise LLMError(self.fail_before)
        return "".join(self.deltas)


def chain_of(*clients) -> LLMChain:
    return LLMChain([(c, RateLimiter(rpm=1000, tpm=10**9)) for c in clients])


MSG = [{"role": "user", "content": "q"}]


def test_falls_back_when_the_first_provider_fails_before_any_delta():
    a = FakeLLM("a", fail_before="LLM_UNAVAILABLE")
    b = FakeLLM("b", ["ok"])
    assert list(chain_of(a, b).stream(MSG, tokens=10)) == ["ok"]
    assert (a.calls, b.calls) == (1, 1)


def test_never_switches_model_after_the_first_delta():
    a = FakeLLM("a", ["one", "two", "three"], fail_after=1)
    b = FakeLLM("b", ["never"])
    out, err = [], None
    try:
        for d in chain_of(a, b).stream(MSG, tokens=10):
            out.append(d)
    except LLMError as exc:
        err = exc
    assert out == ["one"]
    assert err is not None and err.code == "LLM_UNAVAILABLE"
    assert b.calls == 0


def test_complete_falls_back_when_the_first_provider_is_rate_limited():
    a = FakeLLM("a", fail_before="RATE_LIMITED")
    b = FakeLLM("b", ["viết", " lại"])
    assert chain_of(a, b).complete(MSG, tokens=10) == "viết lại"


def test_all_providers_failing_raises_the_last_code():
    a = FakeLLM("a", fail_before="RATE_LIMITED")
    b = FakeLLM("b", fail_before="LLM_UNAVAILABLE")
    with pytest.raises(LLMError) as err:
        list(chain_of(a, b).stream(MSG, tokens=10))
    assert err.value.code == "LLM_UNAVAILABLE"


def test_a_healthy_first_provider_is_called_once():
    a = FakeLLM("a", ["x"])
    b = FakeLLM("b", ["y"])
    assert list(chain_of(a, b).stream(MSG, tokens=10)) == ["x"]
    assert (a.calls, b.calls) == (1, 0)


def test_a_provider_whose_ceiling_is_too_small_is_skipped_not_fed_the_prompt():
    small = FakeLLM("small", ["bad"], cap=100)
    big = FakeLLM("big", ["good"], cap=5000)
    assert list(chain_of(small, big).stream(MSG, tokens=1000)) == ["good"]
    assert small.calls == 0


def test_context_budget_is_the_smallest_declared_ceiling():
    chain = chain_of(FakeLLM("a", cap=4000), FakeLLM("b", cap=3000), FakeLLM("c", cap=None))
    assert chain.context_budget == 3000
    assert chain_of(FakeLLM("d", cap=None)).context_budget is None


def test_the_estimate_is_conservative():
    assert estimate_tokens("abcd") == 2
    assert estimate_tokens("") == 0


# --- models.yaml -----------------------------------------------------------------------------


def test_build_chain_reads_the_model_and_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("SOPILOT_LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("SOPILOT_LLM_MODEL", "served-model")
    monkeypatch.setenv("SOPILOT_LLM_API_KEY", "secret-value")
    config = ModelsConfig.load(MODELS)
    chain = build_chain(config, "generate")
    client, limiter = chain._entries[0]
    assert client.spec.model == "served-model"
    assert client.spec.base_url == "https://llm.test/v1"
    assert client.spec.api_key == "secret-value"
    assert client.spec.context_max_tokens is None  # not declared: no ceiling yet
    assert client.spec.temperature == 0.2 and client.spec.max_output_tokens == 800
    assert (limiter.rpm, limiter.tpm) == (60, 200_000)


def test_rewrite_task_is_deterministic_and_short(monkeypatch):
    monkeypatch.setenv("SOPILOT_LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("SOPILOT_LLM_MODEL", "m")
    client, _ = build_chain(ModelsConfig.load(MODELS), "rewrite")._entries[0]
    assert client.spec.temperature == 0 and client.spec.max_output_tokens == 200


def test_an_empty_model_is_a_startup_error_not_a_default(monkeypatch):
    monkeypatch.setenv("SOPILOT_LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.delenv("SOPILOT_LLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="SOPILOT_LLM_MODEL"):
        build_chain(ModelsConfig.load(MODELS), "generate")


def test_an_empty_base_url_is_a_startup_error(monkeypatch):
    monkeypatch.delenv("SOPILOT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("SOPILOT_LLM_MODEL", "m")
    with pytest.raises(ValueError, match="SOPILOT_LLM_BASE_URL"):
        build_chain(ModelsConfig.load(MODELS), "generate")


def test_the_models_file_declares_no_gemini_or_groq_in_llm_chains():
    raw = ModelsConfig.load(MODELS).raw["llm"]
    providers = {e["provider"] for task in ("generate", "rewrite") for e in raw[task]["chain"]}
    assert providers == {"modal"}


# --- review follow-ups -------------------------------------------------------------------------


@pytest.mark.parametrize("event", [
    '{"choices": [{"delta": []}]}',        # delta is not an object
    '{"choices": ["not-a-dict"]}',         # choice is not an object
    '{"choices": []}',                     # no choices
    '[1, 2]',                              # not an object at all
])
def test_a_malformed_sse_event_is_llm_unavailable_not_a_raw_error(event):
    body = f"data: {event}\n\ndata: [DONE]\n\n".encode()
    client = client_with(lambda r: httpx.Response(200, content=body))
    with pytest.raises(LLMError) as err:
        list(client.stream([{"role": "user", "content": "q"}]))
    assert err.value.code == "LLM_UNAVAILABLE"


def test_the_api_key_is_not_in_the_spec_repr():
    text = repr(spec(api_key="super-secret-key"))
    assert "super-secret-key" not in text


def test_stopping_early_closes_the_inner_stream():
    closed = []

    class Inner:
        spec = spec()

        def stream(self, messages):
            try:
                yield "a"
                yield "b"
                yield "c"
            finally:
                closed.append(True)

    chain = LLMChain([(Inner(), RateLimiter(rpm=1000, tpm=10**9))])
    gen = chain.stream([{"role": "user", "content": "q"}], tokens=10)
    assert next(gen) == "a"
    gen.close()
    assert closed == [True]


# --- which model answered (messages.model) ---------------------------------------------------


def test_on_start_reports_the_model_that_answers_after_a_fallback():
    a = FakeLLM("a", fail_before="LLM_UNAVAILABLE")
    b = FakeLLM("b", ["x", "y"])
    started: list[str] = []
    assert list(chain_of(a, b).stream(MSG, tokens=10, on_start=started.append)) == ["x", "y"]
    assert started == ["qwen-test"]  # once, with the model of the provider that delivered
    b2 = FakeLLM("b2", ["z"])
    got: list[str] = []
    assert chain_of(b2).complete(MSG, tokens=10, on_start=got.append) == "z"
    assert got == ["qwen-test"]


def test_on_start_is_not_called_when_every_provider_fails():
    a = FakeLLM("a", fail_before="LLM_UNAVAILABLE")
    started: list[str] = []
    with pytest.raises(LLMError):
        list(chain_of(a).stream(MSG, tokens=10, on_start=started.append))
    assert started == []


def test_chain_exposes_its_clients_for_the_startup_model_check():
    a, b = FakeLLM("a"), FakeLLM("b")
    assert chain_of(a, b).clients == [a, b]
