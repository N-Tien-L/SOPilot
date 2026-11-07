"""V2-09 step 2, no database: fusion, gate, doc codes, config, UTF-16 offsets, access tokens."""
from __future__ import annotations

import time
from uuid import uuid4

import jwt
import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from fakes import FakeEmbedder
from sopilot_ai.api.documents import utf16_offsets
from sopilot_ai.auth.jwt import AUDIENCE, ISSUER, InvalidToken, TokenVerifier
from sopilot_ai.config import SERVICE_ROOT
from sopilot_ai.providers.registry import ModelsConfig, RetrievalConfig
from sopilot_ai.providers.rerank import build_rerank_provider
from sopilot_ai.qa.doc_code import find_doc_codes
from sopilot_ai.retrieval import fusion
from sopilot_ai.retrieval.access_filter import Principal, allowed_cte
from sopilot_ai.retrieval.lexical import BM25, lexical_len, tokenize
from sopilot_ai.retrieval.retriever import Retriever

# --- fusion ---------------------------------------------------------------------------------


def test_rrf_sums_weighted_reciprocal_ranks() -> None:
    fused = fusion.rrf([["a", "b"], ["b", "c"]], [1.0, 0.5], k=60)
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 0.5 / 61)
    assert fused["c"] == pytest.approx(0.5 / 62)
    assert fusion.order(fused) == ["b", "a", "c"]


def test_cross_lingual_factor_one_is_plain_rrf() -> None:
    rankings = [["a", "b", "c"], ["c", "a", "b"]]
    langs = {"a": "en", "b": "vi", "c": None}
    plain = fusion.rrf(rankings, [1.0, 1.0])
    weights = fusion.cross_lingual_weights(langs, "vi", 1.0)
    assert weights == {}
    assert fusion.rrf(rankings, [1.0, 1.0], item_weights=[None, weights]) == plain


def test_cross_lingual_factor_scales_only_other_language() -> None:
    langs = {"a": "en", "b": "vi", "c": None, "d": "fr"}
    assert fusion.cross_lingual_weights(langs, "vi", 0.5) == {"a": 0.5}
    assert fusion.cross_lingual_weights(langs, None, 0.5) == {}  # unknown question language
    fused = fusion.rrf([[], ["a", "b"]], [1.0, 1.0],
                       item_weights=[None, fusion.cross_lingual_weights(langs, "vi", 0.5)])
    assert fused["a"] == pytest.approx(0.5 / 61)
    assert fused["b"] == pytest.approx(1 / 62)


def test_doc_code_boost_adds_to_matching_candidates_only() -> None:
    boosted = fusion.apply_doc_code_boost({"a": 0.01, "b": 0.02}, {"a", "zz"}, 0.02)
    assert boosted == {"a": pytest.approx(0.03), "b": 0.02}
    assert fusion.apply_doc_code_boost({"a": 0.01}, {"a"}, 0.0) == {"a": 0.01}


def test_gate_score_per_mode() -> None:
    cand = {"dense_score": 0.6, "rerank_score": 0.2}
    assert fusion.gate_score("dense", cand) == 0.6
    assert fusion.gate_score("hybrid", cand) == 0.6
    assert fusion.gate_score("hybrid_rerank", cand) == 0.2
    assert fusion.gate_score("bm25", cand) is None
    with pytest.raises(ValueError):
        fusion.gate_score("hybrid", {"dense_score": None})
    with pytest.raises(ValueError):
        fusion.gate_score("rrf", cand)


def test_thresholds_are_per_mode_and_bm25_never_refuses() -> None:
    t = RetrievalConfig().thresholds
    assert fusion.threshold_for("hybrid", t) == 0.45
    assert fusion.threshold_for("hybrid_rerank", t) == 0.30
    assert fusion.threshold_for("bm25", t) is None
    assert fusion.passes(None, None)
    assert fusion.passes(0.45, 0.45)
    assert not fusion.passes(0.44, 0.45)
    assert not fusion.passes(None, 0.45)


# --- document codes -------------------------------------------------------------------------


@pytest.mark.parametrize(("question", "codes"), [
    ("QT-MH-01 quy định gì về duyệt?", {"QT-MH-01"}),
    ("theo quy trình qt-mh-01, ai duyệt", {"QT-MH-01"}),
    ("Biểu mẫu BM/QT-05 ở đâu", {"BM/QT-05"}),
    ("quy trình mua hàng gồm mấy bước", set()),
    ("Who approves purchase requests?", set()),
])
def test_find_doc_codes(question: str, codes: set[str]) -> None:
    assert find_doc_codes(question) == codes


# --- configuration --------------------------------------------------------------------------


def test_models_yaml_retrieval_and_rerank_sections() -> None:
    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    r = config.retrieval()
    assert (r.mode, r.candidate_pool, r.rerank_pool, r.context_k, r.rrf_k) == (
        "hybrid", 50, 25, 5, 60)
    assert r.rrf_weights == (1.0, 1.0)
    assert r.doc_code_boost == 0.02 and r.cross_lingual_bm25_factor == 1.0
    assert r.thresholds == {"dense": 0.45, "bm25": None, "hybrid": 0.45, "hybrid_rerank": 0.30}
    spec = config.rerank()
    assert not spec.enabled and spec.model == "BAAI/bge-reranker-v2-m3"
    assert build_rerank_provider(config, "local") is None


def test_rerank_enabled_needs_pinned_revision_in_eval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.delenv("RERANK_REVISION", raising=False)
    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    assert config.rerank().enabled
    with pytest.raises(RuntimeError):
        build_rerank_provider(config, "eval")
    provider = build_rerank_provider(config, "local")  # not loaded until first score()
    assert provider is not None and provider.revision == "unpinned"


def test_rerank_only_on_hybrid() -> None:
    class Rerank:
        name, model, revision = "local", "m", "r"

        def score(self, query, passages):  # noqa: ANN001, ANN201
            return np.zeros(len(passages))

    Retriever(FakeEmbedder(), RetrievalConfig(mode="hybrid"), Rerank())
    with pytest.raises(ValueError):
        Retriever(FakeEmbedder(), RetrievalConfig(mode="dense"), Rerank())
    assert Retriever(FakeEmbedder(), RetrievalConfig(mode="hybrid"), Rerank()).mode == (
        "hybrid_rerank")


def test_access_filter_sql_is_parameterised() -> None:
    sql = allowed_cte()
    for param in (":wid", ":wrole", ":wdept"):
        assert param in sql
    assert "deleted_at IS NULL" in sql and "active_version_id IS NOT NULL" in sql
    with pytest.raises(ValueError):
        Principal(uuid4(), uuid4(), "VIEWER")


# --- in-memory BM25 reference ---------------------------------------------------------------


def test_bm25_reference_uses_base_length_and_folded_terms() -> None:
    docs = ["Quy trình mua hàng", "Purchase request approval", "quy trình tuyển dụng"]
    bm25 = BM25([tokenize(d) for d in docs], lengths=[lexical_len(d) for d in docs])
    s = bm25.scores(tokenize("quy trinh mua hang", role="query"))
    assert int(np.argmax(s)) == 0 and s[1] == 0
    english = bm25.scores(tokenize("purchase approval", role="query"))
    assert int(np.argmax(english)) == 1


# --- UTF-16 offsets -------------------------------------------------------------------------


def test_utf16_offsets_count_astral_characters_twice() -> None:
    text = "a😀b𝔸c"  # two characters outside the BMP
    out = utf16_offsets(text, [0, 1, 2, 3, 4, 5])
    assert out == {0: 0, 1: 1, 2: 3, 3: 4, 4: 6, 5: 7}
    for i in range(len(text) + 1):
        assert utf16_offsets(text, [i])[i] == len(text[:i].encode("utf-16-le")) // 2


# --- access tokens --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def keypair():  # noqa: ANN201
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key()


def _token(private, **overrides) -> str:  # noqa: ANN001
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": ["sopilot-core", AUDIENCE], "sub": str(uuid4()),
              "wid": str(uuid4()), "wrole": "MEMBER", "wdept": None, "jti": str(uuid4()),
              "iat": now, "exp": now + 900}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not ...}
    return jwt.encode(claims, private, algorithm="RS256")


def test_valid_token_gives_principal(keypair) -> None:  # noqa: ANN001
    private, public = keypair
    dept = uuid4()
    verifier = TokenVerifier(key_for=lambda _t: public)
    p = verifier.verify(_token(private, wrole="ADMIN", wdept=str(dept)))
    assert p.role == "ADMIN" and p.department_id == dept
    assert verifier.verify(_token(private)).department_id is None


@pytest.mark.parametrize("overrides", [
    {"aud": ["sopilot-core"]},
    {"iss": "someone-else"},
    {"exp": int(time.time()) - 3600},
    {"wid": ...},
    {"wrole": "ROOT"},
])
def test_invalid_tokens_are_rejected(keypair, overrides) -> None:  # noqa: ANN001
    private, public = keypair
    with pytest.raises(InvalidToken):
        TokenVerifier(key_for=lambda _t: public).verify(_token(private, **overrides))


def test_token_signed_by_another_key_is_rejected(keypair) -> None:  # noqa: ANN001
    _, public = keypair
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidToken):
        TokenVerifier(key_for=lambda _t: public).verify(_token(other))
