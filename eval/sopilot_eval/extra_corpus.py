"""Helpers for adding documents to an existing eval dataset (V2-45, ``sop-main-v3``).

Pure functions, no docproc import, so they run in the plain ``eval`` environment:

* :func:`handbook_source_record`: where a handbook page's bytes are and what the manifest says about it
  (used by ``eval/build_canonical.py --only handbook-v3``).
* :func:`merge_extra_corpus`: base manifest + extra manifest -> one manifest with a new ``corpus_version``.
* :func:`rebase_reviews`: carry base reviews to the new ``corpus_version`` (base documents are byte-identical).
* :func:`recheck_negatives`: search every base near-miss negative's terms in the NEW documents only, so a
  question the new pages made answerable is found before it is scored.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .dataset import sha256

EXTRA_MANIFEST = "manifest.extra.json"
EXTRA_PAGE_MAP = "page-map.extra.json"


def handbook_source_record(root: Path, doc_id: str) -> tuple[Path, dict]:
    """Return ``(path to the bytes docproc reads, manifest metadata)`` for one handbook page.

    ``<root>/acquisition/sources.json`` holds ``documents``: ``doc_id``, ``url``, ``commit``, ``license``,
    ``lang`` (``en`` or ``vi``), ``section`` and, for a translated page, ``translated_from``
    (``url``, ``commit``, ``sha256``, ``model``). A Vietnamese page is read from ``acquisition/translated/``,
    an English page from ``acquisition/raw/``; the English original of a translated page is never indexed.
    """
    sources = json.loads((root / "acquisition" / "sources.json").read_text(encoding="utf-8"))
    entry = next((d for d in sources["documents"] if d["doc_id"] == doc_id), None)
    if entry is None:
        raise ValueError(f"{doc_id}: not listed in acquisition/sources.json")
    lang = entry["lang"]
    if lang not in {"en", "vi"}:
        raise ValueError(f"{doc_id}: lang must be en or vi")
    translated = entry.get("translated_from")
    if (lang == "vi") != bool(translated):
        raise ValueError(f"{doc_id}: a vi page needs translated_from and an en page must not have it")
    folder = "translated" if translated else "raw"
    path = root / "acquisition" / folder / f"{doc_id}.md"
    if not path.is_file():
        raise ValueError(f"{doc_id}: missing {path.relative_to(root)}")
    meta = {
        "lang": lang,
        "family": entry.get("section", "gitlab-handbook"),
        "source": entry["url"],
        "license": entry["license"],
        "redistribution": "CC BY-SA 4.0: attribution to GitLab; translations and derived questions share the licence",
        "source_commit": entry.get("commit"),
    }
    if translated:
        meta["translated_from"] = translated
    return path, meta


def merge_extra_corpus(base_manifest: dict, extra_manifest: dict, extra_dir: Path, target: Path) -> dict:
    """Return the merged manifest and copy the extra canonical files into ``target/corpus``.

    Raises when a ``doc_id`` repeats, an extra file is missing or does not match its hash, or the new
    ``corpus_version`` equals the base one (reviews would silently stay attached to a changed corpus).
    """
    if extra_manifest["corpus_version"] == base_manifest["corpus_version"]:
        raise ValueError("extra corpus must carry a new corpus_version")
    known = {d["doc_id"] for d in base_manifest["documents"]}
    (target / "corpus").mkdir(parents=True, exist_ok=True)
    added = []
    for doc in extra_manifest["documents"]:
        if doc["doc_id"] in known:
            raise ValueError(f"{doc['doc_id']}: already in the base corpus")
        known.add(doc["doc_id"])
        src = extra_dir / doc["path"]
        if not src.is_file():
            raise ValueError(f"{doc['doc_id']}: missing canonical file {doc['path']}")
        text = src.read_bytes().decode("utf-8")
        if sha256(text) != doc["sha256"]:
            raise ValueError(f"{doc['doc_id']}: canonical hash mismatch")
        dest = target / doc["path"]
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        added.append(doc)
    merged = dict(base_manifest)
    merged["documents"] = [*base_manifest["documents"], *added]
    merged["corpus_version"] = extra_manifest["corpus_version"]
    merged["extra_corpus"] = {
        "added_documents": len(added),
        "base_corpus_version": base_manifest["corpus_version"],
        "normalization_version": extra_manifest.get("normalization_version"),
        "docproc": extra_manifest.get("docproc"),
        "models": extra_manifest.get("models"),
    }
    return merged


def rebase_reviews(reviews: list[dict], old_version: str, new_version: str, date: str,
                   excluded: set[str] | None = None) -> list[dict]:
    """Carry reviews of ``old_version`` to ``new_version``; question ids in ``excluded`` are not carried."""
    skip = excluded or set()
    out = []
    for row in reviews:
        if row.get("question_id") in skip:
            continue
        if row.get("corpus_version") != old_version:
            out.append(row)
            continue
        carried = {k: v for k, v in row.items() if k != "rebased_from"}
        if "rebased_from" in row:
            carried["rebased_from_prev"] = row["rebased_from"]
        carried["corpus_version"] = new_version
        carried["rebased_from"] = {
            "corpus_version": old_version,
            "date": date,
            "reason": "documents were added; every base document is byte-identical, so evidence quotes, "
                      "questions and answers are unchanged",
        }
        out.append(carried)
    return out


def negative_terms(questions: list[dict], reviews: list[dict], audits: list[dict]) -> dict[str, list[str]]:
    """Search terms per unanswerable question id, from ``review.jsonl`` audits and the audit file."""
    by_intent = {a["intent_id"]: a.get("search_terms", []) for a in audits}
    by_question = {r["question_id"]: r["unanswerable_audit"].get("search_terms", [])
                   for r in reviews if r.get("unanswerable_audit")}
    out = {}
    for q in questions:
        if not q["answerable"]:
            out[q["id"]] = list(by_question.get(q["id"]) or by_intent.get(q["intent_id"]) or [])
    return out


def recheck_negatives(terms_by_question: dict[str, list[str]], new_texts: dict[str, str]) -> dict:
    """Count each question's terms in the new documents only; ``with_hits`` needs an adjudication."""
    with_hits, no_terms = [], []
    for qid, terms in sorted(terms_by_question.items()):
        if not terms:
            no_terms.append(qid)
            continue
        hits = {doc: {t: n for t in terms if (n := text.casefold().count(t.casefold()))}
                for doc, text in new_texts.items()}
        hits = {d: h for d, h in hits.items() if h}
        if hits:
            with_hits.append({"question_id": qid, "terms": terms, "hits": hits})
    return {"checked": len(terms_by_question), "with_hits": with_hits, "without_search_terms": no_terms}
