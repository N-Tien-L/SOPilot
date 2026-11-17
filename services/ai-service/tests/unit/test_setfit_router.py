"""SetFit router classifier (V2-44, ADR-012): head maths, input format, actions, steps, flag."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from fakes import BowEmbedder, FakeSetFitEncoder, ScriptedChain
from sopilot_ai.config import Settings
from sopilot_ai.conversations.service import QAService
from sopilot_ai.conversations.steps import (
    ClassifierRouterStep,
    QAContext,
    classify_question,
)
from sopilot_ai.providers.registry import ModelsConfig, RouterClassifierSpec
from sopilot_ai.qa import router, setfit_router
from sopilot_ai.qa.pipeline import STEP_ORDER, DecisionKind
from sopilot_ai.quota.counters import QuotaCounter
from sopilot_ai.retrieval.context import ContextConfig
from sopilot_ai.retrieval.retriever import RetrievalConfig, Retriever

SERVICE_ROOT = Path(__file__).resolve().parents[2]
LABELS = ("greeting", "thanks", "about_bot", "abuse_only", "off_topic", "legal_medical",
          "action_request", "sop_question", "about_source")
DIM = len(LABELS)


def spec(**kw) -> RouterClassifierSpec:  # noqa: ANN003
    base = RouterClassifierSpec(
        artifact_dir=Path("unused"), max_seq_length=128, max_input_chars=2000,
        previous_template="Previous message: {previous}\nCurrent message: {current}",
        previous_max_chars=200, labels=LABELS,
        template_labels=frozenset({"greeting", "thanks", "about_bot", "abuse_only"}),
        deferred_labels=frozenset({"off_topic", "legal_medical", "about_source"}),
        disclaimer_labels=frozenset({"action_request", "legal_medical"}),
        out_of_scope_label="off_topic")
    return replace(base, **kw)


def onehot(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


def classifier(*, table: dict[str, str] | None = None, **kw  # noqa: ANN003
               ) -> tuple[setfit_router.SetFitClassifier, FakeSetFitEncoder]:
    """A head that reads the label straight off a one-hot embedding (coef = 4 * identity).

    ``table`` maps a text fragment to the label its embedding points at."""
    encoder = FakeSetFitEncoder(
        {k: onehot(LABELS.index(v)) for k, v in (table or {}).items()}, DIM)
    head = setfit_router.SetFitClassifier(
        encoder, 4.0 * np.eye(DIM), np.zeros(DIM), np.arange(DIM), spec(**kw))
    return head, encoder


# -- the head: softmax(embedding @ coef.T + intercept) ------------------------------------------

def test_probabilities_are_the_softmax_of_the_linear_head() -> None:
    rng = np.random.default_rng(3)
    coef, intercept = rng.normal(size=(DIM, 6)), rng.normal(size=DIM)
    emb = rng.normal(size=6).astype(np.float32)
    encoder = FakeSetFitEncoder({"q": emb}, 6)
    head = setfit_router.SetFitClassifier(encoder, coef, intercept, np.arange(DIM), spec())
    z = emb.astype(np.float64) @ coef.T + intercept
    want = np.exp(z - z.max()) / np.exp(z - z.max()).sum()
    got = head.probabilities("q")
    assert np.abs(got - want).max() < 1e-9 and abs(got.sum() - 1.0) < 1e-9


def test_head_classes_map_columns_to_label_positions() -> None:
    encoder = FakeSetFitEncoder({"q": np.array([1.0, 0.0], dtype=np.float32)}, 2)
    coef = np.array([[5.0, 0.0], [0.0, 5.0]])
    head = setfit_router.SetFitClassifier(encoder, coef, np.zeros(2), np.array([7, 1]), spec())
    proba = head.probabilities("q")
    assert LABELS[int(np.argmax(proba))] == "sop_question"  # class 7 is the first column
    assert proba[0] == 0.0  # a label the head never saw


def test_a_head_that_does_not_fit_the_labels_is_refused() -> None:
    encoder = FakeSetFitEncoder({}, 2)
    with pytest.raises(setfit_router.ClassifierUnavailable):
        setfit_router.SetFitClassifier(encoder, np.zeros((2, 2)), np.zeros(2),
                                       np.array([0, 99]), spec())


# -- the input: previous message and format -----------------------------------------------------

def test_the_input_is_the_bare_question_without_a_previous_message() -> None:
    head, encoder = classifier(table={"xin chao": "greeting"})
    head.classify("xin chao")
    assert encoder.inputs == ["xin chao"]


def test_the_input_has_the_training_format_with_a_previous_message() -> None:
    head, encoder = classifier(table={"cam on": "thanks"})
    head.classify("cam on", "Ban nop don truoc 3 ngay.")
    assert encoder.inputs == [
        "Previous message: Ban nop don truoc 3 ngay.\nCurrent message: cam on"]


def test_previous_message_is_the_first_sentence_of_the_last_answer_without_markers() -> None:
    history = [("q1", "Cau tra loi cu."),
               ("q2", "Nhân viên nộp đơn trước 3 ngày [1][2]. Sau đó quản lý duyệt [3].")]
    assert setfit_router.previous_message(history, 200) == "Nhân viên nộp đơn trước 3 ngày."


def test_previous_message_skips_markdown_markup_and_blank_lines() -> None:
    history = [("q", "\n\n- **Quy trình** nghỉ phép: nộp đơn [1]\n- bước 1")]
    assert setfit_router.previous_message(history, 200) == "Quy trình nghỉ phép: nộp đơn"


def test_a_leading_heading_is_skipped_for_the_first_sentence_below_it() -> None:
    history = [("q", "## Trả lời\n\nNộp đơn trước 3 ngày [1][2].\n\n- Bước 1")]
    assert setfit_router.previous_message(history, 200) == "Nộp đơn trước 3 ngày."
    # an answer that is only a heading still gives something to send
    assert setfit_router.previous_message([("q", "## Kết luận")], 200) == "Kết luận"


@pytest.mark.parametrize(("answer", "want"), [
    ("1. Nộp đơn [1]\n2. Chờ duyệt [2]\n\nLưu ý: mình không cung cấp dữ liệu cá nhân.", "Nộp đơn"),
    ("**Trả lời**\n\nNộp đơn trước 3 ngày [1].", "Nộp đơn trước 3 ngày."),
    ("**Nhân viên nộp đơn trước ba ngày làm việc kể từ ngày bắt đầu nghỉ** [1]\n\nHết.",
     "Nhân viên nộp đơn trước ba ngày làm việc kể từ ngày bắt đầu nghỉ"),
    ("* Bước 1 nộp đơn\n* Bước 2\n\nTóm lại là xong.", "Bước 1 nộp đơn"),
    ("| Bước | Nội dung |\n|---|---|\n| 1 | Nộp đơn |\n\nNộp đơn trước 3 ngày.",
     "Nộp đơn trước 3 ngày."),
    ("```text\nmã\n```\nNộp đơn trước 3 ngày.", "Nộp đơn trước 3 ngày."),
    ("---\n## Kết luận\n- Bước 1", "Bước 1"),
    ("## Kết luận\n---", "Kết luận"),
])
def test_previous_message_takes_the_first_sentence_line_in_order(answer: str, want: str) -> None:
    assert setfit_router.previous_message([("q", answer)], 200) == want


def test_head_classes_must_be_integers() -> None:
    encoder = FakeSetFitEncoder({}, 2)
    with pytest.raises(setfit_router.ClassifierUnavailable):
        setfit_router.SetFitClassifier(encoder, np.zeros((2, 2)), np.zeros(2),
                                       np.array([0.7, 1.2]), spec())


def test_previous_message_is_cut_at_a_word_boundary() -> None:
    answer = "một hai ba bốn năm sáu bảy tám chín mười"
    cut = setfit_router.previous_message([("q", answer)], 20)
    assert cut is not None and len(cut) <= 20 and answer.startswith(cut)
    assert not cut.endswith(" ")


def test_previous_message_is_none_without_history_or_readable_text() -> None:
    assert setfit_router.previous_message([], 200) is None
    assert setfit_router.previous_message([("q", " [1][2] ")], 200) is None


def test_a_long_question_is_cut_to_the_configured_length() -> None:
    head, encoder = classifier(max_input_chars=10)
    head.classify("x" * 50)
    assert encoder.inputs == ["x" * 10]


# -- label groups and actions --------------------------------------------------------------------

@pytest.mark.parametrize(("label", "action"), [
    ("greeting", router.ACTION_TEMPLATE), ("abuse_only", router.ACTION_TEMPLATE),
    ("legal_medical", router.ACTION_DISCLAIMER), ("action_request", router.ACTION_DISCLAIMER),
    ("off_topic", router.ACTION_OUT_OF_SCOPE),
    ("sop_question", router.ACTION_RAG), ("about_source", router.ACTION_RAG),
])
def test_actions_follow_the_config_groups(label: str, action: str) -> None:
    head, _ = classifier(table={label: label})
    decision = head.classify(label)
    assert (decision.label, decision.action) == (label, action)
    assert decision.confidence > 0.5


def test_a_deferred_label_cannot_be_a_template_label() -> None:
    with pytest.raises(ValueError, match="deferred"):
        spec(deferred_labels=frozenset({"greeting"}))


def test_a_group_naming_an_unknown_label_is_refused() -> None:
    with pytest.raises(ValueError, match="not in labels"):
        spec(template_labels=frozenset({"nonsense"}))


def test_models_yaml_declares_the_classifier_groups_and_artifact_path() -> None:
    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    s = config.router_classifier(SERVICE_ROOT)
    assert len(s.labels) == 14
    assert s.template_labels == {"greeting", "thanks", "about_bot", "abuse_only"}
    assert s.deferred_labels == {"off_topic", "legal_medical", "personal_data",
                                 "abuse_with_question", "about_source"}
    assert s.artifact_dir == SERVICE_ROOT / "models" / "setfit-router"


# -- loading -------------------------------------------------------------------------------------

def test_a_missing_artifact_is_a_fixed_error(tmp_path: Path) -> None:
    with pytest.raises(setfit_router.ClassifierUnavailable, match="not found"):
        setfit_router.load_classifier(spec(artifact_dir=tmp_path))


def test_labels_that_differ_from_the_config_are_refused(tmp_path: Path) -> None:
    (tmp_path / "body").mkdir()
    np.savez(tmp_path / "head.npz", coef=np.zeros((2, 2)), intercept=np.zeros(2),
             classes=np.arange(2))
    (tmp_path / "labels.json").write_text(json.dumps({"label_names": ["a", "b"]}))
    with pytest.raises(setfit_router.ClassifierUnavailable, match="differ"):
        setfit_router.load_classifier(spec(artifact_dir=tmp_path))


# -- the steps -----------------------------------------------------------------------------------

def ctx(text: str, history: list[tuple[str, str]] | None = None) -> QAContext:
    c = QAContext(question=text, lang="vi")
    c.text = text
    c.history = history or []
    return c


async def test_a_template_label_answers_with_a_fixed_sentence_and_no_retrieval() -> None:
    head, _ = classifier(table={"xin chao": "greeting"})
    c = ctx("xin chao")
    d = await ClassifierRouterStep(head).run(c)
    assert d.kind is DecisionKind.TEMPLATE and d.template_key == "greeting"
    assert c.route_info["layer"] == "setfit" and c.route_info["classifier"]["label"] == "greeting"


async def test_abuse_only_is_recorded_as_an_input_flag() -> None:
    head, _ = classifier(table={"du ma": "abuse_only"})
    c = ctx("du ma")
    await ClassifierRouterStep(head).run(c)
    assert [(e.layer, e.rule_id) for e in c.guard_events] == [("INPUT_FLAG", "router.abuse")]


@pytest.mark.parametrize("label", ["sop_question", "about_source", "off_topic", "legal_medical"])
async def test_every_other_label_goes_on_to_retrieval(label: str) -> None:
    head, _ = classifier(table={"q": label})
    d = await ClassifierRouterStep(head).run(ctx("q"))
    assert d.kind is DecisionKind.CONTINUE


async def test_disclaimer_labels_add_the_disclaimer_and_off_topic_waits_for_the_gate() -> None:
    head, _ = classifier(table={"hop dong": "legal_medical", "thoi tiet": "off_topic"})
    legal = ctx("hop dong")
    await ClassifierRouterStep(head).run(legal)
    assert legal.checks["disclaimers"] == ["legal_medical"] and not legal.classifier_off_topic
    weather = ctx("thoi tiet")
    await ClassifierRouterStep(head).run(weather)
    assert weather.classifier_off_topic and "disclaimers" not in weather.checks


async def test_the_step_sends_the_previous_message_when_there_is_history() -> None:
    head, encoder = classifier(table={"cam on": "thanks"})
    c = ctx("cam on", [("q", "Nộp đơn trước 3 ngày [1]. Rồi chờ duyệt.")])
    await ClassifierRouterStep(head).run(c)
    assert encoder.inputs == ["Previous message: Nộp đơn trước 3 ngày.\nCurrent message: cam on"]
    assert c.route_info["classifier"]["withPrevious"] is True


async def test_a_classifier_failure_never_blocks_the_question() -> None:
    head, encoder = classifier()
    encoder.fail = True
    c = ctx("q")
    d = await ClassifierRouterStep(head).run(c)
    assert d.kind is DecisionKind.CONTINUE
    assert c.route_info["classifier"]["error"] == "CLASSIFIER_ERROR"
    assert "encoder down" not in json.dumps(c.route_info)


async def test_classify_question_records_label_confidence_and_mode() -> None:
    head, _ = classifier(table={"q": "sop_question"})
    c = ctx("q")
    decision = await classify_question(head, c, "shadow")
    entry = c.route_info["classifier"]
    assert decision is not None and decision is c.classifier
    assert (entry["mode"], entry["label"], entry["action"]) == ("shadow", "sop_question", "rag")
    assert 0.5 < entry["confidence"] <= 1.0 and "classifier" in c.timings


# -- the flag ------------------------------------------------------------------------------------

def service(**kw) -> QAService:  # noqa: ANN003
    return QAService(None, Retriever(BowEmbedder(), RetrievalConfig()),  # type: ignore[arg-type]
                     ScriptedChain(), ScriptedChain(), context=ContextConfig(),
                     quota=QuotaCounter(None), **kw)  # type: ignore[arg-type]


def names(svc: QAService) -> tuple[str, ...]:
    return tuple(s.name for s in svc.steps())


def settings_with(**extra: str) -> Settings:
    return Settings.model_validate({"SOPILOT_DB_URL": "postgresql://unused",
                                    "SOPILOT_INTERNAL_TOKEN": "t", **extra})


def test_the_classifier_mode_is_off_by_default() -> None:
    assert settings_with().router_classifier_mode == "off"


def test_an_unknown_classifier_mode_is_a_startup_error() -> None:
    with pytest.raises(ValueError):
        settings_with(SOPILOT_ROUTER_CLASSIFIER_MODE="maybe")


def test_mode_off_is_exactly_the_v2_27_chain_even_with_a_classifier() -> None:
    head, _ = classifier()
    plain = tuple(n for n in STEP_ORDER if n != "setfit_router")
    with_layer = service(classifier=head, classifier_mode="off", semantic=object())  # type: ignore[arg-type]
    assert names(with_layer) == plain
    assert names(service(classifier=head, classifier_mode="off")) == tuple(
        n for n in plain if n != "semantic_router")


def test_mode_shadow_leaves_the_chain_unchanged() -> None:
    head, _ = classifier()
    assert names(service(classifier=head, classifier_mode="shadow")) == tuple(
        n for n in STEP_ORDER if n not in ("semantic_router", "setfit_router"))


def test_mode_on_replaces_the_semantic_layer_in_the_same_slot() -> None:
    head, _ = classifier()
    got = names(service(classifier=head, classifier_mode="on", semantic=object()))  # type: ignore[arg-type]
    assert got == tuple(n for n in STEP_ORDER if n != "semantic_router")
    assert got.index("setfit_router") == STEP_ORDER.index("semantic_router")


async def test_shadow_records_the_rule_decision_and_the_classifier_and_routes_nothing() -> None:
    head, _ = classifier(table={"xin chao": "greeting"})
    svc = service(classifier=head, classifier_mode="shadow")
    c = ctx("xin chao")
    c.route_info["steps"] = ["quota", "input", "pii", "frame", "guard", "router"]
    c.route_info["decided_by"] = "router"  # the rules answered this one
    await svc._shadow(c)  # noqa: SLF001
    entry = c.route_info["classifier"]
    assert entry["label"] == "greeting" and entry["mode"] == "shadow"
    assert entry["rule"] == {"decidedBy": "router", "layer": None}
    assert not c.classifier_off_topic and "intent" not in c.route_info


async def test_shadow_skips_a_question_the_input_step_rejected() -> None:
    head, _ = classifier()
    svc = service(classifier=head, classifier_mode="shadow")
    c = ctx("")
    await svc._shadow(c)  # noqa: SLF001
    assert "classifier" not in c.route_info


# -- the real artifact (opt in: SOPILOT_TEST_REAL_CLASSIFIER=1) ----------------------------------

REPO = SERVICE_ROOT.parents[1]
REAL_DIR = Path(os.environ.get("SOPILOT_ROUTER_CLASSIFIER_DIR") or
                REPO / "eval/results/routing/setfit-router-model-histaug/setfit-router")
# Written by eval/experiments/routing/artifact_reference.py (plain sentence-transformers, batched,
# numpy head): the saved artifact is not the model that scored the training job (ADR-012 §5).
REF = REAL_DIR.parent / "artifact_reference.jsonl"
TEST = REPO / "eval/datasets/routing/test.jsonl"


@pytest.mark.skipif(
    os.environ.get("SOPILOT_TEST_REAL_CLASSIFIER") != "1"
    or not (REAL_DIR / "head.npz").is_file() or not REF.is_file() or not TEST.is_file(),
    reason="opt in with SOPILOT_TEST_REAL_CLASSIFIER=1; needs the artifact and its reference")
def test_the_real_artifact_matches_its_independent_reference() -> None:
    """Argmax identical and probabilities within 0.001 of the batched reference (reproduction
    only; the frozen test split is never used to tune anything)."""
    pytest.importorskip("sentence_transformers")
    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    head = setfit_router.load_classifier(
        replace(config.router_classifier(SERVICE_ROOT), artifact_dir=REAL_DIR))
    ref = {r["id"]: r for r in map(json.loads, REF.read_text(encoding="utf-8").splitlines())}
    rows = [json.loads(ln) for ln in TEST.read_text(encoding="utf-8").splitlines() if ln.strip()]
    worst = 0.0
    for row in rows:
        got = head.probabilities(row["text"], row.get("previous_turn") or None)
        want = np.array(ref[row["id"]]["proba"])
        assert int(np.argmax(got)) == int(np.argmax(want)), row["id"]
        worst = max(worst, float(np.abs(got - want).max()))
    assert worst < 0.001


# -- review fixes: shadow never touches a raw question or a finished answer ------------------------

async def test_shadow_does_not_classify_a_question_the_pii_step_never_masked() -> None:
    head, encoder = classifier(table={"q": "sop_question"})
    svc = service(classifier=head, classifier_mode="shadow")
    c = ctx("q " + "x" * 1200)  # too long: the chain stopped at the input step, text is still raw
    c.route_info["steps"] = ["quota", "input"]
    await svc._shadow(c)  # noqa: SLF001
    assert "classifier" not in c.route_info and encoder.inputs == []


async def test_shadow_classifies_after_the_pii_step_and_survives_a_failure() -> None:
    head, encoder = classifier(table={"q": "sop_question"})
    svc = service(classifier=head, classifier_mode="shadow")
    ok = ctx("q")
    ok.route_info["steps"] = ["quota", "input", "pii"]
    await svc._shadow(ok)  # noqa: SLF001
    assert ok.route_info["classifier"]["label"] == "sop_question"
    encoder.fail = True
    bad = ctx("q")
    bad.route_info["steps"] = ["quota", "input", "pii"]
    bad.history = [("q", None)]  # a broken history row must not escape either
    await svc._shadow(bad)  # noqa: SLF001
    assert bad.route_info["classifier"]["error"] == "CLASSIFIER_ERROR"


def test_a_numbered_list_answer_gives_the_sentence_after_the_number() -> None:
    history = [("q", "1. Nộp đơn trước 3 ngày. 2. Chờ duyệt.")]
    assert setfit_router.previous_message(history, 200) == "Nộp đơn trước 3 ngày."


@pytest.mark.parametrize("kw", [
    {"template_labels": frozenset({"sop_question"})},
    {"template_labels": frozenset({"greeting"}), "disclaimer_labels": frozenset({"greeting"})},
    {"out_of_scope_label": "greeting"},
])
def test_overlapping_or_unsafe_label_groups_are_refused(kw: dict) -> None:
    with pytest.raises(ValueError):
        spec(**kw)


def test_a_malformed_head_is_refused_at_load() -> None:
    encoder = FakeSetFitEncoder({}, 2)
    for coef, intercept, classes in (
            (np.zeros((2, 2)), np.zeros(3), np.array([0, 1])),   # intercept length
            (np.zeros((2, 2)), np.zeros(2), np.array([-1, 1])),  # negative class
            (np.zeros((2, 2)), np.zeros(2), np.array([1, 1])),   # duplicate classes
            (np.full((2, 2), np.nan), np.zeros(2), np.array([0, 1])),  # not finite
            (np.zeros((0, 2)), np.zeros(0), np.array([], dtype=int))):  # empty
        with pytest.raises(setfit_router.ClassifierUnavailable):
            setfit_router.SetFitClassifier(encoder, coef, intercept, classes, spec())


async def test_the_factory_loads_nothing_when_off_and_degrades_only_in_shadow(
        tmp_path: Path) -> None:
    from sopilot_ai.conversations.factory import _build_classifier

    config = ModelsConfig.load(SERVICE_ROOT / "config" / "models.yaml")
    base = {"SOPILOT_DB_URL": "postgresql://unused", "SOPILOT_INTERNAL_TOKEN": "t"}
    missing = Settings.model_validate({**base, "SOPILOT_ROUTER_CLASSIFIER_MODE": "shadow"})
    # the default artifact folder does not exist in a fresh checkout
    config.raw["router_classifier"]["artifact_dir"] = str(tmp_path / "absent")
    off = Settings.model_validate(base)
    assert await _build_classifier(config, off) is None
    assert await _build_classifier(config, missing) is None  # shadow: warning, service runs
    broken = ModelsConfig(raw={**config.raw, "router_classifier": {}})
    assert await _build_classifier(broken, missing) is None  # a bad section does not 503 shadow
    on = Settings.model_validate({**base, "SOPILOT_ROUTER_CLASSIFIER_MODE": "on"})
    with pytest.raises(setfit_router.ClassifierUnavailable):
        await _build_classifier(config, on)  # on: a startup error
