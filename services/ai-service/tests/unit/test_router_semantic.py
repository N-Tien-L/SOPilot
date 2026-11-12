"""Semantic router (V2-27): thresholds, margin, history, cache identity, and flag off = V2-10."""
from __future__ import annotations

import numpy as np
import pytest

from sopilot_ai.qa import router
from sopilot_ai.qa.query_frame import build_query_frame

DIM = 8


def axis(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


def mix(*parts: tuple[int, float]) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for i, w in parts:
        v[i] += w
    return v


class TableEmbedder:
    """Returns the vector given for each text. An unknown text is a test bug (KeyError)."""

    def __init__(self, table: dict[str, np.ndarray]) -> None:
        self.table = table
        self.calls = 0
        self.embedded: list[str] = []

    def embed(self, texts, *, is_query: bool):
        self.calls += 1
        self.embedded += list(texts)
        return np.vstack([self.table[t] for t in texts])


EXEMPLARS = {
    "sop_question": ("quy trinh nghi phep",),
    "about_bot": ("ban la ai",),
    "greeting": ("xin chao",),
    "about_source": ("nguon tu dau",),
    "off_topic": ("thoi tiet hom nay",),
}
THRESHOLDS = router.RouterThresholds(
    default=router.IntentThreshold(0.8, 0.1),
    intents={"about_bot": router.IntentThreshold(0.8, 0.1)},
)
EXEMPLAR_VECTORS = {
    "quy trinh nghi phep": axis(0),
    "ban la ai": axis(1),
    "xin chao": axis(2),
    "nguon tu dau": axis(3),
    "thoi tiet hom nay": axis(4),
}


def table_for(query_vectors: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {**EXEMPLAR_VECTORS, **query_vectors}


def layer(query_vectors: dict[str, np.ndarray], **kw) -> router.SemanticLayer:
    return router.SemanticLayer(TableEmbedder(table_for(query_vectors)), model_id="fake@r1",
                                exemplars=EXEMPLARS, thresholds=THRESHOLDS, **kw)


# --- flag off: the V2-10 rule router is unchanged -------------------------------------------

def test_flag_off_builds_no_layer_and_never_loads_the_model():
    calls: list[int] = []

    def factory():
        calls.append(1)
        raise AssertionError("embedder must not load when the router is off")

    assert router.build_semantic_layer(enabled=False, embedder_factory=factory,
                                       model_id="x") is None
    assert calls == []


def test_rule_router_outputs_are_the_same_as_before_v2_27():
    frame = build_query_frame("Xin chào")
    result = router.strip_and_judge(frame)
    assert result.template_key == "greeting" and result.working_text == ""

    frame = build_query_frame("Quy trình xin nghỉ phép gồm những bước nào?")
    result = router.strip_and_judge(frame)
    assert result.template_key is None and result.working_text.startswith("Quy trình")


# --- flag on: routing with a deterministic embedder -----------------------------------------

def test_flag_on_routes_a_question_the_rules_missed_to_about_bot():
    # "ê mày làm được gì vậy" shares no trigger phrase with the rules; its vector is near about_bot.
    lay = layer({"ê mày làm được gì vậy": mix((1, 0.95), (0, 0.05))})
    decision = lay.classify("ê mày làm được gì vậy", has_history=False)
    assert decision.intent == "about_bot"
    assert decision.top_intent == "about_bot"
    assert router.action_for(decision.intent) == router.ACTION_TEMPLATE


def test_below_threshold_falls_back_to_rag():
    # Best cosine to about_bot is 0.5, under its threshold of 0.8: no route.
    lay = layer({"hơi mơ hồ": mix((1, 0.5), (5, 0.866))})
    decision = lay.classify("hơi mơ hồ", has_history=False)
    assert decision.intent is None and decision.top_intent == "about_bot"
    assert router.action_for(decision.intent) == router.ACTION_RAG


def test_margin_against_sop_question_blocks_a_route():
    # about_bot exemplar sits 30 degrees from the sop_question axis; the question sits 15 degrees
    # away from both. Its cosine to about_bot (0.966) passes the 0.8 threshold, but the margin
    # to sop_question is about 0, under the 0.1 required.
    about = np.array([np.cos(np.pi / 6), np.sin(np.pi / 6)] + [0.0] * (DIM - 2), np.float32)
    query = np.array([np.cos(np.pi / 12), np.sin(np.pi / 12)] + [0.0] * (DIM - 2), np.float32)
    lay = layer({"ban la ai": about, "cau lai": query})
    decision = lay.classify("cau lai", has_history=False)
    assert decision.top_intent == "about_bot" and decision.top_score > 0.8
    assert decision.intent is None
    assert abs(decision.margin) < 0.01


def test_threshold_and_margin_are_read_per_intent_with_default_fallback():
    thresholds = router.RouterThresholds(
        default=router.IntentThreshold(0.5, 0.0),
        intents={"about_bot": router.IntentThreshold(0.95, 0.0)})
    assert thresholds.for_intent("greeting").threshold == 0.5
    assert thresholds.for_intent("about_bot").threshold == 0.95


def test_about_source_is_only_eligible_with_history():
    lay = layer({"no lay tu dau": mix((3, 0.97), (0, 0.1))})
    assert lay.classify("no lay tu dau", has_history=False).top_intent != "about_source"
    with_history = lay.classify("no lay tu dau", has_history=True)
    assert with_history.intent == "about_source"
    assert router.action_for(with_history.intent) == router.ACTION_TEMPLATE


def test_off_topic_becomes_out_of_scope_only_when_the_gate_refused():
    lay = layer({"thoi tiet the nao": mix((4, 0.95), (0, 0.05))})
    decision = lay.classify("thoi tiet the nao", has_history=False)
    assert decision.intent == router.OUT_OF_SCOPE_CANDIDATE
    assert router.action_for(decision.intent) == router.ACTION_OUT_OF_SCOPE
    assert router.is_out_of_scope(decision, gate_refused=True)
    # The router never turns a passing gate into a refusal.
    assert not router.is_out_of_scope(decision, gate_refused=False)


def test_question_vector_is_reused_without_a_second_embedding_of_the_question():
    emb = TableEmbedder(table_for({"cau hoi": axis(0)}))
    lay = router.SemanticLayer(emb, model_id="fake@r1", exemplars=EXEMPLARS,
                               thresholds=THRESHOLDS)
    vector = lay.embed_query("cau hoi")
    lay.decide(vector, has_history=False)
    assert emb.embedded.count("cau hoi") == 1


# --- cache identity: a changed model embeds the exemplars again ----------------------------

def test_exemplars_are_embedded_once_per_model_and_never_mixed():
    cache: dict = {}
    first = TableEmbedder(table_for({}))
    router.SemanticLayer(first, model_id="model-a@r1", exemplars=EXEMPLARS,
                         thresholds=THRESHOLDS, cache=cache)
    assert len(first.embedded) == 5

    again = TableEmbedder(table_for({}))
    router.SemanticLayer(again, model_id="model-a@r1", exemplars=EXEMPLARS,
                         thresholds=THRESHOLDS, cache=cache)
    assert again.embedded == []  # warm cache, same model

    other = TableEmbedder(table_for({}))
    router.SemanticLayer(other, model_id="model-b@r2", exemplars=EXEMPLARS,
                         thresholds=THRESHOLDS, cache=cache)
    assert sorted(other.embedded) == sorted(first.embedded)  # re-embedded for the new model
    assert {k[0] for k in cache} == {"model-a@r1", "model-b@r2"}


def test_build_with_flag_on_uses_the_factory_once():
    calls: list[int] = []

    def factory():
        calls.append(1)
        return TableEmbedder(table_for({}))

    lay = router.build_semantic_layer(enabled=True, embedder_factory=factory,
                                      model_id="fake@r1", exemplars=EXEMPLARS,
                                      thresholds=THRESHOLDS)
    assert isinstance(lay, router.SemanticLayer) and calls == [1]


# --- configuration files ----------------------------------------------------------------------

def test_shipped_exemplars_and_thresholds_load_and_agree():
    exemplars = router.load_exemplars()
    thresholds = router.load_thresholds()
    assert router.REFERENCE_INTENT in exemplars
    assert set(exemplars) <= router.SEMANTIC_INTENTS | {router.REFERENCE_INTENT}
    assert set(thresholds.intents) <= set(exemplars)
    assert all(texts for texts in exemplars.values())


def test_unknown_intent_or_missing_contrast_class_is_rejected():
    with pytest.raises(ValueError, match="unknown intents"):
        router.parse_exemplars({"sop_question": ["a"], "smalltalk": ["b"]})
    with pytest.raises(ValueError, match="contrast class"):
        router.parse_exemplars({"greeting": ["a"]})
    with pytest.raises(ValueError, match="unknown intents"):
        router.parse_thresholds({"default": {"threshold": 0.8, "margin": 0.1},
                                 "intents": {"smalltalk": {"threshold": 0.8, "margin": 0.1}}})


def test_threshold_out_of_range_is_rejected():
    with pytest.raises(ValueError):
        router.parse_thresholds({"default": {"threshold": 1.5, "margin": 0.1}})


def test_empty_exemplar_list_is_rejected():
    with pytest.raises(ValueError):
        router.parse_exemplars({"sop_question": ["a"], "greeting": []})


def test_embed_query_normalises_the_provider_vector():
    emb = TableEmbedder(table_for({"x": mix((0, 3.0), (1, 4.0))}))
    lay = router.SemanticLayer(emb, model_id="fake@r1", exemplars=EXEMPLARS,
                               thresholds=THRESHOLDS)
    assert float(np.linalg.norm(lay.embed_query("x"))) == pytest.approx(1.0, abs=1e-6)
