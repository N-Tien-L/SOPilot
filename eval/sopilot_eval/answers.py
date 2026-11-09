"""Answer-level evaluation of the QA pipeline (V2-10; RQ3 at answer level, context ablation).

Two commands (``python -m sopilot_eval.answers coverage|answers --help``):

* ``coverage``: no LLM. For every answerable question, how much of the gold evidence ends up in the
  context the model would be given, with ``context.expand`` on and off (TECH-V2-ai-service §6.4a).
* ``answers``: needs the answer LLM (and a judge). Citation precision, refusal accuracy with the
  gate (``NO_EVIDENCE``) and the model's own refusal (``GENERATOR_NOT_FOUND``) kept apart,
  faithfulness on a fixed subset (``temperature = 0``), and the same numbers for ``expand`` on/off.

The context assembly, prompt, citation clean-up and number check are the ai-service functions
(``sopilot_ai.retrieval.context``, ``sopilot_ai.qa``), imported, not copied, so the harness measures
what the service runs (token counts are those of ``index_text``, as the service stores them).
Citation precision: a cited source is *correct* when a **hit** chunk of it overlaps a gold span
(strict); ``citation_precision_source`` accepts any chunk of the source (expanded sections count).
Differences from the service, stated so nobody reads more into the numbers:
the index is in memory (no access filter, one workspace), the prompt has no ``code``/``rev``/
``effective`` attributes (the frozen corpus keeps no extracted metadata), and there is no output
guard (a canary leak is tested in ai-service, not measured here).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sopilot_ai.qa import checks as qa_checks
from sopilot_ai.qa import citations as qa_citations
from sopilot_ai.qa import prompt as qa_prompt
from sopilot_ai.retrieval import fusion
from sopilot_ai.retrieval.context import (
    ChunkInfo,
    ContextConfig,
    GroupKey,
    Source,
    build_sources,
)

from .corpus import Chunk
from .metrics import SPAN_COVER, _covered
from .retrievers import Index, retrieve_candidates

ROOT = Path(__file__).resolve().parents[1]
EVAL_TODAY = date(2026, 11, 9)  # the prompt's "today" line: fixed so a rerun builds the same prompt
CHUNK_TYPES = {"SECTION", "PROCEDURE_STEP", "TABLE", "PROSE"}
GROUPS = ("condition_exception", "multi_passage")  # reported apart (V2-10 ablation)

Complete = Callable[[Sequence[dict[str, str]]], str]


@dataclass(frozen=True)
class _Range:
    """What ``metrics._covered`` reads from a chunk: document and character range."""

    doc_id: str
    char_start: int
    char_end: int


@dataclass
class Setup:
    """The retrieval side of one run: chunks, index, retrieval settings and context settings."""

    chunks: list[Chunk]
    index: Index
    retrieval: dict[str, Any]  # one entry of ``configs`` (retriever, k, weights, ...)
    thresholds: dict[str, float | None]
    context: ContextConfig
    count_tokens: Callable[[str], int]
    spans: dict[str, dict]
    reranker: Any = None
    pool: int = 25
    infos: list[ChunkInfo] = field(init=False)
    groups: dict[GroupKey, list[ChunkInfo]] = field(init=False)
    doc_of: dict[uuid.UUID, str] = field(init=False)

    def __post_init__(self) -> None:
        if any(c.char_start is None or c.doc_id is None for c in self.chunks):
            raise ValueError("answer evaluation needs docproc chunks (char offsets and doc_id)")
        ordinal: dict[str, int] = defaultdict(int)
        order = sorted(range(len(self.chunks)),
                       key=lambda i: (self.chunks[i].doc_id, self.chunks[i].char_start))
        ords = {}
        for i in order:
            ords[i] = ordinal[self.chunks[i].doc_id]
            ordinal[self.chunks[i].doc_id] += 1
        self.doc_of = {}
        self.infos = []
        for i, c in enumerate(self.chunks):
            doc = uuid.uuid5(uuid.NAMESPACE_URL, f"doc:{c.doc_id}")
            self.doc_of[doc] = c.doc_id
            self.infos.append(ChunkInfo(
                chunk_id=uuid.uuid5(uuid.NAMESPACE_URL, f"chunk:{c.doc_id}:{c.char_start}"),
                document_id=doc, version_id=doc, ordinal=ords[i],
                chunk_type=c.kind if c.kind in CHUNK_TYPES else "PROSE",
                section_path=tuple(c.section_path), page_start=c.page, char_start=c.char_start,
                char_end=c.char_end, content=c.text,
                token_count=self.count_tokens(c.index_text or c.text)))  # as the service
        self.groups = defaultdict(list)
        for info in sorted(self.infos, key=lambda x: (x.version_id, x.ordinal)):
            self.groups[(info.version_id, info.section_path)].append(info)

    @property
    def gate_mode(self) -> str:
        mode = self.retrieval["retriever"]
        return "hybrid_rerank" if self.reranker is not None else mode


@dataclass
class Retrieved:
    cands: list[dict]
    gate: float | None
    threshold: float | None
    passed: bool


def retrieve(setup: Setup, question: dict) -> Retrieved:
    cands = retrieve_candidates(setup.index, question["question"], setup.retrieval, setup.reranker,
                                pool=max(setup.pool, setup.retrieval.get("k", 5)),
                                query_lang=question.get("lang"))
    gate = cands[0]["gate"] if cands else None
    threshold = fusion.threshold_for(setup.gate_mode, setup.thresholds)
    return Retrieved(cands, gate, threshold, bool(cands) and fusion.passes(gate, threshold))


def context_for(setup: Setup, retrieved: Retrieved, *, expand: bool) -> list[Source]:
    """The sources the service would put in the prompt for these candidates (§6.4a)."""
    k = setup.retrieval.get("k", 5)
    hits = [setup.infos[c["idx"]] for c in retrieved.cands[:k]]
    cfg = replace(setup.context, expand=expand)
    # Same call as the service; with expand off the groups are ignored (the old behaviour).
    return build_sources(hits, setup.groups, cfg)


def _ranges(setup: Setup, sources: Sequence[Source]) -> list[_Range]:
    return [_Range(setup.doc_of[c.document_id], c.char_start, c.char_end)
            for s in sources for c in s.chunks]


def evidence_in_context(setup: Setup, sources: Sequence[Source], question: dict) -> dict[str, float]:
    """``span_recall`` (best alternative) and ``full`` (some alternative fully covered)."""
    ranges = _ranges(setup, sources)
    best = 0.0
    for es in question["evidence_sets"]:
        covered = sum(_covered(setup.spans[sid], ranges) >= SPAN_COVER for sid in es)
        best = max(best, covered / len(es))
    return {"span_recall": best, "full": 1.0 if best == 1.0 else 0.0}


def _group_names(question: dict) -> list[str]:
    return [g for g in GROUPS if g in question.get("query_types", [])]


def _mean(values: Sequence[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


# -- coverage (no LLM) --------------------------------------------------------------------------

def coverage_report(setup: Setup, questions: Sequence[dict]) -> dict[str, Any]:
    """Evidence coverage and prompt size with ``expand`` on and off, over answerable questions.

    The gate is not applied (coverage is about what the top candidates would put in the prompt);
    ``gate_pass_rate`` says how many of these questions the gate lets through."""
    answerable = [q for q in questions if q["answerable"] and q.get("evidence_sets")]
    retrieved = {q["id"]: retrieve(setup, q) for q in answerable}
    out: dict[str, Any] = {"n_questions": len(answerable), "context_k": setup.retrieval.get("k", 5),
                           "gate_pass_rate": _mean([float(r.passed) for r in retrieved.values()]),
                           "section_max_tokens": setup.context.section_max_tokens,
                           "max_tokens": setup.context.max_tokens, "by_expand": {}}
    for expand in (True, False):
        rows: dict[str, list[dict]] = defaultdict(list)
        for q in answerable:
            sources = context_for(setup, retrieved[q["id"]], expand=expand)
            row = {**evidence_in_context(setup, sources, q),
                   "context_tokens": float(sum(s.tokens for s in sources)),
                   "sources": float(len(sources))}
            for name in ("all", *_group_names(q)):
                rows[name].append(row)
        out["by_expand"]["on" if expand else "off"] = {
            name: {"n": len(rs), **{k: _mean([r[k] for r in rs]) for k in rs[0]}}
            for name, rs in sorted(rows.items())}
    return out


# -- answers ------------------------------------------------------------------------------------

JUDGE_SYSTEM = (
    "You check whether an answer is supported by the given sources. Read the question, the "
    "sources and the answer. Decide only from the sources, never from your own knowledge. "
    'Reply with JSON only: {"verdict": "supported" | "partial" | "unsupported"}. '
    '"supported": every claim of the answer is in the sources. "partial": some claims are, '
    'some are not. "unsupported": the answer says things the sources do not.')
VERDICT_SCORE = {"supported": 1.0, "partial": 0.5, "unsupported": 0.0}


def judge_messages(question: str, sources: Sequence[qa_prompt.SourceText],
                   answer: str) -> list[dict[str, str]]:
    body = "\n\n".join(qa_prompt.render_source(s) for s in sources)
    user = f"Question:\n{question}\n\nSources:\n{body}\n\nAnswer:\n{answer}"
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


def parse_verdict(raw: str) -> str | None:
    """``supported`` / ``partial`` / ``unsupported`` from the judge's reply, else ``None``."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        verdict = json.loads(raw[start:end + 1]).get("verdict")
    except (ValueError, AttributeError):
        return None
    return verdict if verdict in VERDICT_SCORE else None


def fixed_subset(ids: Sequence[str], n: int, seed: str) -> list[str]:
    """``n`` ids chosen by hash order: the same ids for the same seed, whatever the file order."""
    keyed = sorted(ids, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    return sorted(keyed[:n])


@dataclass
class AnswerRow:
    id: str
    answerable: bool
    outcome: str  # ANSWERED | NO_EVIDENCE | GENERATOR_NOT_FOUND
    gate: float | None
    answer: str = ""
    cited: int = 0
    cited_correct: int = 0  # a hit chunk of the cited source overlaps gold
    cited_correct_source: int = 0  # any chunk of the cited source overlaps gold
    number_warned: bool = False
    verdict: str | None = None
    judge_attempted: bool = False
    context_tokens: int = 0
    llm_calls: int = 0
    groups: list[str] = field(default_factory=list)


def answer_one(setup: Setup, question: dict, generate: Complete, *, expand: bool,
               retrieved: Retrieved | None = None) -> tuple[AnswerRow, list[Source], list[qa_prompt.SourceText]]:
    retrieved = retrieved or retrieve(setup, question)
    row = AnswerRow(question["id"], bool(question["answerable"]), "NO_EVIDENCE", retrieved.gate,
                    groups=_group_names(question))
    if not retrieved.passed:
        return row, [], []
    sources = context_for(setup, retrieved, expand=expand)
    texts = [qa_prompt.SourceText(n=s.n, text=s.text, title=setup.doc_of[s.document_id],
                                  page=s.page) for s in sources]
    bundle = qa_prompt.build_prompt(question=question["question"], sources=texts,
                                    lang=question.get("lang") or "vi", today=EVAL_TODAY)
    raw = generate(bundle.messages)
    row.llm_calls = 1
    row.context_tokens = sum(s.tokens for s in sources)
    final, used = qa_citations.clean_markers(raw, {s.n for s in sources})
    row.answer = final.strip()
    if qa_checks.is_generator_not_found(row.answer):
        row.outcome = "GENERATOR_NOT_FOUND"
        return row, sources, texts
    row.outcome = "ANSWERED"
    cites = qa_citations.build_citations(sources, used)
    gold = [setup.spans[sid] for es in question.get("evidence_sets", []) for sid in es]
    by_n = {s.n: s for s in sources}
    for c in cites:
        hit = [_Range(setup.doc_of[x.document_id], x.char_start, x.char_end)
               for x in by_n[c.n].hit_chunks]
        whole = [_Range(setup.doc_of[x.document_id], x.char_start, x.char_end)
                 for x in by_n[c.n].chunks]
        row.cited += 1
        row.cited_correct += any(_covered(span, hit) > 0 for span in gold)
        row.cited_correct_source += any(_covered(span, whole) > 0 for span in gold)
    held = [qa_prompt.render_source(t) for t in texts] + [question["question"],
                                                          f"Hôm nay là {EVAL_TODAY.isoformat()}"]
    row.number_warned = qa_checks.check_numbers(row.answer, held).warned
    return row, sources, texts


def summarize(rows: Sequence[AnswerRow]) -> dict[str, Any]:
    ans = [r for r in rows if r.answerable]
    una = [r for r in rows if not r.answerable]

    def rate(group: Sequence[AnswerRow], outcome: str) -> float | None:
        return _mean([float(r.outcome == outcome) for r in group])

    # Precision is over answerable questions: an unanswerable question has no gold, so any
    # citation on it would count as wrong; those are reported apart.
    cited = sum(r.cited for r in ans)
    correct = sum(r.cited_correct for r in ans)
    correct_source = sum(r.cited_correct_source for r in ans)
    judged = [r for r in rows if r.verdict is not None]
    flagged = [VERDICT_SCORE[r.verdict] for r in judged if r.number_warned]
    clean = [VERDICT_SCORE[r.verdict] for r in judged if not r.number_warned]
    return {
        "n": len(rows), "n_answerable": len(ans), "n_unanswerable": len(una),
        "answerable": {"answered": rate(ans, "ANSWERED"),
                       "false_refusal_gate": rate(ans, "NO_EVIDENCE"),
                       "false_refusal_generator": rate(ans, "GENERATOR_NOT_FOUND")},
        "unanswerable": {"correct_refusal_gate": rate(una, "NO_EVIDENCE"),
                         "correct_refusal_generator": rate(una, "GENERATOR_NOT_FOUND"),
                         "false_answer": rate(una, "ANSWERED")},
        "citation_precision": round(correct / cited, 4) if cited else None,
        "citation_precision_source": round(correct_source / cited, 4) if cited else None,
        "citations": cited,
        "citations_on_unanswerable": sum(r.cited for r in una),
        "answered_without_citation": _mean(
            [float(r.cited == 0) for r in rows if r.outcome == "ANSWERED"]),
        "faithfulness": _mean([VERDICT_SCORE[r.verdict] for r in judged]),
        "judged": len(judged),
        "judge_unparsed": sum(r.judge_attempted and r.verdict is None for r in rows),
        "faithfulness_number_flagged": _mean(flagged), "n_number_flagged": len(flagged),
        "faithfulness_number_clean": _mean(clean),
        "context_tokens_mean": _mean([float(r.context_tokens) for r in rows if r.llm_calls]),
        "llm_calls": sum(r.llm_calls for r in rows),
    }


def answers_report(setup: Setup, questions: Sequence[dict], generate: Complete, judge: Complete | None,
                   subset: Sequence[str]) -> tuple[dict[str, Any], list[dict]]:
    """Run every question for ``expand`` on and off; judge only the fixed ``subset``."""
    chosen = set(subset)
    retrieved = {q["id"]: retrieve(setup, q) for q in questions}
    out: dict[str, Any] = {"n_questions": len(questions), "judged_subset": sorted(chosen),
                           "by_expand": {}}
    per_question: list[dict] = []
    verdicts: dict[bool, dict[str, str]] = {}
    for expand in (True, False):
        rows = []
        for q in questions:
            row, _sources, texts = answer_one(setup, q, generate, expand=expand,
                                              retrieved=retrieved[q["id"]])
            if judge is not None and q["id"] in chosen and row.outcome == "ANSWERED":
                row.judge_attempted = True
                row.verdict = parse_verdict(judge(judge_messages(q["question"], texts, row.answer)))
            rows.append(row)
            per_question.append({"expand": expand, **row.__dict__})
        entry = {"all": summarize(rows)}
        for name in GROUPS:
            sub = [r for r in rows if name in r.groups]
            if sub:
                entry[name] = summarize(sub)
        out["by_expand"]["on" if expand else "off"] = entry
        verdicts[expand] = {r.id: r.verdict for r in rows if r.verdict is not None}
    # Faithfulness on the questions judged in both modes: on and off may answer different ones.
    common = sorted(set(verdicts[True]) & set(verdicts[False]))
    out["faithfulness_common"] = {
        "n": len(common),
        "on": _mean([VERDICT_SCORE[verdicts[True][i]] for i in common]),
        "off": _mean([VERDICT_SCORE[verdicts[False][i]] for i in common])}
    return out, per_question


# -- CLI ----------------------------------------------------------------------------------------

def _build_setup(args: argparse.Namespace) -> tuple[Setup, list[dict], dict[str, Any]]:
    import yaml
    from sopilot_ai.providers.registry import ModelsConfig

    from .embedders import build_embedder
    from .run import _chunks_for, _git_state, load_questions

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    conf = next(c for c in cfg["configs"] if c["name"] == args.name)
    questions, spans, data_info = load_questions(args.dataset, args.split, args.allow_draft)
    chunks, chunk_info = _chunks_for(args.dataset, cfg.get("chunking", {}), conf["embedder"])
    index = Index(chunks, build_embedder(conf["embedder"], ROOT / ".cache"))
    models = ModelsConfig.load(args.models)
    tok = conf["embedder"].get("tokenizer") or {"model": conf["embedder"]["model"],
                                                 "revision": conf["embedder"].get("revision")}
    from sopilot_ai.docproc.tokens import HFTokenizer

    counter = HFTokenizer(tok["model"], tok.get("revision"), local_files_only=True).count
    setup = Setup(chunks, index, conf, models.retrieval().thresholds, models.context(), counter,
                  spans)
    provenance = {"git": _git_state(), "dataset": str(args.dataset),
                  "dataset_info": data_info, "chunking": chunk_info, "split": args.split,
                  "allow_draft": bool(args.allow_draft),
                  "reviewed": bool(data_info.get("reviewed", False)),
                  "context": {"expand_default": setup.context.expand,
                              "section_max_tokens": setup.context.section_max_tokens,
                              "max_tokens": setup.context.max_tokens},
                  "token_count": "index_text (title path + content), as ai-service stores it"}
    return setup, questions, provenance


def _chain_fn(models_path: Path, task: str) -> Complete:
    from sopilot_ai.providers.llm import build_chain, estimate_tokens
    from sopilot_ai.providers.registry import ModelsConfig

    chain = build_chain(ModelsConfig.load(models_path), task)

    def call(messages: Sequence[dict[str, str]]) -> str:
        tokens = estimate_tokens(" ".join(m["content"] for m in messages))
        return chain.complete(messages, tokens=tokens, temperature=0.0)

    return call


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("coverage", "answers"):
        p = sub.add_parser(name)
        p.add_argument("--dataset", type=Path, required=True)
        p.add_argument("--config", type=Path, required=True, help="retrieval config (eval/configs)")
        p.add_argument("--name", required=True, help="entry of `configs` to use, e.g. hybrid")
        p.add_argument("--split", choices=["dev", "test", "all"], required=True)
        p.add_argument("--models", type=Path,
                       default=ROOT.parent / "services/ai-service/config/models.yaml")
        p.add_argument("--out", type=Path, default=ROOT / "results")
        p.add_argument("--allow-draft", action="store_true")
        if name == "answers":
            p.add_argument("--subset-size", type=int, default=30)
            p.add_argument("--subset-seed", default="v2-10-faithfulness")
            p.add_argument("--judge", choices=["judge", "generate", "none"], default="judge",
                           help="`generate` = the answer model judges itself (stated in the report)")
    a = ap.parse_args()
    setup, questions, provenance = _build_setup(a)
    out = a.out / f"answers-{a.command}-{a.name}-{a.split}"
    out.mkdir(parents=True, exist_ok=True)
    if a.command == "coverage":
        report = coverage_report(setup, questions)
    else:
        answerable_ids = [q["id"] for q in questions if q["answerable"]]
        subset = fixed_subset(answerable_ids, a.subset_size, a.subset_seed)
        judge = None if a.judge == "none" else _chain_fn(a.models, a.judge)
        report, rows = answers_report(setup, questions, _chain_fn(a.models, "generate"), judge,
                                      subset)
        report["judge"] = a.judge
        report["judge_is_the_answer_model"] = a.judge == "generate"
        (out / "per_question.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    report["retrieval_config"] = setup.retrieval
    report["provenance"] = provenance
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    sys.stdout.write(str(out) + "\n")


if __name__ == "__main__":
    main()
