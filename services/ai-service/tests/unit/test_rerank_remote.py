"""RemoteRerankProvider (V2-35): Modal `/rerank` over httpx, no network."""
from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from sopilot_ai.providers.registry import ModelsConfig
from sopilot_ai.providers.rerank import (
    LocalRerankProvider,
    RemoteRerankProvider,
    RerankError,
    build_rerank_provider,
)


def _config(provider: str = "modal", base_url: str = "https://x.modal.run/v1") -> ModelsConfig:
    return ModelsConfig(raw={
        "rerank": {"enabled": True, "provider": provider, "model": "BAAI/bge-reranker-v2-m3",
                   "revision": "abc", "max_pairs": 25, "timeout_s": 5},
        "providers": {"modal": {"rerank_base_url": base_url, "api_key_env": "TEST_RERANK_KEY"}},
    })


def _provider(handler, monkeypatch) -> RemoteRerankProvider:
    monkeypatch.setenv("TEST_RERANK_KEY", "secret-key")
    built = build_rerank_provider(_config(), "dev", transport=httpx.MockTransport(handler))
    assert isinstance(built, RemoteRerankProvider)
    return built


def test_logits_become_sigmoid_scores_in_passage_order(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"logits": [0.0, 2.0]})

    scores = _provider(handler, monkeypatch).score("q", ["a", "b"])
    assert seen["url"] == "https://x.modal.run/v1/rerank"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"] == {"query": "q", "passages": ["a", "b"]}
    assert np.allclose(scores, [0.5, 1 / (1 + np.exp(-2.0))])


def test_unauthorized_is_a_rerank_error_with_fixed_code(monkeypatch):
    provider = _provider(lambda r: httpx.Response(401, json={"detail": "secret-key"}), monkeypatch)
    with pytest.raises(RerankError, match="RERANK_HTTP_401") as err:
        provider.score("q", ["a"])
    assert "secret-key" not in str(err.value)


def test_timeout_is_a_rerank_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(RerankError, match="RERANK_TIMEOUT"):
        _provider(handler, monkeypatch).score("q", ["a"])


def test_logit_count_mismatch_is_a_rerank_error(monkeypatch):
    provider = _provider(lambda r: httpx.Response(200, json={"logits": [1.0]}), monkeypatch)
    with pytest.raises(RerankError, match="RERANK_BAD_RESPONSE"):
        provider.score("q", ["a", "b"])


def test_malformed_json_is_a_rerank_error(monkeypatch):
    provider = _provider(lambda r: httpx.Response(200, content=b"not json"), monkeypatch)
    with pytest.raises(RerankError, match="RERANK_BAD_RESPONSE"):
        provider.score("q", ["a"])


def test_empty_passages_make_no_network_call(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call for empty passages")

    assert _provider(handler, monkeypatch).score("q", []).shape == (0,)


def test_build_rerank_provider_handles_local_modal_and_none():
    assert isinstance(build_rerank_provider(_config("local"), "dev"), LocalRerankProvider)
    assert isinstance(build_rerank_provider(_config("modal"), "dev"), RemoteRerankProvider)
    assert build_rerank_provider(_config("none"), "dev") is None
    with pytest.raises(ValueError):
        build_rerank_provider(_config("modal", base_url=""), "dev")


def test_modal_303_redirect_during_cold_start_is_followed(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rerank"):
            return httpx.Response(303, headers={"Location": "https://x.modal.run/__modal/result"})
        return httpx.Response(200, json={"logits": [0.0]})

    assert _provider(handler, monkeypatch).score("q", ["a"]).tolist() == [0.5]
