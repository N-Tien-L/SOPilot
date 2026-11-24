"""V2-06: assemble the main retrieval dataset (dev = reviewed pilot, test = new drafts).

    python -m sopilot_eval.prepare_main --dataset datasets/sop-main --pilot datasets/sop-pilot

Inputs in ``<dataset>``: ``manifest.json``, ``page-map.json`` and ``corpus/`` from
``eval/build_canonical.py`` (docproc), and ``test.seed.json`` with the drafted intents. Each
intent gives its questions, the evidence as quotes copied from the canonical text, and labels; the
builder finds every quote's code-point offsets (exact first, then whitespace-flexible) and writes
``evidence.jsonl``, ``questions.master.jsonl``, ``review.jsonl``, ``negative-audit.draft.jsonl``
and ``rebase-report.json``.

Pilot (dev) rebase: each pilot span is located in the docproc canonical text. A question keeps its
owner review only if every span quote is byte-identical in the new text and the question is
answerable; the review record then gets the new ``corpus_version`` plus ``carried_from``. Negatives
always return to ``draft`` because the corpus grew and the unanswerable audit must be redone.

The builder refuses to overwrite an existing ``questions.master.jsonl`` (the review app edits it)
unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .dataset import load_documents, project_expected, read_jsonl, sha256

LABEL_VERSION = "main-draft-v1"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_bytes("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8"))


def locate(text: str, quote: str, occurrence: int = 0, after: str | None = None) -> tuple[int, int]:
    """Offsets of ``quote`` in ``text``. ``after`` anchors the search after a context string."""
    base = text.find(after) if after else 0
    if base < 0:
        raise ValueError(f"anchor not found: {after!r}")
    hits = [m.start() for m in re.finditer(re.escape(quote), text[base:])]
    if hits:
        if occurrence >= len(hits):
            raise ValueError(f"occurrence {occurrence} of {quote!r} not found")
        if len(hits) > 1 and occurrence == 0 and after is None:
            raise ValueError(f"ambiguous quote ({len(hits)} hits), give occurrence/after: {quote!r}")
        start = base + hits[occurrence]
        return start, start + len(quote)
    pattern = r"\s+".join(re.escape(tok) for tok in quote.split())
    flex = list(re.finditer(pattern, text[base:]))
    if not flex:
        raise ValueError(f"quote not found: {quote!r}")
    m = flex[occurrence]
    return base + m.start(), base + m.end()


def pages_for(page_map: list[dict] | None, start: int, end: int) -> list[int] | None:
    if not page_map:
        return None
    return [p["page"] for p in page_map if p["end_char"] > start and p["start_char"] < end]


def make_span(span_id: str, doc_id: str, section: str, text: str, start: int, end: int, pmap) -> dict:
    quote = text[start:end]
    row = {
        "span_id": span_id,
        "doc_id": doc_id,
        "section_id": section,
        "start_char": start,
        "end_char": end,
        "quote": quote,
        "quote_sha": sha256(quote),
    }
    pages = pages_for(pmap, start, end)
    if pages:
        row["pages"] = pages
    return row


def rebase_pilot(pilot: Path, texts: dict, page_map: dict):
    spans, report = [], []
    old_spans = read_jsonl(pilot / "evidence.jsonl")
    for s in old_spans:
        text = texts[s["doc_id"]]
        status = "exact"
        try:
            start, end = locate(text, s["quote"])
        except ValueError:
            try:
                start, end = _loose(text, s["quote"])
                status = "changed"
            except ValueError:
                report.append({"span_id": s["span_id"], "status": "missing", "old_quote": s["quote"]})
                continue
        row = make_span(s["span_id"], s["doc_id"], s["section_id"], text, start, end, page_map.get(s["doc_id"]))
        if row["quote"] != s["quote"]:
            status = "changed"
        report.append({"span_id": s["span_id"], "status": status, "old_quote": s["quote"], "new_quote": row["quote"]})
        spans.append(row)
    return spans, {r["span_id"]: r["status"] for r in report}, report


def _strip_markdown(quote: str) -> str:
    """Drop the Markdown syntax docproc does not render: emphasis, link targets, list numbers."""
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", quote)
    value = re.sub(r"(\*\*|__|`)", "", value)
    return re.sub(r"(?m)^\s*(?:\d+\.|[-*+])\s+", "", value).strip()


def _loose(text: str, quote: str) -> tuple[int, int]:
    """Whitespace- and markup-tolerant match for rebasing pypdf/Markdown quotes onto docproc text.

    The match starts at the first word of the stripped quote, so a list number that docproc
    renumbered (``1.`` -> ``4.``) is not part of the new span.
    """
    tokens = [re.escape(t) for t in re.findall(r"\w+|[^\w\s]", _strip_markdown(quote))]
    m = re.search(r"[\s|*_\-#>]*".join(tokens), text)
    if not m:
        raise ValueError("not found")
    return m.start(), m.end()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    root: Path = args.dataset
    if (root / "questions.master.jsonl").exists() and not args.force:
        raise SystemExit("questions.master.jsonl exists (may hold review edits); use --force to rebuild")
    manifest, texts, documents = load_documents(root)
    page_map = json.loads((root / "page-map.json").read_text(encoding="utf-8"))
    corpus_version = manifest["corpus_version"]

    spans, span_status, report = rebase_pilot(args.pilot, texts, page_map)
    pilot_reviews = {r["question_id"]: r for r in read_jsonl(args.pilot / "review.jsonl")}
    pilot_manifest = json.loads((args.pilot / "manifest.json").read_text(encoding="utf-8"))
    questions, reviews, carried, reset = [], [], [], []
    for q in read_jsonl(args.pilot / "questions.master.jsonl"):
        q = {k: v for k, v in q.items() if k != "expected"}
        ids = [sid for es in q["evidence_sets"] for sid in es]
        keep = (
            q["answerable"]
            and q["review_status"] == "reviewed"
            and q["id"] in pilot_reviews
            and all(span_status.get(sid) == "exact" for sid in ids)
        )
        if keep:
            rv = dict(pilot_reviews[q["id"]])
            rv["carried_from"] = {
                "corpus_version": rv["corpus_version"],
                "reviewed_at": rv["reviewed_at"],
                "reason": "every evidence quote is byte-identical in the docproc canonical text",
            }
            rv["corpus_version"] = corpus_version
            reviews.append(rv)
            carried.append(q["id"])
        else:
            q["review_status"] = "draft"
            q["label_version"] = LABEL_VERSION
            q["rebase_note"] = (
                "negative: corpus grew from 4 to 23 documents, redo the unanswerable audit"
                if not q["answerable"]
                else "evidence quote changed or moved during docproc rebase; re-check spans"
            )
            reset.append(q["id"])
        questions.append(q)

    seed = json.loads((root / "test.seed.json").read_text(encoding="utf-8"))
    audits = []
    for intent in seed["intents"]:
        sets = []
        for k_set, evidence_set in enumerate(intent.get("evidence", [])):
            ids = []
            for k, ev in enumerate(evidence_set):
                text = texts[ev["doc"]]
                start, end = locate(text, ev["quote"], ev.get("occurrence", 0), ev.get("after"))
                sid = f"{intent['id']}-s{k_set + 1}{chr(97 + k)}"
                spans.append(make_span(sid, ev["doc"], ev.get("section", "manual"), text, start, end,
                                       page_map.get(ev["doc"])))
                ids.append(sid)
            sets.append(ids)
        for item in intent["questions"]:
            corpus_lang = intent["corpus_lang"]
            questions.append(
                {
                    "id": f"{intent['id']}-{item['lang']}",
                    "intent_id": intent["id"],
                    "policy_family_id": intent["family"],
                    "leakage_group_id": intent["family"],
                    "split": "test",
                    "question": item["question"],
                    "lang": item["lang"],
                    "corpus_lang": corpus_lang,
                    "cross_lingual": item["lang"] != corpus_lang,
                    "answerable": bool(sets),
                    "evidence_sets": sets,
                    "reference_answer": item.get("answer", "") if sets else "",
                    "query_types": intent["query_types"],
                    "review_status": "draft",
                    "label_version": LABEL_VERSION,
                    "drafted_by": "Claude",
                }
            )
        if not sets:
            terms = intent["search_terms"]
            audits.append(
                {
                    "intent_id": intent["id"],
                    "drafted_by": "Claude",
                    "human_review_status": "pending",
                    "reason": intent["negative_reason"],
                    "search_terms": terms,
                    "scope_documents": sorted(texts),
                    "candidate_sections": {
                        d: {t: n for t in terms if (n := t_.casefold().count(t.casefold()))}
                        for d, t_ in texts.items()
                    },
                    "conclusion": "draft_unanswerable_in_main_corpus",
                    "corpus_version": corpus_version,
                }
            )
    # pilot negatives keep their old audit text for reference, recomputed on the new corpus
    for a in read_jsonl(args.pilot / "negative-audit.draft.jsonl"):
        audits.append(
            a
            | {
                "scope_documents": sorted(texts),
                "candidate_sections": {
                    d: {t: n for t in a["search_terms"] if (n := t_.casefold().count(t.casefold()))}
                    for d, t_ in texts.items()
                },
                "corpus_version": corpus_version,
                "human_review_status": "pending",
            }
        )
    spans_by_id = {s["span_id"]: s for s in spans}
    if len(spans_by_id) != len(spans):
        raise ValueError("duplicate span ids")
    for q in questions:
        q["expected"] = project_expected(q, spans_by_id, documents)
    write_jsonl(root / "evidence.jsonl", spans)
    write_jsonl(root / "questions.master.jsonl", questions)
    write_jsonl(root / "review.jsonl", reviews)
    write_jsonl(root / "negative-audit.draft.jsonl", audits)
    (root / "rebase-report.json").write_text(
        json.dumps(
            {
                "from_corpus_version": pilot_manifest["corpus_version"],
                "to_corpus_version": corpus_version,
                "spans": report,
                "reviews_carried": carried,
                "reset_to_draft": reset,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    counts = {
        "questions": len(questions),
        "dev": sum(q["split"] == "dev" for q in questions),
        "test": sum(q["split"] == "test" for q in questions),
        "spans": len(spans),
        "reviews_carried": len(carried),
        "reset_to_draft": len(reset),
    }
    sys.stdout.write(json.dumps(counts) + "\n")


if __name__ == "__main__":
    main()
