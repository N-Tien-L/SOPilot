"""SetFit intent classifier behind the rules (V2-44, ADR-012, TECH-V2-ai-service §7.1 step 3).

The body is a fine-tuned ``bge-m3`` sentence-transformers folder; the head is a logistic
regression stored in ``head.npz`` and applied with numpy: ``softmax(embedding @ coef.T +
intercept)``. ``setfit`` is never imported. Labels, deferred set, paths and the input format come
from ``config/models.yaml`` (``RouterClassifierSpec``), not from this module.

The classifier only names a label and an action. It never produces a refusal on its own: harmful
content stays with the guard rules, and ``off_topic`` only matters after the retrieval gate refused.
"""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from sopilot_ai.providers.registry import RouterClassifierSpec
from sopilot_ai.qa.router import (
    ACTION_DISCLAIMER,
    ACTION_OUT_OF_SCOPE,
    ACTION_RAG,
    ACTION_TEMPLATE,
)

_MARKER = re.compile(r"\s*\[\d+(?:\s*[,;]\s*\d+)*\]")
_EMPHASIS = re.compile(r"[*`]+")
_LEADING_MARKUP = re.compile(r"^(?:[\s>\-\u2022*]+|\d+[.)]\s+)+")
_HEADING = re.compile(r"^#+\s*")
_NOT_A_SENTENCE = re.compile(r"^(?:\||```|~~~|[-*_=]{3,}\s*$)")
_BOLD_LINE = re.compile(r"^\*\*([^*]+)\*\*:?\s*$")
_SENTENCE_END = re.compile(r"[.!?…](?=\s|$)")


class ClassifierUnavailable(Exception):
    """The artifact is missing or does not match the config. The message is a fixed phrase."""


class Encoder(Protocol):
    """``SentenceTransformer.encode`` as the classifier uses it (tests pass a fake)."""

    def encode(self, sentences: Sequence[str], **kwargs: Any) -> np.ndarray: ...


@dataclass(frozen=True)
class ClassifierDecision:
    label: str
    confidence: float
    action: str  # ACTION_* of qa.router: template | disclaimer | out_of_scope_candidate | rag


def _bold_heading(line: str) -> bool:
    """A bold line on its own that reads as a title: short, with no sentence end."""
    m = _BOLD_LINE.match(line)
    return bool(m) and len(m.group(1).split()) <= 6 and not _SENTENCE_END.search(m.group(1))


def previous_message(history: Sequence[tuple[str, str]], max_chars: int) -> str | None:
    """The first sentence of the last answer, without ``[n]`` markers, cut at ``max_chars``.

    Training used one short assistant sentence as the previous message. ``None`` when there is no
    history or nothing readable is left, so the input is the bare question as in training.
    """
    if not history:
        return None
    lines: list[str] = []
    fenced = False
    for ln in _MARKER.sub("", history[-1][1]).splitlines():
        ln = ln.strip()
        if ln.startswith(("```", "~~~")):
            fenced = not fenced  # code between fences is never a sentence
        elif ln and not fenced:
            lines.append(ln)
    # In order: the first line that can be a sentence. Headings, table rows, code fences, rules and
    # a bold line on its own are skipped; a heading is the fallback when nothing else is left.
    body = [ln for ln in lines if not ln.startswith("#") and not _NOT_A_SENTENCE.match(ln)
            and not _bold_heading(ln)]
    headings = [_HEADING.sub("", ln) for ln in lines if ln.startswith("#")]
    for candidate in [*body, *headings]:
        text = " ".join(_EMPHASIS.sub("", _LEADING_MARKUP.sub("", candidate)).split())
        if text:
            first = text
            break
    else:
        return None
    end = _SENTENCE_END.search(first)
    if end is not None:
        first = first[:end.end()]
    if len(first) > max_chars:
        cut = first[:max_chars]
        first = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip()
    return first or None


def model_input(spec: RouterClassifierSpec, text: str, previous: str | None) -> str:
    """The training input format: the bare question, or the previous message and the question."""
    current = text[:spec.max_input_chars]
    if not previous:
        return current
    return spec.previous_template.format(previous=previous, current=current)


class SetFitClassifier:
    def __init__(self, encoder: Encoder, coef: np.ndarray, intercept: np.ndarray,
                 classes: np.ndarray, spec: RouterClassifierSpec) -> None:
        coef = np.asarray(coef, dtype=np.float64)
        classes = np.asarray(classes).reshape(-1)
        if not np.issubdtype(classes.dtype, np.integer):
            raise ClassifierUnavailable("classifier head does not match the label list")
        classes = classes.astype(np.int64)
        intercept = np.asarray(intercept, dtype=np.float64).reshape(-1)
        if (coef.ndim != 2 or len(classes) == 0 or coef.shape[0] != len(classes)
                or intercept.shape[0] != len(classes) or classes.min() < 0
                or classes.max() >= len(spec.labels) or len(set(classes.tolist())) != len(classes)
                or not (np.isfinite(coef).all() and np.isfinite(intercept).all())):
            raise ClassifierUnavailable("classifier head does not match the label list")
        self._encoder = encoder
        self._coef = coef
        self._intercept = intercept
        self._classes = classes
        self.spec = spec
        self._lock = threading.Lock()  # one encode at a time: the body is one torch module

    def probabilities(self, text: str, previous: str | None = None) -> np.ndarray:
        """Probabilities in the order of ``spec.labels`` (labels the head never saw get 0)."""
        with self._lock:
            emb = self._encoder.encode([model_input(self.spec, text, previous)],
                                       normalize_embeddings=False, convert_to_numpy=True)
        z = np.asarray(emb, dtype=np.float64).reshape(1, -1) @ self._coef.T + self._intercept
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        p = (e / e.sum(axis=1, keepdims=True))[0]
        out = np.zeros(len(self.spec.labels), dtype=np.float64)
        out[self._classes] = p
        return out

    def action_for(self, label: str) -> str:
        spec = self.spec
        if label in spec.template_labels:
            return ACTION_TEMPLATE
        if label in spec.disclaimer_labels:
            return ACTION_DISCLAIMER
        if label == spec.out_of_scope_label:
            return ACTION_OUT_OF_SCOPE
        return ACTION_RAG

    def classify(self, text: str, previous: str | None = None) -> ClassifierDecision:
        proba = self.probabilities(text, previous)
        best = int(np.argmax(proba))
        label = self.spec.labels[best]
        return ClassifierDecision(label, float(proba[best]), self.action_for(label))


def load_classifier(spec: RouterClassifierSpec) -> SetFitClassifier:
    """Load ``body/`` with sentence-transformers (CPU) and ``head.npz`` with numpy."""
    root = spec.artifact_dir
    body, head, meta = root / "body", root / "head.npz", root / "labels.json"
    if not (body.is_dir() and head.is_file() and meta.is_file()):
        raise ClassifierUnavailable("classifier artifact not found")
    try:
        names = json.loads(meta.read_text(encoding="utf-8"))["label_names"]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ClassifierUnavailable("classifier labels.json is unreadable") from exc
    if list(names) != list(spec.labels):
        raise ClassifierUnavailable("classifier labels differ from config/models.yaml")
    try:
        from sentence_transformers import SentenceTransformer

        data = np.load(head, allow_pickle=False)
        coef, intercept, classes = data["coef"], data["intercept"], data["classes"]
        encoder = SentenceTransformer(str(body), device="cpu")
        encoder.max_seq_length = spec.max_seq_length
        if coef.ndim != 2 or coef.shape[1] != encoder.get_sentence_embedding_dimension():
            raise ClassifierUnavailable("classifier head does not match the encoder")
    except ClassifierUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - only the type reaches the log, never a path or value
        raise ClassifierUnavailable(f"classifier failed to load ({type(exc).__name__})") from exc
    return SetFitClassifier(encoder, coef, intercept, classes, spec)
