"""V2-19: validate extraction annotations and score adapter output by family/language.

This scores exact normalized structure, not semantic quality. Time and peak RAM
must be measured by the adapter; absent measurements remain null.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .dataset import STATUSES, read_jsonl, relative_file, require


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def ordered_matches(gold: list, predicted: list) -> int:
    """LCS gives order-sensitive exact matching without rewarding duplicates."""
    previous = [0] * (len(predicted) + 1)
    for target in gold:
        current = [0]
        for index, candidate in enumerate(predicted, 1):
            current.append(
                previous[index - 1] + 1
                if target == candidate
                else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1]


def cross_reference_counts(text: str) -> dict:
    value = unicodedata.normalize("NFC", text)
    return {
        "within_document": len(
            re.findall(
                r"\b(?:mục|điều|khoản|section|article)\s+\d+(?:\.\d+)*",
                value,
                re.IGNORECASE,
            )
        ),
        "between_documents": len(
            re.findall(r"\b(?:QT|SOP|HD|BM)[-–]\d+(?:[-–][\w]+)*", value, re.IGNORECASE)
        ),
    }


def validate_extraction(
    root: Path, require_reviewed: bool = False
) -> tuple[list[dict], list[dict]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    require(manifest, "corpus_version", "documents")
    documents = manifest["documents"]
    if not isinstance(documents, list) or not documents:
        raise ValueError("extraction documents must be a nonempty list")
    by_id = {}
    for doc in documents:
        require(doc, "doc_id", "path", "lang", "family", "source", "license", "sha256")
        if doc["doc_id"] in by_id:
            raise ValueError("duplicate extraction doc_id")
        path = relative_file(root, doc["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
            raise ValueError("extraction source hash mismatch")
        by_id[doc["doc_id"]] = doc
    annotations = read_jsonl(root / "annotations.jsonl")
    ids = set()
    for row in annotations:
        require(
            row,
            "doc_id",
            "headings",
            "tables",
            "furniture",
            "metadata",
            "cross_references",
            "review_status",
        )
        if row["doc_id"] not in by_id or row["doc_id"] in ids:
            raise ValueError("unknown or duplicate extraction annotation")
        ids.add(row["doc_id"])
        if row["review_status"] not in STATUSES:
            raise ValueError("invalid extraction review_status")

        def validate_page(
            element: dict, source_path: str = by_id[row["doc_id"]]["path"]
        ) -> None:
            if "page" not in element:
                raise ValueError("element page is required (null for Markdown)")
            page = element["page"]
            if Path(source_path).suffix.lower() == ".md":
                if page is not None:
                    raise ValueError("Markdown has no physical page; use null")
            elif type(page) is not int or page < 1:
                raise ValueError("PDF pages must be positive integers")

        for heading in row["headings"]:
            require(heading, "text", "level")
            validate_page(heading)
            if type(heading["level"]) is not int or not 1 <= heading["level"] <= 6:
                raise ValueError("heading level must be 1..6")
        for table in row["tables"]:
            require(table, "rows", "cols", "column_titles", "cell_spans")
            validate_page(table)
            if (
                type(table["rows"]) is not int
                or type(table["cols"]) is not int
                or min(table["rows"], table["cols"]) <= 0
            ):
                raise ValueError("table dimensions must be positive")
            for cell in table["cell_spans"]:
                require(cell, "row", "col", "rowspan", "colspan")
                if any(
                    type(cell[k]) is not int
                    for k in ("row", "col", "rowspan", "colspan")
                ) or not (
                    0 <= cell["row"] < table["rows"]
                    and 0 <= cell["col"] < table["cols"]
                    and cell["rowspan"] > 0
                    and cell["colspan"] > 0
                    and cell["row"] + cell["rowspan"] <= table["rows"]
                    and cell["col"] + cell["colspan"] <= table["cols"]
                ):
                    raise ValueError("merged-cell span exceeds table bounds")
        if require_reviewed:
            if row.get("annotation_scope", "full_document") != "full_document":
                raise ValueError(
                    "partial extraction labels cannot pass the corpus review gate"
                )
            if row["review_status"] not in {"reviewed", "adjudicated"}:
                raise ValueError("extraction labels require human review")
            require(row, "reviewer_id", "reviewed_at", "label_version")
    if ids != set(by_id):
        raise ValueError("each extraction document needs one annotation")
    return documents, annotations


def _pr_counts(gold: list, predicted: list) -> dict:
    matches = ordered_matches(gold, predicted)
    return {
        "matched": matches,
        "gold": len(gold),
        "predicted": len(predicted),
        "precision": matches / len(predicted) if predicted else None,
        "recall": matches / len(gold) if gold else None,
    }


def score_document(gold: dict, output: dict) -> dict:
    headings = lambda row: [
        (normalized(h["text"]), h["level"], h["page"]) for h in row["headings"]
    ]
    tables = lambda row: [
        (t["page"], t["rows"], t["cols"], tuple(map(normalized, t["column_titles"])))
        for t in row["tables"]
    ]
    spans = lambda row: [
        (n, c["row"], c["col"], c["rowspan"], c["colspan"])
        for n, table in enumerate(row["tables"])
        for c in table.get("cell_spans", [])
    ]
    text = output["canonical_markdown"]
    blocks = [normalized(b["text"]) for b in gold["furniture"] if b["text"].strip()]
    leaked = sum(block in normalized(text) for block in blocks)
    metadata_correct = sum(
        output["metadata"].get(k) == v for k, v in gold["metadata"].items()
    )
    pages = output.get("page_count")
    if pages is not None and (type(pages) is not int or pages <= 0):
        raise ValueError("page_count must be positive or null for unpaged Markdown")
    result = {
        "headings": _pr_counts(headings(gold), headings(output)),
        "tables": _pr_counts(tables(gold), tables(output)),
        "merged_cells": _pr_counts(spans(gold), spans(output)),
        "furniture_leaked": leaked,
        "furniture_gold": len(blocks),
        "metadata_correct": metadata_correct,
        "metadata_gold": len(gold["metadata"]),
        "metadata_accuracy": metadata_correct / len(gold["metadata"])
        if gold["metadata"]
        else None,
        "furniture_leakage_rate": leaked / len(blocks) if blocks else None,
        "replacement_characters": text.count("\ufffd"),
        "cid_artifacts": text.count("(cid:"),
        "cross_references": cross_reference_counts(text),
    }
    for key in ("elapsed_ms", "peak_ram_mb"):
        value = output.get(key)
        if value is not None and (
            type(value) not in (float, int) or not math.isfinite(value) or value < 0
        ):
            raise ValueError(
                "adapter measurements must be finite nonnegative numbers or null"
            )
        result[key] = value
    result["elapsed_ms_per_page"] = (
        output.get("elapsed_ms") / pages
        if output.get("elapsed_ms") is not None and pages
        else None
    )
    # A whole-file high-water RAM measurement cannot be divided into page peaks.
    page_ram = output.get("page_peak_ram_mb")
    if page_ram is not None and (
        not isinstance(page_ram, list)
        or not pages
        or len(page_ram) != pages
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0
            for v in page_ram
        )
    ):
        raise ValueError(
            "page_peak_ram_mb needs one measured nonnegative value per physical page"
        )
    result["page_peak_ram_mb"] = page_ram
    return result


def evaluate(root: Path, predictions: Path) -> dict:
    documents, annotations = validate_extraction(root)
    if any(
        row.get("annotation_scope", "full_document") != "full_document"
        for row in annotations
    ):
        raise ValueError("partial extraction labels cannot be scored as full documents")
    if any(row.get("expected_outcome") == "FAILED" for row in annotations):
        raise ValueError(
            "rejection fixtures need a separate outcome check, not heading/table scores"
        )
    rows = read_jsonl(predictions)
    outputs = {row["doc_id"]: row for row in rows}
    if len(outputs) != len(rows) or set(outputs) != {
        doc["doc_id"] for doc in documents
    }:
        raise ValueError(
            "predictions must contain exactly one output for every manifest document"
        )
    gold_by_id = {row["doc_id"]: row for row in annotations}
    groups: dict[str, list[dict]] = defaultdict(list)
    results = {}
    for doc in documents:
        output = outputs[doc["doc_id"]]
        require(output, "headings", "tables", "metadata", "canonical_markdown")
        score = score_document(gold_by_id[doc["doc_id"]], output)
        results[doc["doc_id"]] = score
        groups[f"family={doc['family']};lang={doc['lang']}"].append(score)
    summary = {}
    for group, scores in groups.items():
        counts = Counter()
        for score in scores:
            for kind in ("headings", "tables", "merged_cells"):
                for key in ("matched", "gold", "predicted"):
                    counts[kind + "_" + key] += score[kind][key]
            for key in (
                "furniture_leaked",
                "furniture_gold",
                "metadata_correct",
                "metadata_gold",
                "replacement_characters",
                "cid_artifacts",
            ):
                counts[key] += score[key]
        summary[group] = {"documents": len(scores), **counts}
        for metric, numerator, denominator in (
            ("metadata_accuracy", "metadata_correct", "metadata_gold"),
            ("furniture_leakage_rate", "furniture_leaked", "furniture_gold"),
        ):
            summary[group][metric] = (
                counts[numerator] / counts[denominator] if counts[denominator] else None
            )
        for kind in ("headings", "tables", "merged_cells"):
            for metric, denom in (("precision", "predicted"), ("recall", "gold")):
                total = counts[kind + "_" + denom]
                summary[group][kind + "_" + metric] = (
                    counts[kind + "_matched"] / total if total else None
                )
    return {
        "kind": "extraction_preflight",
        "by_document": results,
        "by_family_language": summary,
        "limits": "Exact normalized matching; reference regex counts are candidates, not adjudicated labels. "
        "No extractor runs here; adapter supplies time/RAM, null means unmeasured.",
    }


def evaluate_selected_pages(root: Path, predictions: Path) -> dict:
    """Score reviewed labels that cover only some pages, on those pages only.

    The strict ``evaluate`` refuses partial labels because comparing page-limited gold with a
    whole-document prediction would count every unlabelled heading or table as a false
    positive. Here predictions are cut down to ``annotated_pages`` first. Documents without
    reviewed, page-limited labels are listed under ``excluded`` and not scored. Metadata is not
    scored (it belongs to V2-21). A heading or table that continues across a labelled page
    boundary is compared per page, as the labels are.
    """
    documents, annotations = validate_extraction(root)
    gold_by_id = {row["doc_id"]: row for row in annotations}
    scored, excluded = [], {}
    for doc in documents:
        gold = gold_by_id[doc["doc_id"]]
        if gold.get("annotation_scope") != "selected_pages" or not gold.get("annotated_pages"):
            excluded[doc["doc_id"]] = "no page-limited labels"
        elif gold["review_status"] not in {"reviewed", "adjudicated"}:
            excluded[doc["doc_id"]] = "labels not reviewed"
        else:
            scored.append(doc)
    outputs = {row["doc_id"]: row for row in read_jsonl(predictions)}
    missing = {d["doc_id"] for d in scored} - set(outputs)
    if missing:
        raise ValueError(f"predictions missing for: {sorted(missing)}")
    results: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in scored:
        gold = gold_by_id[doc["doc_id"]]
        pages = set(gold["annotated_pages"])
        out = outputs[doc["doc_id"]]
        require(out, "headings", "tables", "page_markdown")
        page_text = out["page_markdown"]
        view = {
            **out,
            "headings": [h for h in out["headings"] if h["page"] in pages],
            "tables": [x for x in out["tables"] if x["page"] in pages],
            "metadata": {},
            "canonical_markdown": "\n\n".join(
                page_text.get(str(p), "") for p in sorted(pages)
            ),
        }
        score = score_document(gold, view)
        for key in ("metadata_correct", "metadata_gold", "metadata_accuracy"):
            score.pop(key)
        # Level-agnostic view: some extractors return reliable text and page but flat levels.
        score["headings_text_only"] = _pr_counts(
            [(normalized(h["text"]), h["page"]) for h in gold["headings"]],
            [(normalized(h["text"]), h["page"]) for h in view["headings"]],
        )
        score["annotated_pages"] = sorted(pages)
        results[doc["doc_id"]] = score
        groups[f"family={doc['family']};lang={doc['lang']}"].append(score)
    summary = {}
    for group, scores in groups.items():
        counts: Counter = Counter()
        for score in scores:
            for kind in ("headings", "headings_text_only", "tables", "merged_cells"):
                for key in ("matched", "gold", "predicted"):
                    counts[f"{kind}_{key}"] += score[kind][key]
            counts["furniture_leaked"] += score["furniture_leaked"]
            counts["furniture_gold"] += score["furniture_gold"]
        row: dict = {"documents": len(scores), **counts}
        for kind in ("headings", "headings_text_only", "tables", "merged_cells"):
            for metric, denom in (("precision", "predicted"), ("recall", "gold")):
                total = counts[f"{kind}_{denom}"]
                row[f"{kind}_{metric}"] = counts[f"{kind}_matched"] / total if total else None
        row["furniture_leakage_rate"] = (
            counts["furniture_leaked"] / counts["furniture_gold"]
            if counts["furniture_gold"]
            else None
        )
        summary[group] = row
    return {
        "kind": "extraction_selected_pages",
        "scored": [d["doc_id"] for d in scored],
        "excluded": excluded,
        "by_document": results,
        "by_family_language": summary,
        "limits": "Only labelled pages are scored; matching is exact on normalized text, level, "
        "page, table size and column titles. Labels are page-limited, so results do not describe "
        "whole documents. Metadata is not scored.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument(
        "--selected-pages",
        action="store_true",
        help="score page-limited reviewed labels on their pages only",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        documents, annotations = validate_extraction(
            args.dataset, args.require_reviewed
        )
        result = (
            (
                evaluate_selected_pages(args.dataset, args.predictions)
                if args.selected_pages
                else evaluate(args.dataset, args.predictions)
            )
            if args.predictions
            else {
                "documents": len(documents),
                "annotations": len(annotations),
                "structurally_valid": True,
                "human_review_checked": args.require_reviewed,
            }
        )
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"extraction invalid: {exc}\n")


if __name__ == "__main__":
    main()
