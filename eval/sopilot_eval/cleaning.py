"""V2-21: does cleaning remove the frame and keep the body? Measured on V2-19 labels.

Input: two prediction files written by ``predict_extraction.py --clean`` from one extraction,
``predictions.raw.jsonl`` (render without cleaning) and ``predictions.clean.jsonl`` (render after
``clean_document``, with the removed ``boilerplate`` blocks). Both carry ``page_markdown`` per
physical page and the full ``canonical_markdown``.

Matching (``present``): the label text, after ``flat`` (NFC, casefold, whitespace collapsed,
Markdown table pipes, heading marks and table separator lines removed), occurs in the flattened
output text with no letter or digit directly before or after it. For a PDF the output text is
the page the label names (``page_markdown``); for Markdown (page null) it is the whole file.

Metrics:

* ``furniture_leakage_rate`` = gold furniture blocks present in the cleaned page text / all gold
  furniture blocks. ``furniture_present_raw`` is the same count before cleaning (the baseline)
  and ``furniture_removal_rate`` = blocks present before and absent after / blocks present
  before. ``furniture_leaked_whole_doc`` is the existing whole-document exact check of
  ``extraction.score_document`` on the cleaned Markdown, for comparison.
* ``content_deletion_rate`` (wrongly removed body) = gold content units present in the page
  text before cleaning and absent after / gold content units present before. A content unit is
  a gold heading (``text``, ``page``) or a non-empty gold table column title (``page`` of the
  table fragment). Units not found before cleaning are extraction misses, not cleaning
  deletions, and are left out of the denominator (``content_units_missing_raw``).
* Removal audit: every removed ``boilerplate`` block is ``confirmed`` when it and a gold
  furniture block of the same page contain one another (flattened, boundary-aware), otherwise
  ``unconfirmed``. Unconfirmed blocks are listed for review; they may be frame the labels do
  not list, or body text the gold units do not cover (paragraphs have no gold label).

Limits: substring matching cannot tell two occurrences apart, so a heading repeated in a table
of contents on the same page hides its own deletion; very short labels (``2/9``) can match an
unrelated string on the same page; paragraphs are not labelled, so only headings and column
titles measure wrong deletion directly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .dataset import read_jsonl
from .extraction import score_document, validate_extraction

_SEPARATOR_LINE = re.compile(r"^[\s|:\-]+$")
_HEADING_MARK = re.compile(r"^\s*#{1,6}\s+")
_SNIPPET = 80


def flat(text: str) -> str:
    lines = []
    for line in unicodedata.normalize("NFC", text).splitlines():
        if line.strip() and _SEPARATOR_LINE.match(line) and "-" in line:
            continue
        line = _HEADING_MARK.sub("", line)
        lines.append(line.replace("\\|", " ").replace("|", " "))
    return " ".join(" ".join(lines).casefold().split())


def contains(haystack: str, needle: str) -> bool:
    """``needle`` occurs in ``haystack`` (both already ``flat``), not inside a longer word."""
    if not needle:
        return False
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def page_text(prediction: dict, page: int | None) -> str:
    pages = prediction.get("page_markdown") or {}
    if page is None or not pages:
        return prediction.get("canonical_markdown", "")
    return pages.get(str(page), "")


def snippet(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= _SNIPPET else one_line[: _SNIPPET - 1] + "…"


def content_units(gold: dict) -> list[dict]:
    units = [{"type": "heading", "page": h["page"], "text": h["text"]} for h in gold["headings"]]
    for table in gold["tables"]:
        units += [{"type": "column_title", "page": table["page"], "text": title}
                  for title in table["column_titles"] if title.strip()]
    return units


def score_cleaning(gold: dict, raw: dict, clean: dict) -> dict:
    """Per-document counts and the concrete cases behind them (see module docstring)."""
    flat_raw: dict = {}
    flat_clean: dict = {}

    def text(prediction: dict, cache: dict, page: int | None) -> str:
        if page not in cache:
            cache[page] = flat(page_text(prediction, page))
        return cache[page]

    furniture = [f for f in gold["furniture"] if f["text"].strip()]
    present_raw, removed, leaked = 0, 0, []
    for block in furniture:
        needle = flat(block["text"])
        before = contains(text(raw, flat_raw, block["page"]), needle)
        after = contains(text(clean, flat_clean, block["page"]), needle)
        present_raw += before
        removed += before and not after
        if after:
            leaked.append({"page": block["page"], "text": snippet(block["text"])})
    deleted, missing, present_units = [], 0, 0
    for unit in content_units(gold):
        needle = flat(unit["text"])
        if not contains(text(raw, flat_raw, unit["page"]), needle):
            missing += 1
            continue
        present_units += 1
        if not contains(text(clean, flat_clean, unit["page"]), needle):
            deleted.append({**unit, "text": snippet(unit["text"])})
    confirmed, unconfirmed = 0, []
    for block in clean.get("boilerplate", []):
        body = flat(block["text"])
        same_page = [flat(f["text"]) for f in furniture
                     if block.get("page") is None or f["page"] == block.get("page")]
        if any(contains(body, f) or contains(f, body) for f in same_page if f):
            confirmed += 1
        else:
            unconfirmed.append({"kind": block["kind"], "page": block.get("page"),
                                "chars": len(block["text"]), "text": snippet(block["text"])})
    whole = score_document(gold, {**clean, "metadata": {}})
    return {
        "furniture_gold": len(furniture),
        "furniture_present_raw": present_raw,
        "furniture_leaked": len(leaked),
        "furniture_removed": removed,
        "furniture_leaked_whole_doc": whole["furniture_leaked"],
        "content_units_gold": present_units + missing,
        "content_units_missing_raw": missing,
        "content_units_present_raw": present_units,
        "content_deleted": len(deleted),
        "removed_blocks": confirmed + len(unconfirmed),
        "removed_blocks_confirmed": confirmed,
        "removed_blocks_unconfirmed": len(unconfirmed),
        "removed_chars_unconfirmed": sum(b["chars"] for b in unconfirmed),
        "leaked_cases": leaked,
        "deleted_cases": deleted,
        "unconfirmed_removals": unconfirmed,
    }


_SUMMED = (
    "furniture_gold", "furniture_present_raw", "furniture_leaked", "furniture_removed",
    "furniture_leaked_whole_doc", "content_units_gold", "content_units_missing_raw",
    "content_units_present_raw", "content_deleted", "removed_blocks", "removed_blocks_confirmed",
    "removed_blocks_unconfirmed", "removed_chars_unconfirmed",
)


def _rates(counts: Counter) -> dict:
    def ratio(numerator: str, denominator: str) -> float | None:
        return counts[numerator] / counts[denominator] if counts[denominator] else None

    return {
        "furniture_leakage_rate": ratio("furniture_leaked", "furniture_gold"),
        "furniture_leakage_rate_raw": ratio("furniture_present_raw", "furniture_gold"),
        "furniture_removal_rate": ratio("furniture_removed", "furniture_present_raw"),
        "furniture_leakage_rate_whole_doc": ratio("furniture_leaked_whole_doc",
                                                  "furniture_gold"),
        "content_deletion_rate": ratio("content_deleted", "content_units_present_raw"),
        "removed_blocks_unconfirmed_rate": ratio("removed_blocks_unconfirmed",
                                                 "removed_blocks"),
    }


def evaluate_cleaning(root: Path, raw_path: Path, clean_path: Path) -> dict:
    documents, annotations = validate_extraction(root)
    gold_by_id = {row["doc_id"]: row for row in annotations}
    raw = {row["doc_id"]: row for row in read_jsonl(raw_path)}
    clean = {row["doc_id"]: row for row in read_jsonl(clean_path)}
    if set(raw) != set(clean):
        raise ValueError("raw and clean predictions must cover the same documents")
    results, excluded = {}, {}
    groups: dict[str, Counter] = defaultdict(Counter)
    docs_in_group: Counter = Counter()
    cases: dict[str, list] = {"leaked": [], "deleted": [], "unconfirmed_removals": []}
    total: Counter = Counter()
    for doc in documents:
        doc_id = doc["doc_id"]
        gold = gold_by_id[doc_id]
        if gold.get("expected_outcome") == "FAILED":
            excluded[doc_id] = "rejection fixture"
            continue
        if doc_id not in raw:
            excluded[doc_id] = "no prediction"
            continue
        score = score_cleaning(gold, raw[doc_id], clean[doc_id])
        results[doc_id] = {k: score[k] for k in _SUMMED}
        group = f"family={doc['family']};lang={doc['lang']}"
        docs_in_group[group] += 1
        for key in _SUMMED:
            groups[group][key] += score[key]
            total[key] += score[key]
        for name, key in (("leaked", "leaked_cases"), ("deleted", "deleted_cases"),
                          ("unconfirmed_removals", "unconfirmed_removals")):
            cases[name] += [{"doc_id": doc_id, **case} for case in score[key]]
    by_group = {g: {"documents": docs_in_group[g], **dict(c), **_rates(c)}
                for g, c in sorted(groups.items())}
    for lang in sorted({d["lang"] for d in documents}):
        counts = Counter()
        for group, group_counts in groups.items():
            if group.endswith(f";lang={lang}"):
                counts.update(group_counts)
        by_group[f"lang={lang}"] = {**dict(counts), **_rates(counts)}
    return {
        "kind": "cleaning_v2_21",
        "scored": sorted(results),
        "excluded": excluded,
        "overall": {"documents": len(results), **dict(total), **_rates(total)},
        "by_family_language": by_group,
        "by_document": results,
        "cases": cases,
        "definitions": (__doc__ or "").strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V2-21 cleaning leakage / wrong-deletion")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        payload = json.dumps(evaluate_cleaning(args.dataset, args.raw, args.clean),
                             ensure_ascii=False, indent=2) + "\n"
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"cleaning score invalid: {exc}\n")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


if __name__ == "__main__":
    main()
