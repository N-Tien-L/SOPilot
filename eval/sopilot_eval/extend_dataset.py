"""Build ``sop-main-v2``: the frozen ``sop-main`` questions plus new draft intents from seed files.

    python -m sopilot_eval.extend_dataset --base datasets/sop-main --dataset datasets/sop-main-v2

Why a second dataset instead of editing ``sop-main``: the frozen test split stays byte-identical, so
every V2-07 result on ``test_sha256`` stays reproducible, and the new questions can be reviewed and
frozen on their own schedule.

Inputs:

* ``<base>``: a valid V2-06 dataset (corpus, manifest, page-map, questions, evidence, review).
* ``<dataset>/seed/*.json``: lists of intents. Each intent has ``id``, ``split`` (dev|test),
  ``family``, ``corpus_lang``, ``query_types``, ``tags``, ``questions`` (lang, question, answer)
  and either ``evidence`` (OR list of AND lists of ``{doc, quote, occurrence?, after?}``) or, for a
  negative, ``negative_reason`` + ``search_terms``.

Output in ``<dataset>``: corpus, manifest and page-map copied from the base (same
``corpus_version``, so base reviews stay valid), ``questions.master.jsonl`` / ``evidence.jsonl`` /
``review.jsonl`` / ``negative-audit.draft.jsonl`` = base rows + new drafts. Every question gets a
``subset`` (``v1`` for base rows, ``v2`` for new ones) and ``tags``. The manifest is unfrozen and
records the base freeze under ``derived_from``. New questions are ``draft`` with
``drafted_by=Claude``: the owner must review them before the dataset can be frozen.

Refuses to run when ``<dataset>`` already holds a reviewed v2 question (the review app edits the
files in place), unless ``--force``.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from .dataset import (
    FREEZE_KEYS,
    load_documents,
    project_expected,
    read_jsonl,
    sha256,
    validate_retrieval,
)
from .prepare_main import locate, make_span, write_jsonl

LABEL_VERSION = "main-v2-draft-v1"
DOC_CODE = re.compile(r"\b(?:QT[-.]?\d+|QĐ|SOP\s*\d+|\d+/(?:QĐ|NĐ|TB|VBHN)\b|BDP|EPA|FDA|ORA|NCI)", re.IGNORECASE)


def _seed_intents(seed_dir: Path) -> list[dict]:
    intents: list[dict] = []
    for path in sorted(seed_dir.glob("*.json")):
        part = json.loads(path.read_text(encoding="utf-8"))
        for it in part:
            it["_seed_file"] = path.name
        intents.extend(part)
    ids = [it["id"] for it in intents]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate intent id in seed files")
    return intents


def lexical_overlap(question: str, quotes: list[str]) -> float:
    """Share of the question's content words (>= 3 letters, diacritics folded) found in its gold quotes."""
    def words(text: str) -> set[str]:
        folded = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
        folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
        return {w for w in re.findall(r"\w+", folded) if len(w) >= 3}

    q = words(question)
    gold = words(" ".join(quotes))
    return round(len(q & gold) / len(q), 3) if q else 0.0


def build(base: Path, root: Path, force: bool = False) -> dict:
    existing = root / "questions.master.jsonl"
    if existing.exists() and not force:
        touched = [q["id"] for q in read_jsonl(existing)
                   if q.get("subset") == "v2" and q["review_status"] != "draft"]
        if touched:
            raise SystemExit(f"{len(touched)} v2 questions already reviewed; refusing to rebuild (use --force)")
    validate_retrieval(base)
    for name in ("manifest.json", "page-map.json", "selection.json", "SOURCES.md"):
        if (base / name).exists():
            shutil.copyfile(base / name, root / name)
    if (root / "corpus").exists():
        for f in (base / "corpus").iterdir():
            shutil.copyfile(f, root / "corpus" / f.name)
    else:
        shutil.copytree(base / "corpus", root / "corpus")

    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    derived = {"dataset": base.name, **{k: manifest.get(k) for k in FREEZE_KEYS if k in manifest}}
    for k in (*FREEZE_KEYS, "frozen"):
        manifest.pop(k, None)
    manifest["frozen"] = False
    manifest["derived_from"] = derived
    manifest["purpose"] = (manifest.get("purpose", "") + " | v2: base questions + realistic, cross-lingual "
                           "and near-miss negative drafts (see README)").strip(" |")
    _, texts, documents = load_documents(base)
    page_map = json.loads((base / "page-map.json").read_text(encoding="utf-8"))

    spans = read_jsonl(base / "evidence.jsonl")
    questions = [q | {"subset": "v1", "tags": sorted(q.get("tags", []))} for q in read_jsonl(base / "questions.master.jsonl")]
    reviews = read_jsonl(base / "review.jsonl")
    audits = read_jsonl(base / "negative-audit.draft.jsonl")
    seed = _seed_intents(root / "seed")
    for it in seed:
        sets = []
        quotes = []
        for k_set, evidence_set in enumerate(it.get("evidence", [])):
            ids = []
            for k, ev in enumerate(evidence_set):
                start, end = locate(texts[ev["doc"]], ev["quote"], ev.get("occurrence", 0), ev.get("after"))
                sid = f"{it['id']}-s{k_set + 1}{chr(97 + k)}"
                spans.append(make_span(sid, ev["doc"], ev.get("section", "manual"), texts[ev["doc"]], start, end,
                                       page_map.get(ev["doc"])))
                quotes.append(spans[-1]["quote"])
                ids.append(sid)
            sets.append(ids)
        if bool(sets) == ("negative_reason" in it):
            raise ValueError(f"{it['id']}: give evidence or negative_reason, not both or neither")
        for item in it["questions"]:
            tags = set(it.get("tags", []))
            if DOC_CODE.search(item["question"]):
                tags.add("names_doc_code")
            if sets and item["lang"] != it["corpus_lang"]:
                tags.add("cross_lingual")
            questions.append({
                "id": f"{it['id']}-{item['lang']}",
                "intent_id": it["id"],
                "policy_family_id": it["family"],
                "leakage_group_id": it["family"],
                "split": it["split"],
                "question": item["question"],
                "lang": item["lang"],
                "corpus_lang": it["corpus_lang"],
                "cross_lingual": item["lang"] != it["corpus_lang"],
                "answerable": bool(sets),
                "evidence_sets": sets,
                "reference_answer": item.get("answer", "") if sets else "",
                "query_types": it["query_types"],
                "review_status": "draft",
                "label_version": LABEL_VERSION,
                "drafted_by": "Claude",
                "subset": "v2",
                "tags": sorted(tags),
                **({"lexical_overlap": lexical_overlap(item["question"], quotes)} if sets else {}),
            })
        if not sets:
            terms = it["search_terms"]
            audits.append({
                "intent_id": it["id"],
                "drafted_by": "Claude",
                "human_review_status": "pending",
                "reason": it["negative_reason"],
                "search_terms": terms,
                "scope_documents": sorted(texts),
                "candidate_sections": {d: {t: n for t in terms if (n := tx.casefold().count(t.casefold()))}
                                       for d, tx in texts.items()},
                "conclusion": "draft_unanswerable_in_main_corpus",
                "corpus_version": manifest["corpus_version"],
            })
    by_id = {s["span_id"]: s for s in spans}
    if len(by_id) != len(spans):
        raise ValueError("duplicate span ids")
    for q in questions:
        q["expected"] = project_expected(q, by_id, documents)
    manifest["v2_seed"] = {
        "label_version": LABEL_VERSION,
        "files": {p.name: sha256(p.read_text(encoding="utf-8")) for p in sorted((root / "seed").glob("*.json"))},
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(root / "evidence.jsonl", spans)
    write_jsonl(root / "questions.master.jsonl", questions)
    write_jsonl(root / "review.jsonl", reviews)
    write_jsonl(root / "negative-audit.draft.jsonl", audits)
    info = validate_retrieval(root)
    new = [q for q in questions if q["subset"] == "v2"]
    return {
        **info,
        "new_questions": len(new),
        "new_intents": len(seed),
        "new_by_split": {s: {"answerable": sum(q["answerable"] for q in new if q["split"] == s),
                             "unanswerable": sum(not q["answerable"] for q in new if q["split"] == s),
                             "cross_lingual": sum(q["cross_lingual"] and q["answerable"] for q in new if q["split"] == s)}
                         for s in ("dev", "test")},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sys.stdout.write(json.dumps(build(a.base, a.dataset, a.force), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
