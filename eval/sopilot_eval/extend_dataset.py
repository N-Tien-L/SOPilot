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

With ``--extra-corpus <dir>`` (V2-45) the dir holds ``manifest.extra.json``, ``page-map.extra.json`` and
``corpus/`` with added canonical documents (``build_canonical.py --only handbook-v3``). They are merged into the
base corpus under the new ``corpus_version``; base reviews are carried with ``rebased_from``; the new drafts are
``subset=v3``; and ``negative-recheck.json`` lists base near-miss negatives whose search terms occur in the
added documents (they may have become answerable and need an adjudication).

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
from datetime import UTC, datetime
from pathlib import Path

from .dataset import (
    FREEZE_KEYS,
    load_documents,
    project_expected,
    read_jsonl,
    sha256,
    validate_retrieval,
)
from .extra_corpus import (
    EXTRA_MANIFEST,
    EXTRA_PAGE_MAP,
    merge_extra_corpus,
    negative_terms,
    rebase_reviews,
    recheck_negatives,
)
from .prepare_main import locate, make_span, write_jsonl

LABEL_VERSION = "main-v2-draft-v1"
LABEL_VERSION_V3 = "main-v3-draft-v1"
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


def build(base: Path, root: Path, force: bool = False, extra: Path | None = None) -> dict:
    # With --extra-corpus the new drafts are ``subset=v3``; the base rows keep their subset (v1/v2).
    subset = "v3" if extra is not None else "v2"
    label_version = LABEL_VERSION_V3 if extra is not None else LABEL_VERSION
    existing = root / "questions.master.jsonl"
    if existing.exists() and not force:
        touched = [q["id"] for q in read_jsonl(existing)
                   if q.get("subset") == subset and q["review_status"] != "draft"]
        if touched:
            raise SystemExit(f"{len(touched)} {subset} questions already reviewed; refusing to rebuild (use --force)")
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
    manifest["purpose"] = (manifest.get("purpose", "") + (
        " | v3: v2 questions + added GitLab Handbook pages and drafts (see README)" if extra is not None else
        " | v2: base questions + realistic, cross-lingual and near-miss negative drafts (see README)")).strip(" |")
    page_map = json.loads((base / "page-map.json").read_text(encoding="utf-8"))
    base_reviews = read_jsonl(base / "review.jsonl")
    base_version = manifest["corpus_version"]
    recheck = None
    if extra is not None:
        extra_manifest = json.loads((extra / EXTRA_MANIFEST).read_text(encoding="utf-8"))
        manifest = merge_extra_corpus(manifest, extra_manifest, extra, root)
        page_map = page_map | json.loads((extra / EXTRA_PAGE_MAP).read_text(encoding="utf-8"))
        (root / "page-map.json").write_text(json.dumps(page_map, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _, texts, documents = load_documents(root)

    spans = read_jsonl(base / "evidence.jsonl")
    questions = [q | {"subset": q.get("subset", "v1"), "tags": sorted(q.get("tags", []))} for q in read_jsonl(base / "questions.master.jsonl")]
    audits = read_jsonl(base / "negative-audit.draft.jsonl")
    reviews = base_reviews
    if extra is not None:
        new_ids = {d["doc_id"] for d in extra_manifest["documents"]}
        recheck = recheck_negatives(negative_terms(questions, base_reviews, audits),
                                    {d: t for d, t in texts.items() if d in new_ids})
        recheck["corpus_version"] = manifest["corpus_version"]
        (root / "negative-recheck.json").write_text(json.dumps(recheck, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
        reviews = rebase_reviews(base_reviews, base_version, manifest["corpus_version"], datetime.now(UTC).date().isoformat())
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
                "label_version": label_version,
                "drafted_by": "Claude",
                "subset": subset,
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
    manifest[f"{subset}_seed"] = {
        "label_version": label_version,
        "files": {p.name: sha256(p.read_text(encoding="utf-8")) for p in sorted((root / "seed").glob("*.json"))},
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(root / "evidence.jsonl", spans)
    write_jsonl(root / "questions.master.jsonl", questions)
    write_jsonl(root / "review.jsonl", reviews)
    write_jsonl(root / "negative-audit.draft.jsonl", audits)
    info = validate_retrieval(root)
    new = [q for q in questions if q["subset"] == subset]
    return {
        **info,
        **({"negative_recheck_hits": len(recheck["with_hits"])} if recheck else {}),
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
    ap.add_argument("--extra-corpus", type=Path, default=None,
                    help="directory with manifest.extra.json, page-map.extra.json and corpus/ of added documents")
    a = ap.parse_args()
    sys.stdout.write(json.dumps(build(a.base, a.dataset, a.force, a.extra_corpus), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
