"""Routing evaluation (V2-27): dataset hygiene, metric definitions, acceptance, path resolution."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest
import yaml
from sopilot_ai.qa import router

from sopilot_eval import routing as R

EVAL_ROOT = Path(__file__).resolve().parents[1]
DATA = EVAL_ROOT / "datasets" / "routing"
EXEMPLARS = EVAL_ROOT.parent / "services" / "ai-service" / "src" / "sopilot_ai" / "qa" / "router_exemplars.yaml"


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("đ", "d")
    return " ".join(re.findall(r"\w+", s))


def _rows(split: str) -> list[dict]:
    return R.load_dataset(DATA / f"{split}.jsonl")


# --- dataset hygiene ---------------------------------------------------------------------------

def test_no_dataset_row_duplicates_a_router_exemplar():
    exemplars = yaml.safe_load(EXEMPLARS.read_text(encoding="utf-8"))
    exemplar_norm = {_norm(t) for texts in exemplars.values() for t in texts}
    clashes = [(split, r["id"]) for split in ("dev", "test") for r in _rows(split)
               if _norm(r["text"]) in exemplar_norm]
    assert clashes == [], f"rows copy router exemplars: {clashes}"


def test_no_text_overlaps_between_dev_and_test_or_repeats_inside_a_split():
    dev = {_norm(r["text"]) for r in _rows("dev")}
    test = [_norm(r["text"]) for r in _rows("test")]
    assert not (dev & set(test)), "dev/test overlap"
    for split in ("dev", "test"):
        texts = [_norm(r["text"]) for r in _rows(split)]
        assert len(texts) == len(set(texts)), f"repeated text inside {split}"


def test_dataset_size_and_ids_match_the_ticket():
    rows = _rows("dev") + _rows("test")
    assert 300 <= len(rows) <= 500
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_every_label_appears_in_both_splits_and_only_known_labels_are_used():
    labels = set(R.LABELS)
    for split in ("dev", "test"):
        seen = Counter(r["intent"] for r in _rows(split))
        assert set(seen) <= labels, f"unknown labels in {split}: {set(seen) - labels}"
        assert set(seen) == labels, f"labels missing from {split}: {labels - set(seen)}"


def test_followup_and_about_source_rows_carry_previous_turn_and_corpus_fields():
    for split in ("dev", "test"):
        for r in _rows(split):
            if r["intent"] in ("followup", "about_source"):
                assert r["previous_turn"], r["id"]
                assert "corpus" in r and "evidence" in r, r["id"]


def test_sarcasm_and_teencode_are_covered_in_test():
    test = _rows("test")
    assert sum(r["sarcasm"] for r in test) >= 10
    assert sum(r["teencode"] for r in test) >= 10


# --- metric definitions ------------------------------------------------------------------------

def _pred(label: str, ms: float | None = None, layer: str = "rule") -> R.Prediction:
    return R.Prediction(label, layer, ms)


def test_costly_and_cheap_error_classes():
    rows = [{"intent": "sop_question"}, {"intent": "followup"}, {"intent": "greeting"},
            {"intent": "abuse_with_question"}, {"intent": "about_bot"}]
    preds = [_pred("greeting"), _pred("rag"), _pred("rag"), _pred("rag"), _pred("about_bot")]
    errors = R.error_classes(rows, preds)
    assert errors["costly"] == 1  # the sop_question row routed to greeting
    assert errors["cheap"] == 2  # greeting and abuse_with_question reached RAG
    assert errors["other_misses"] == 0


def test_off_topic_gap_list_rate_counts_only_non_out_of_scope_rows():
    rows = [{"intent": "off_topic"}] * 4
    preds = [_pred(router.OUT_OF_SCOPE_CANDIDATE), _pred("rag"), _pred("rag"), _pred("rag")]
    result = R.summarize(rows, preds)
    assert result["off_topic"]["to_gap_list_upper_bound"] == 3
    assert result["off_topic"]["rate"] == pytest.approx(0.75)


def test_per_label_precision_and_recall():
    rows = [{"intent": "greeting"}, {"intent": "greeting"}, {"intent": "thanks"}]
    preds = [_pred("greeting"), _pred("rag"), _pred("greeting")]
    stats = R.per_label(rows, preds)
    assert stats["greeting"]["recall"] == pytest.approx(0.5)
    assert stats["greeting"]["precision"] == pytest.approx(0.5)  # the thanks row was predicted greeting
    assert stats["thanks"]["recall"] == 0.0 and stats["thanks"]["precision"] is None
    assert stats["sop_question"]["n"] == 0


def test_acceptance_uses_the_two_percent_threshold_and_baseline_costly_count():
    rows = [{"intent": "sop_question"}] * 50
    one_routed = [_pred("rag")] * 49 + [_pred("greeting")]
    assert R.summarize(rows, one_routed)["acceptance"]["passed"] is True  # 1/50 = 2 %
    two_routed = [_pred("rag")] * 48 + [_pred("greeting")] * 2
    assert R.summarize(rows, two_routed)["acceptance"]["passed"] is False  # 4 %
    # Not more costly errors than the rules-only baseline:
    assert R.summarize(rows, one_routed, baseline_costly=0)["acceptance"]["passed"] is False


def test_acceptance_thresholds_come_from_the_config_when_given():
    rows = [{"intent": "sop_question"}] * 10
    preds = [_pred("rag")] * 9 + [_pred("greeting")]  # 10 %
    assert R.summarize(rows, preds, {"sop_misroute_max": 0.2})["acceptance"]["passed"] is True


def test_latency_percentiles():
    rows = [{"intent": "sop_question"}] * 4
    preds = [_pred("rag", ms) for ms in (10.0, 20.0, 30.0, 40.0)]
    result = R.summarize(rows, preds)
    assert result["router_latency_ms"]["ran_on"] == 4
    assert result["router_latency_ms"]["p50"] == pytest.approx(25.0)
    assert result["router_latency_ms"]["p95"] == pytest.approx(38.5, abs=1.0)


# --- paths and offline rules ------------------------------------------------------------------

def test_config_dataset_paths_resolve_from_the_eval_directory(monkeypatch):
    monkeypatch.chdir(EVAL_ROOT)
    assert R.resolve_path("eval/datasets/routing/test.jsonl").is_file()


def test_config_dataset_paths_resolve_from_an_unrelated_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert R.resolve_path("eval/datasets/routing/test.jsonl").is_file()


def test_rules_only_prediction_runs_without_a_model():
    vocab = frozenset()
    preds = R.predict_rules(["Xin chào", "Quy trình xin nghỉ phép gồm những bước nào?"], vocab)
    assert preds[0][0] == "greeting"
    assert preds[1][0] == R.RAG


def test_rules_config_is_the_rules_only_configuration():
    cfg = yaml.safe_load((EVAL_ROOT / "configs" / "routing-rules.yaml").read_text(encoding="utf-8"))
    assert cfg["semantic_router_enabled"] is False
    assert "embedder" not in cfg


def test_semantic_config_pins_the_embedding_revision_and_compares_to_rules():
    cfg = yaml.safe_load((EVAL_ROOT / "configs" / "routing-rules-router.yaml").read_text(encoding="utf-8"))
    assert cfg["semantic_router_enabled"] is True
    assert re.fullmatch(r"[0-9a-f]{40}", cfg["embedder"]["revision"])
    assert cfg["baseline"]


def test_jsonl_loader_skips_blank_lines(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text(json.dumps({"text": "a", "intent": "greeting"}) + "\n\n", encoding="utf-8")
    assert R.load_dataset(path) == [{"text": "a", "intent": "greeting"}]


# --- V2-44: the SetFit classifier through the service code path ----------------------------------

class _FakeClassifier:
    """Names a label from the text; the harness must only act on non-RAG actions."""

    def __init__(self):
        self.seen: list[tuple[str, str | None]] = []

    def classify(self, text, previous=None):
        from sopilot_ai.qa.setfit_router import ClassifierDecision
        self.seen.append((text, previous))
        if "thoi tiet" in text:
            return ClassifierDecision("off_topic", 0.9, router.ACTION_OUT_OF_SCOPE)
        if "cam on" in text:
            return ClassifierDecision("thanks", 0.9, router.ACTION_TEMPLATE)
        return ClassifierDecision("sop_question", 0.9, router.ACTION_RAG)


def test_the_classifier_config_points_at_the_service_models_yaml_and_has_a_baseline():
    cfg = yaml.safe_load((EVAL_ROOT / "configs" / "routing-setfit.yaml").read_text(encoding="utf-8"))
    assert cfg["router_classifier"]["models_config"] == "services/ai-service/config/models.yaml"
    assert cfg["semantic_router_enabled"] is False and cfg["baseline"]


def test_a_config_without_router_classifier_builds_no_classifier():
    assert R.build_classifier({}) is None


def test_predict_uses_the_classifier_only_where_the_rules_left_retrieval():
    classifier = _FakeClassifier()
    vocab = frozenset({"quy", "trinh", "nghi", "phep", "thoi", "tiet", "hom", "nay", "toi", "can"})
    rows = [{"text": "quy trinh nghi phep", "intent": "sop_question", "previous_turn": "Prev."},
            {"text": "thoi tiet hom nay", "intent": "off_topic"},
            {"text": "Xin chào", "intent": "greeting"}]
    preds = R.predict(rows, None, vocab, classifier)
    assert [p.layer for p in preds] == ["setfit", "setfit", "rule"]  # the rules decided the greeting
    assert [p.label for p in preds] == [R.RAG, "off_topic", "greeting"]
    assert classifier.seen[0] == ("quy trinh nghi phep", "Prev.") and len(classifier.seen) == 2


# --- V2-44: the corpus-specific set stays apart from the training data -------------------------------

def test_corpus_set_is_disjoint_from_training_dev_and_frozen_test_texts():
    if not (DATA / "corpus-test.jsonl").exists():  # the datasets folder is git-ignored
        pytest.skip("corpus-test.jsonl is only on the owner's machine")
    corpus = R.load_dataset(DATA / "corpus-test.jsonl")
    seen = set()
    for r in corpus:
        key = (_norm(r["text"]), bool(r["previous_turn"]))
        assert key not in seen, r["id"]
        seen.add(key)
    used = {_norm(r["text"]) for f in ("train-pool", "dev", "test") for r in R.load_dataset(DATA / f"{f}.jsonl")}
    leaked = [r["id"] for r in corpus if _norm(r["text"]) in used]  # every row, every source
    assert leaked == []
    assert {r["intent"] for r in corpus} <= set(R.LABELS)
    assert sum(r["intent"] == "sop_question" and r["source"].startswith("sop-main-v2:") for r in corpus) >= 100
