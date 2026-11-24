"""Vietnamese SOP system check (V2-28): dataset validation, pipeline run, metrics per group.

This is an acceptance check for the audit changes, not an RQ experiment and not a source of RQ3
thresholds. The sample is small.

Entry points
- :func:`run_system_check`: validates the dataset (schema, spans against the corpus, dev/test
  separation, group sizes), then, unless ``dry_run``, asks every question through an ``asker``.
  The default asker is :class:`ServiceAsker`, which drives the real answer pipeline
  (``sopilot_ai.conversations.service.QAService.answer``; its steps run ``sopilot_ai.qa.pipeline``)
  and needs the local stack. Tests inject fakes through ``asker``.
- ``python -m sopilot_eval.system_check --config configs/vi-sop-check.yaml [--dry-run]``.

Group e is not stored in ``questions.jsonl``. :func:`generate_group_e` derives it from the
hand-written rows with a fixed seed, so every unaccented variant keeps its base question's
evidence and answer.

Paths in the config are resolved against the config file, ``eval/`` and the repository root, so
the command works from any working directory.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from uuid import UUID, uuid4

import yaml

from sopilot_eval.dataset import QUERY_TYPES

EVAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EVAL_ROOT.parent

GROUPS: dict[str, str] = {
    "a": "group_a_merged_cells",
    "b": "group_b_condition_exception",
    "c": "group_c_doc_code",
    "d": "group_d_doc_metadata",
    "e": "group_e_unaccented",
    "f": "group_f_short_docs",
    "g": "group_g_scenario",
    "h": "group_h_refusal_boundaries",
    "i": "group_i_pii_masking",
}
GROUP_E = GROUPS["e"]
LETTER_OF: dict[str, str] = {name: letter for letter, name in GROUPS.items()}
GROUP_ORDER: tuple[str, ...] = tuple(GROUPS.values())
HAND_GROUPS = tuple(g for k, g in GROUPS.items() if k != "e")
# Groups whose answerable rows can seed the generated unaccented variants (group e).
GENERATED_FROM: tuple[str, ...] = tuple(GROUPS[k] for k in "abcdfg")
SPLITS: tuple[str, ...] = ("dev", "test")
REFUSAL_REASONS: tuple[str, ...] = ("OUT_OF_SCOPE", "INPUT_INVALID")
PII_RULES: tuple[str, ...] = ("pii.id", "pii.account", "pii.email", "pii.phone")
UNACCENT_SEED = "vi-sop-check-group-e-v1"
UNACCENT_COUNT = 4  # generated group e rows; split evenly between dev and test
MAX_QUESTION_CHARS = 1000  # ai-service default (SOPILOT_MAX_QUESTION_CHARS)
DOC_CODE_RE = re.compile(r"(?<![\wĐ])[A-ZĐ]{1,6}(?:[-/][A-Z0-9]{1,8}){1,3}(?![\w])")
PII_LEAK_RE = re.compile(r"\d{9,}|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ROW_REQUIRED = ("id", "group", "split", "question", "lang", "answerable", "query_types",
                "evidence_sets", "reference_answer", "expected")


class DatasetError(ValueError):
    """The dataset does not pass validation. ``errors`` lists every problem found."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__(f"{len(self.errors)} dataset error(s)")


class ConfigError(ValueError):
    pass


# -- text helpers ---------------------------------------------------------------------------


def strip_marks(text: str) -> str:
    """Remove Vietnamese diacritics (NFD, drop combining marks, map đ/Đ)."""
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return kept.replace("đ", "d").replace("Đ", "D")


def unaccent(text: str) -> str:
    """A question as a user types it without diacritics: lower case, no punctuation but ``- . / @ :``."""
    out = re.sub(r"[^a-z0-9\s\-./@:]", " ", strip_marks(text).lower())
    return re.sub(r"\s+", " ", out).strip()


def fold(text: str) -> str:
    """Comparison form for expected terms: case-, accent- and punctuation-insensitive."""
    return re.sub(r"[^a-z0-9]+", " ", strip_marks(text).lower()).strip()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# -- files and paths ------------------------------------------------------------------------


def resolve_path(value: str, config_path: Path) -> Path:
    """Resolve a path from the config: absolute, then config dir, ``eval/``, repository root."""
    raw = Path(value)
    if raw.is_absolute():
        return raw
    candidates = [config_path.parent / raw, EVAL_ROOT / raw, REPO_ROOT / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError([f"{path.name}:{number}: invalid JSON"]) from exc
            if not isinstance(row, dict):
                raise DatasetError([f"{path.name}:{number}: expected a JSON object"])
            rows.append(row)
    return rows


def load_questions(path: Path) -> list[dict[str, Any]]:
    """Rows of ``questions.jsonl`` (kept for callers that only need the rows)."""
    return read_jsonl(path)


# -- schema and dataset validation ----------------------------------------------------------


def _corpus_texts(manifest: dict[str, Any], root: Path) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    errors: list[str] = []
    for doc in manifest.get("documents", []):
        doc_id = doc.get("doc_id", "?")
        path = root / str(doc.get("path", ""))
        if not path.is_file():
            errors.append(f"document {doc_id}: missing file {doc.get('path')}")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != doc.get("sha256"):
            errors.append(f"document {doc_id}: sha256 differs from manifest.json")
        texts[doc_id] = data.decode("utf-8")
    return texts, errors


def validate_spans(spans: dict[str, dict[str, Any]], texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for sid, span in spans.items():
        doc = span.get("doc_id")
        if doc not in texts:
            errors.append(f"span {sid}: unknown doc_id {doc!r}")
            continue
        start, end, quote = span.get("start_char"), span.get("end_char"), span.get("quote")
        if not isinstance(start, int) or not isinstance(end, int) or not quote:
            errors.append(f"span {sid}: start_char, end_char and quote are required")
            continue
        if texts[doc][start:end] != quote:
            errors.append(f"span {sid}: quote is not at offsets {start}:{end} of {doc}")
        if sha_text(quote) != span.get("quote_sha"):
            errors.append(f"span {sid}: quote_sha does not match quote")
        if texts[doc].count(quote) != 1:
            errors.append(f"span {sid}: quote must occur exactly once in {doc}")
    return errors


def validate_rows(rows: Sequence[dict[str, Any]], spans: dict[str, dict[str, Any]]) -> list[str]:
    """Schema of every question row (V2-06 fields plus the checker's expectations)."""
    errors: list[str] = []
    seen: Counter[str] = Counter(str(r.get("id")) for r in rows)
    for rid, n in seen.items():
        if n > 1:
            errors.append(f"{rid}: duplicate id")
    for row in rows:
        rid = str(row.get("id", "?"))
        missing = [k for k in ROW_REQUIRED if k not in row]
        if missing:
            errors.append(f"{rid}: missing {', '.join(missing)}")
            continue
        group = row["group"]
        letter = LETTER_OF.get(group, "?")
        if group not in GROUP_ORDER:
            errors.append(f"{rid}: unknown group {group!r}")
        if group == GROUP_E and not row.get("generated"):
            errors.append(f"{rid}: group e is generated by system_check, not stored by hand")
        if row["split"] not in SPLITS:
            errors.append(f"{rid}: split must be dev or test")
        if not str(row["question"]).strip():
            errors.append(f"{rid}: empty question")
        if row["lang"] != "vi":
            errors.append(f"{rid}: lang must be vi")
        if not str(row["reference_answer"]).strip():
            errors.append(f"{rid}: empty reference_answer")
        qtypes = row["query_types"]
        if not isinstance(qtypes, list) or not set(qtypes) <= QUERY_TYPES:
            errors.append(f"{rid}: query_types must be a list of {sorted(QUERY_TYPES)}")
        if "expected_terms" in row and (
                not isinstance(row["expected_terms"], list)
                or not all(isinstance(t, str) and t.strip() for t in row["expected_terms"])):
            errors.append(f"{rid}: expected_terms must be a list of non-empty strings")
        evidence = row["evidence_sets"]
        if not isinstance(evidence, list) or not all(isinstance(s, list) for s in evidence):
            errors.append(f"{rid}: evidence_sets must be a list of lists of span ids")
            continue
        span_ids = [s for group_set in evidence for s in group_set]
        for sid in span_ids:
            if sid not in spans:
                errors.append(f"{rid}: unknown span {sid}")
        expected_docs = sorted({spans[s]["doc_id"] for s in span_ids if s in spans})
        declared = sorted({e.get("doc") for e in row["expected"] if isinstance(e, dict)})
        if declared != sorted(f"{d}.md" for d in expected_docs):
            errors.append(f"{rid}: expected.doc must be derived from evidence_sets")
        if row["answerable"]:
            if letter in ("h", "i"):
                errors.append(f"{rid}: group {letter} rows are not answerable")
            if not evidence or not all(evidence) or not qtypes:
                errors.append(f"{rid}: answerable rows need evidence_sets and query_types")
            if "expected_terms" not in row:
                errors.append(f"{rid}: answerable rows need expected_terms")
        else:
            if evidence:
                errors.append(f"{rid}: unanswerable rows must not have evidence_sets")
            if letter not in ("h", "i"):
                errors.append(f"{rid}: only groups h and i may be unanswerable")
        if letter == "h" and row.get("expected_refusal") not in REFUSAL_REASONS:
            errors.append(f"{rid}: group h needs expected_refusal in {REFUSAL_REASONS}")
        if letter == "i" and row.get("expected_pii_rule") not in PII_RULES:
            errors.append(f"{rid}: group i needs expected_pii_rule in {PII_RULES}")
        if letter == "c":
            code = row.get("doc_code")
            if not code or "".join(str(code).upper().split()) not in {
                    "".join(m.upper().split()) for m in DOC_CODE_RE.findall(row["question"].upper())}:
                errors.append(f"{rid}: group c question must contain doc_code")
        if len(row["question"]) > MAX_QUESTION_CHARS and row.get("expected_refusal") != "INPUT_INVALID":
            errors.append(f"{rid}: over {MAX_QUESTION_CHARS} characters must expect INPUT_INVALID")
    used = {s for r in rows for group_set in r.get("evidence_sets", []) for s in group_set}
    for sid in spans:
        if sid not in used:
            errors.append(f"span {sid}: not used by any question")
    return errors


def validate_split_separation(rows: Sequence[dict[str, Any]]) -> list[str]:
    """Dev and test must share no question text and no evidence span."""
    errors: list[str] = []
    span_splits: dict[str, set[str]] = defaultdict(set)
    question_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        question_splits[row["question"].strip()].add(row["split"])
        for group_set in row.get("evidence_sets", []):
            for sid in group_set:
                span_splits[sid].add(row["split"])
    for sid, splits in span_splits.items():
        if len(splits) > 1:
            errors.append(f"span {sid} is used by both dev and test")
    for question, splits in question_splits.items():
        if len(splits) > 1:
            errors.append(f"question text appears in both dev and test: {question[:60]}")
    return errors


def validate_group_sizes(rows: Sequence[dict[str, Any]], min_rows: int) -> list[str]:
    errors: list[str] = []
    for group in GROUP_ORDER:
        group_rows = [r for r in rows if r["group"] == group]
        if len(group_rows) < min_rows:
            errors.append(f"{group}: {len(group_rows)} rows, minimum is {min_rows}")
        for split in SPLITS:
            if not any(r["split"] == split for r in group_rows):
                errors.append(f"{group}: no {split} row")
    return errors


def _span_index(spans_rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for span in spans_rows:
        sid = str(span.get("span_id"))
        if sid in index:
            raise DatasetError([f"span {sid}: duplicate span_id"])
        index[sid] = span
    return index


@dataclass
class Dataset:
    root: Path
    hand_rows: list[dict[str, Any]]
    spans: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
    texts: dict[str, str]
    errors: list[str] = field(default_factory=list)


def load_dataset(questions_path: Path) -> Dataset:
    """Read and check the files next to ``questions.jsonl``; raises nothing, reports in ``errors``."""
    root = questions_path.parent
    manifest_path = root / "manifest.json"
    evidence_path = root / "evidence.jsonl"
    for needed in (questions_path, evidence_path, manifest_path):
        if not needed.is_file():
            raise DatasetError([f"missing file {needed}"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spans = _span_index(read_jsonl(evidence_path))
    rows = read_jsonl(questions_path)
    texts, errors = _corpus_texts(manifest, root)
    errors += validate_spans(spans, texts)
    errors += validate_rows(rows, spans)
    errors += validate_split_separation(rows)
    return Dataset(root=root, hand_rows=rows, spans=spans, manifest=manifest, texts=texts,
                   errors=errors)


def generate_group_e(rows: Sequence[dict[str, Any]], *, seed: str = UNACCENT_SEED,
                     count: int = UNACCENT_COUNT) -> list[dict[str, Any]]:
    """Group e: unaccented variants of answerable questions (deterministic).

    Eligible base rows are answerable, carry diacritics and belong to :data:`GENERATED_FROM`. For
    each split the base rows are ordered by ``sha256(seed:id)`` and the first ``count // 2`` are
    taken, so the same seed always yields the same rows. Each variant copies its base's split,
    evidence, expected terms and reference answer, so dev and test stay separate.
    """
    eligible = [r for r in rows if r["group"] in GENERATED_FROM and r["answerable"]
                and strip_marks(r["question"]) != r["question"]]

    def order(row: dict[str, Any]) -> str:
        return hashlib.sha256(f"{seed}:{row['id']}".encode()).hexdigest()

    per_split = count // len(SPLITS)
    picked: list[dict[str, Any]] = []
    for split in SPLITS:
        pool = sorted((r for r in eligible if r["split"] == split), key=order)
        picked.extend(pool[:per_split])
    generated: list[dict[str, Any]] = []
    for base in sorted(picked, key=lambda r: r["id"]):
        suffix = base["id"].removeprefix("vi-sop-")
        variant = {k: base[k] for k in ("split", "lang", "corpus_lang", "cross_lingual",
                                        "answerable", "query_types", "evidence_sets",
                                        "reference_answer", "expected") if k in base}
        if "expected_terms" in base:
            variant["expected_terms"] = base["expected_terms"]
        variant.update({
            "id": f"vi-sop-e-{suffix}", "group": GROUP_E, "question": unaccent(base["question"]),
            "base_id": base["id"], "unaccented": True, "generated": True,
            "label_version": base.get("label_version"),
            "drafted_by": "generated by system_check.generate_group_e",
        })
        generated.append(variant)
    return generated


def build_rows(dataset: Dataset) -> list[dict[str, Any]]:
    return [*dataset.hand_rows, *generate_group_e(dataset.hand_rows)]


# -- answers and scoring --------------------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    doc_id: str
    start: int | None = None  # character offsets in the document's canonical text
    end: int | None = None


@dataclass(frozen=True)
class Answer:
    outcome: str  # ANSWERED, TEMPLATE, REFUSED_GUARD, REFUSED_NO_EVIDENCE, ERROR, ...
    refusal_reason: str | None = None  # OUT_OF_SCOPE, INPUT_INVALID, NO_EVIDENCE, ...
    text: str = ""
    citations: tuple[Citation, ...] = ()
    # Retrieved context as (doc_id, start, end) ranges. None = not measured by this asker.
    context_spans: tuple[tuple[str, int, int], ...] | None = None


Asker = Callable[[str], Awaitable[Answer]]


@dataclass(frozen=True)
class RowResult:
    id: str
    group: str
    split: str
    query_types: tuple[str, ...]
    answerable: bool
    passed: bool
    outcome: str
    refusal_reason: str | None
    checks: dict[str, bool | None]
    citation_total: int = 0
    citation_hits: int = 0
    gold_in_context: bool | None = None
    answer_chars: int = 0
    error: str | None = None


def _gold_sets(row: dict[str, Any], spans: dict[str, dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [[spans[s] for s in group_set] for group_set in row["evidence_sets"]]


def _overlaps(citation: Citation, span: dict[str, Any]) -> bool:
    if citation.doc_id != span["doc_id"] or citation.start is None or citation.end is None:
        return False
    return citation.start < span["end_char"] and citation.end > span["start_char"]


def _inside(span: dict[str, Any], context: tuple[str, int, int]) -> bool:
    doc, start, end = context
    return doc == span["doc_id"] and start <= span["start_char"] and span["end_char"] <= end


def mask_rules(question: str) -> set[str]:
    """PII rules that fire on the question, using the ai-service masking step."""
    from sopilot_ai.qa.pii import mask_pii

    return set(mask_pii(question).rule_ids)


def score_row(row: dict[str, Any], spans: dict[str, dict[str, Any]], answer: Answer) -> RowResult:
    """Pass/fail for one row. Pass criteria are in the module docstring and README."""
    group = row["group"]
    checks: dict[str, bool | None] = {}
    citation_total = citation_hits = 0
    gold_in_context: bool | None = None
    if group == GROUPS["h"]:
        checks["refused"] = answer.outcome != "ANSWERED"
        checks["refusal_reason_ok"] = answer.refusal_reason == row["expected_refusal"]
        passed = bool(checks["refused"] and checks["refusal_reason_ok"])
    elif group == GROUPS["i"]:
        checks["pii_rule_fired"] = row["expected_pii_rule"] in mask_rules(row["question"])
        checks["no_pii_in_answer"] = not PII_LEAK_RE.search(answer.text or "")
        passed = bool(checks["pii_rule_fired"] and checks["no_pii_in_answer"])
    else:
        gold_sets = _gold_sets(row, spans)
        checks["answered"] = answer.outcome == "ANSWERED"
        folded = fold(answer.text)
        checks["terms_ok"] = all(fold(t) in folded for t in row["expected_terms"])
        cited = [c for c in answer.citations]
        citation_total = len(cited)
        citation_hits = sum(1 for c in cited if any(_overlaps(c, s) for g in gold_sets for s in g))
        checks["gold_cited"] = any(
            all(any(_overlaps(c, s) for c in cited) for s in group_set) for group_set in gold_sets)
        if answer.context_spans is not None:
            contexts = answer.context_spans
            gold_in_context = any(
                all(any(_inside(s, ctx) for ctx in contexts) for s in group_set)
                for group_set in gold_sets)
        checks["gold_in_context"] = gold_in_context
        passed = bool(checks["answered"] and checks["terms_ok"] and checks["gold_cited"])
    if answer.outcome == "ERROR":  # a failed call never passes, whatever the group
        passed = False
    return RowResult(
        id=row["id"], group=group, split=row["split"], query_types=tuple(row["query_types"]),
        answerable=bool(row["answerable"]), passed=passed, outcome=answer.outcome,
        refusal_reason=answer.refusal_reason, checks=checks, citation_total=citation_total,
        citation_hits=citation_hits, gold_in_context=gold_in_context,
        answer_chars=len(answer.text or ""))


async def run_questions(rows: Sequence[dict[str, Any]], spans: dict[str, dict[str, Any]],
                        asker: Asker) -> list[RowResult]:
    """Ask every row in order. An exception from the asker fails that row, not the run."""
    results: list[RowResult] = []
    for row in rows:
        try:
            answer = await asker(row["question"])
        except Exception as exc:  # noqa: BLE001 - recorded as a failed row; message not kept
            answer = Answer(outcome="ERROR", refusal_reason=None, text="")
            result = score_row(row, spans, answer)
            results.append(RowResult(**{**result.__dict__, "error": type(exc).__name__}))
            continue
        results.append(score_row(row, spans, answer))
    return results


# -- metrics --------------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _summary(results: Sequence[RowResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(r.passed for r in results)
    measured = [r for r in results if r.gold_in_context is not None]
    cited_total = sum(r.citation_total for r in results)
    cited_hits = sum(r.citation_hits for r in results)
    answerable = [r for r in results if r.answerable]
    return {
        "total": total,
        "passed": passed,
        "pass_rate": _rate(passed, total),
        "answered_rate": _rate(sum(r.outcome == "ANSWERED" for r in answerable), len(answerable)),
        "gold_in_context_rate": _rate(sum(bool(r.gold_in_context) for r in measured), len(measured)),
        "citation_precision": _rate(cited_hits, cited_total),
        "refusal_reason_rate": _rate(sum(bool(r.checks.get("refusal_reason_ok")) for r in results
                                         if "refusal_reason_ok" in r.checks),
                                     sum("refusal_reason_ok" in r.checks for r in results)),
        "pii_masked_rate": _rate(sum(r.passed for r in results if "pii_rule_fired" in r.checks),
                                 sum("pii_rule_fired" in r.checks for r in results)),
    }


def summarize(results: Sequence[RowResult], min_group_rate: float, min_overall_rate: float,
              expected_groups: Sequence[str] = GROUP_ORDER) -> dict[str, Any]:
    by_group = {g: [r for r in results if r.group == g] for g in expected_groups}
    groups = {g: _summary(rs) for g, rs in by_group.items()}
    by_qtype: dict[str, dict[str, Any]] = {}
    for qtype in sorted(QUERY_TYPES):
        rs = [r for r in results if r.answerable and qtype in r.query_types]
        if rs:
            by_qtype[qtype] = {"total": len(rs), "passed": sum(r.passed for r in rs),
                               "pass_rate": _rate(sum(r.passed for r in rs), len(rs))}
    splits = {s: _summary([r for r in results if r.split == s]) for s in SPLITS
              if any(r.split == s for r in results)}
    overall = _summary(results)
    failing = [g for g, s in groups.items() if s["total"] == 0 or (s["pass_rate"] or 0) < min_group_rate]
    passed_acceptance = bool(results) and not failing and (overall["pass_rate"] or 0) >= min_overall_rate
    return {"groups": groups, "query_types": by_qtype, "splits": splits, "overall": overall,
            "failing_groups": failing, "passed_acceptance": passed_acceptance}


# -- real pipeline asker --------------------------------------------------------------------


class ServiceAsker:
    """Asks questions through ``QAService.answer`` on the local stack (needs Postgres, the
    embedding model and the generation endpoint). Use as an async context manager."""

    def __init__(self, principal: dict[str, str], document_ids: dict[str, str]) -> None:
        self._principal_cfg = principal
        self._document_ids = document_ids
        self._engine: Any = None
        self._service: Any = None
        self._principal: Any = None
        self._doc_by_uuid: dict[str, str] = {}

    async def __aenter__(self) -> Self:
        from sopilot_ai.config import get_settings
        from sopilot_ai.conversations.factory import build_service
        from sopilot_ai.db.engine import make_engine
        from sopilot_ai.retrieval.access_filter import Principal

        settings = get_settings()
        self._principal = Principal(
            user_id=UUID(self._principal_cfg["user_id"]),
            workspace_id=UUID(self._principal_cfg["workspace_id"]),
            role=str(self._principal_cfg["role"]).upper())
        self._doc_by_uuid = {str(v): k for k, v in self._document_ids.items()}
        self._engine = make_engine(settings.db_url.get_secret_value())
        self._service = await build_service(settings, self._engine)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def __call__(self, question: str) -> Answer:
        from sopilot_ai.conversations.service import ConversationRef

        ref = ConversationRef(uuid4(), True)
        outcome: str | None = None
        reason: str | None = None
        text = ""
        citations: list[Citation] = []
        async for event in self._service.answer(self._principal, ref, question, None):
            if event.name == "citations":
                for c in event.data:
                    citations.append(Citation(doc_id=self._doc_by_uuid.get(str(c.get("documentId")), "?"),
                                              start=c.get("charStart"), end=c.get("charEnd")))
            elif event.name == "done":
                outcome = event.data.get("outcome")
                reason = event.data.get("refusalReason")
                text = event.data.get("finalText") or ""
            elif event.name == "error":
                outcome = "ERROR"
        return Answer(outcome=outcome or "ERROR", refusal_reason=reason, text=text,
                      citations=tuple(citations), context_spans=None)


# -- config and orchestration ---------------------------------------------------------------


def load_config(config_path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for key in ("name", "dataset"):
        if key not in cfg:
            raise ConfigError(f"config {config_path.name} needs {key}")
    cfg["_questions_path"] = resolve_path(str(cfg["dataset"]), config_path)
    output = str(cfg.get("output_dir", "eval/results/vi-sop-check"))
    cfg["_output_dir"] = resolve_path(output, config_path)
    cfg.setdefault("acceptance", {})
    return cfg


def _check_run_config(cfg: dict[str, Any], dataset: Dataset) -> tuple[dict[str, str], dict[str, str]]:
    principal = cfg.get("principal") or {}
    missing = [k for k in ("user_id", "workspace_id", "role") if not principal.get(k)]
    if missing:
        raise ConfigError("run mode needs principal." + ", principal.".join(missing) +
                          " from the local stack (see eval/datasets/vi-sop-check/README.md)")
    document_ids = {str(k): str(v) for k, v in (cfg.get("document_ids") or {}).items() if v}
    absent = sorted(d["doc_id"] for d in dataset.manifest["documents"] if d["doc_id"] not in document_ids)
    if absent:
        raise ConfigError("run mode needs document_ids for: " + ", ".join(absent))
    return principal, document_ids


def run_system_check(config_path: Path, *, asker: Asker | None = None, dry_run: bool = False,
                     split: str = "all", output: Path | None = None) -> dict[str, Any]:
    """Validate, then (unless ``dry_run``) run every selected question and build the report."""
    if split not in ("all", *SPLITS):
        raise ConfigError("split must be all, dev or test")
    cfg = load_config(config_path)
    dataset = load_dataset(cfg["_questions_path"])
    if dataset.errors:
        raise DatasetError(dataset.errors)
    rows = build_rows(dataset)
    min_rows = int(cfg["acceptance"].get("min_rows_per_group", 4))
    size_errors = validate_group_sizes(rows, min_rows)
    if size_errors:
        raise DatasetError(size_errors)
    selected = [r for r in rows if split == "all" or r["split"] == split]
    counts = Counter((r["group"], r["split"]) for r in rows)
    report: dict[str, Any] = {
        "name": cfg["name"],
        "mode": "dry-run" if dry_run else "run",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": split,
        "corpus_version": dataset.manifest.get("corpus_version"),
        "dataset": {
            "questions_file_rows": len(dataset.hand_rows), "generated_rows": len(rows) - len(dataset.hand_rows),
            "spans": len(dataset.spans), "documents": len(dataset.manifest["documents"]),
            "group_counts": {g: {s: counts[(g, s)] for s in SPLITS} for g in GROUP_ORDER},
            "schema_errors": 0,
        },
        "thresholds": {"min_group_pass_rate": float(cfg["acceptance"].get("min_group_pass_rate", 0.8)),
                       "min_overall_pass_rate": float(cfg["acceptance"].get("min_overall_pass_rate", 0.8)),
                       "min_rows_per_group": min_rows,
                       "status": "proposed; the ticket gives no numeric threshold; owner to confirm"},
        "recorded_only": {"parameters": cfg.get("parameters", {}),
                          "temperature": cfg.get("temperature"), "max_tokens": cfg.get("max_tokens")},
        "notes": [
            "Not an RQ experiment; the sample is small (V2-28).",
            "reference_answer is recorded for owner review and is not scored automatically.",
            "gold_in_context is measured only when the asker reports context_spans (ServiceAsker does not yet).",
            "Knowledge-gap list (FR-17) is not measured by this runner.",
        ],
    }
    if dry_run:
        report["passed_acceptance"] = None
        return report
    if asker is None:
        principal, document_ids = _check_run_config(cfg, dataset)
        results = asyncio.run(_run_with_service(principal, document_ids, selected, dataset.spans))
    else:
        results = asyncio.run(run_questions(selected, dataset.spans, asker))
    summary = summarize(results, report["thresholds"]["min_group_pass_rate"],
                        report["thresholds"]["min_overall_pass_rate"])
    report.update(summary)
    report["rows"] = [_row_json(r) for r in results]
    target = output or (cfg["_output_dir"] / f"{cfg['name']}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["output_path"] = str(target)
    return report


async def _run_with_service(principal: dict[str, str], document_ids: dict[str, str],
                            rows: Sequence[dict[str, Any]], spans: dict[str, dict[str, Any]]) -> list[RowResult]:
    async with ServiceAsker(principal, document_ids) as asker:
        return await run_questions(rows, spans, asker)


def _row_json(r: RowResult) -> dict[str, Any]:
    return {"id": r.id, "group": r.group, "split": r.split, "passed": r.passed,
            "outcome": r.outcome, "refusal_reason": r.refusal_reason, "checks": r.checks,
            "citation_total": r.citation_total, "citation_hits": r.citation_hits,
            "gold_in_context": r.gold_in_context, "answer_chars": r.answer_chars, "error": r.error}


def format_report(report: dict[str, Any]) -> str:
    lines = [
        "=" * 78,
        f"Vietnamese SOP system check ({report['name']}), mode={report['mode']}, split={report['split']}",
        (f"Rows: {report['dataset']['questions_file_rows']} stored + {report['dataset']['generated_rows']} "
         f"generated (group e); spans {report['dataset']['spans']}; corpus {report['corpus_version']}"),
        "-" * 78,
        f"{'group':32s}{'dev':>5s}{'test':>6s}",
    ]
    for group, counts in report["dataset"]["group_counts"].items():
        lines.append(f"{group:32s}{counts['dev']:>5d}{counts['test']:>6d}")
    if report["mode"] == "dry-run":
        lines += ["-" * 78, "dry-run: dataset validated; no services were contacted.", "=" * 78]
        return "\n".join(lines)
    lines += ["-" * 78, f"{'group':32s}{'n':>4s}{'pass':>6s}{'rate':>8s}{'cited':>8s}{'in-ctx':>8s}"]
    for group, s in report["groups"].items():
        lines.append(f"{group:32s}{s['total']:>4d}{s['passed']:>6d}{_fmt(s['pass_rate']):>8s}"
                     f"{_fmt(s['citation_precision']):>8s}{_fmt(s['gold_in_context_rate']):>8s}")
    o = report["overall"]
    lines.append(f"{'OVERALL':32s}{o['total']:>4d}{o['passed']:>6d}{_fmt(o['pass_rate']):>8s}")
    lines += ["-" * 78, "By query_type (answerable rows):"]
    for qtype, s in report["query_types"].items():
        lines.append(f"  {qtype:22s} {s['passed']}/{s['total']}  {_fmt(s['pass_rate'])}")
    failing = ", ".join(report["failing_groups"]) or "none"
    lines += ["-" * 78,
              f"passed_acceptance={report['passed_acceptance']} (failing groups: {failing})",
              "=" * 78]
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Vietnamese SOP system check (V2-28)")
    parser.add_argument("--config", required=True, help="path to configs/vi-sop-check.yaml")
    parser.add_argument("--dry-run", action="store_true", help="validate the dataset only; no services")
    parser.add_argument("--split", default="all", choices=["all", *SPLITS])
    parser.add_argument("--output", help="JSON report path (default: output_dir in the config)")
    args = parser.parse_args(argv)
    try:
        report = run_system_check(Path(args.config), dry_run=args.dry_run, split=args.split,
                                  output=Path(args.output) if args.output else None)
    except DatasetError as exc:
        for error in exc.errors:
            sys.stderr.write(f"dataset error: {error}\n")
        return 2
    except ConfigError as exc:
        sys.stderr.write(f"config error: {exc}\n")
        return 2
    sys.stdout.write(format_report(report) + "\n")
    if report.get("output_path"):
        sys.stdout.write(f"report written to {report['output_path']}\n")
    return 0 if report["mode"] == "dry-run" or report["passed_acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
