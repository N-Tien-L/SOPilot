"""V2-06 annotation preflight. Structural validity does not constitute human review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

QUERY_TYPES = {
    "fact",
    "procedure",
    "condition_exception",
    "number_deadline",
    "responsibility",
    "comparison",
    "multi_passage",
}
STATUSES = {"draft", "reviewed", "adjudicated", "excluded"}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{number}: expected an object")
            rows.append(row)
    return rows


def require(row: dict, *keys: str) -> None:
    for key in keys:
        if key not in row or row[key] is None or row[key] == "":
            raise ValueError(
                f"{row.get('id', row.get('span_id', 'record'))}: missing {key}"
            )


def relative_file(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("source path must be an existing file inside the dataset")
    return path


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_documents(root: Path) -> tuple[dict, dict[str, str], dict[str, dict]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    require(manifest, "corpus_version", "normalization_version", "documents")
    if not isinstance(manifest["documents"], list) or not manifest["documents"]:
        raise ValueError("manifest documents must be a nonempty list")
    texts, documents = {}, {}
    for doc in manifest["documents"]:
        require(doc, "doc_id", "path", "lang", "sha256", "source", "license")
        if doc["doc_id"] in documents:
            raise ValueError("duplicate doc_id")
        text = relative_file(root, doc["path"]).read_bytes().decode("utf-8")
        if "\r" in text or unicodedata.normalize("NFC", text) != text:
            raise ValueError("canonical text must use NFC and LF")
        if sha256(text) != doc["sha256"]:
            raise ValueError(f"canonical hash mismatch: {doc['doc_id']}")
        texts[doc["doc_id"]], documents[doc["doc_id"]] = text, doc
    return manifest, texts, documents


def project_expected(question: dict, spans: dict, documents: dict) -> list[dict]:
    """Legacy doc/page proxy only. OR alternatives retain their semantics in evidence_sets."""
    grouped: dict[str, set[int]] = {}
    for evidence_set in question["evidence_sets"]:
        for sid in evidence_set:
            span = spans[sid]
            doc = documents[span["doc_id"]]
            pages = grouped.setdefault(doc["path"].removeprefix("corpus/"), set())
            pages.update(span.get("pages", []))
    return [
        {"doc": doc, **({"pages": sorted(pages)} if pages else {})}
        for doc, pages in sorted(grouped.items())
    ]


def validate_retrieval(root: Path, require_reviewed: bool = False) -> dict:
    manifest, texts, documents = load_documents(root)
    spans = {}
    for span in read_jsonl(root / "evidence.jsonl"):
        require(
            span,
            "span_id",
            "doc_id",
            "section_id",
            "start_char",
            "end_char",
            "quote",
            "quote_sha",
        )
        sid = span["span_id"]
        start, end = span["start_char"], span["end_char"]
        if sid in spans or span["doc_id"] not in texts:
            raise ValueError("duplicate span or unknown document")
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(texts[span["doc_id"]])
        ):
            raise ValueError(f"invalid code-point offsets: {sid}")
        if (
            texts[span["doc_id"]][start:end] != span["quote"]
            or sha256(span["quote"]) != span["quote_sha"]
        ):
            raise ValueError(f"quote/offset/hash mismatch: {sid}")
        spans[sid] = span
    questions = read_jsonl(root / "questions.master.jsonl")
    if not questions:
        raise ValueError("question set must not be empty")
    reviews = (
        read_jsonl(root / "review.jsonl") if (root / "review.jsonl").exists() else []
    )
    ids, split_by_group, span_splits, normalized_splits = set(), {}, {}, {}
    for q in questions:
        require(
            q,
            "id",
            "intent_id",
            "policy_family_id",
            "leakage_group_id",
            "split",
            "question",
            "lang",
            "corpus_lang",
            "cross_lingual",
            "answerable",
            "evidence_sets",
            "query_types",
            "review_status",
            "label_version",
        )
        if (
            q["id"] in ids
            or q["split"] not in {"dev", "test"}
            or q["lang"] not in {"vi", "en"}
        ):
            raise ValueError("duplicate question ID or invalid split/language")
        ids.add(q["id"])
        if not isinstance(q.get("reference_answer"), str):
            raise TypeError("reference_answer must be a string (empty for negatives)")
        if type(q["answerable"]) is not bool or type(q["cross_lingual"]) is not bool:
            raise ValueError("answerable and cross_lingual must be booleans")
        if q["corpus_lang"] not in {"vi", "en"} or q["cross_lingual"] != (
            q["lang"] != q["corpus_lang"]
        ):
            raise ValueError(
                "cross_lingual disagrees with declared query/corpus language"
            )
        if (
            not isinstance(q["query_types"], list)
            or not q["query_types"]
            or set(q["query_types"]) - QUERY_TYPES
        ):
            raise ValueError("query_types must be a nonempty list of supported labels")
        if q["review_status"] not in STATUSES:
            raise ValueError("invalid review_status")
        sets = q["evidence_sets"]
        if not isinstance(sets, list) or any(
            not isinstance(s, list) or not s for s in sets
        ):
            raise ValueError(
                "evidence_sets must contain nonempty AND lists (OR between lists)"
            )
        if q["answerable"] != bool(sets) or (
            q["answerable"] and not q["reference_answer"].strip()
        ):
            raise ValueError(
                "answerable requires evidence and a reference answer; negatives have no gold"
            )
        for group in ("intent_id", "policy_family_id", "leakage_group_id"):
            key = (group, q[group])
            if key in split_by_group and split_by_group[key] != q["split"]:
                raise ValueError(f"dev/test leakage: {group}")
            split_by_group[key] = q["split"]
        normalized = re.sub(
            r"\W+", "", unicodedata.normalize("NFC", q["question"]).casefold()
        )
        if (
            normalized in normalized_splits
            and normalized_splits[normalized] != q["split"]
        ):
            raise ValueError("duplicate question text crosses dev/test")
        normalized_splits[normalized] = q["split"]
        for evidence_set in sets:
            if len(set(evidence_set)) != len(evidence_set):
                raise ValueError("duplicate span inside evidence set")
            for sid in evidence_set:
                if sid not in spans:
                    raise ValueError(f"unknown evidence span: {sid}")
                if sid in span_splits and span_splits[sid] != q["split"]:
                    raise ValueError("same evidence span crosses dev/test")
                span_splits[sid] = q["split"]
        derived = project_expected(q, spans, documents)
        if "expected" in q and q["expected"] != derived:
            raise ValueError(
                "expected must be derived from evidence_sets, not maintained by hand"
            )
        if require_reviewed:
            if q["review_status"] not in {"reviewed", "adjudicated"}:
                raise ValueError(
                    "dataset is draft/excluded: human review is required before freeze"
                )
            approval = next(
                (
                    r
                    for r in reviews
                    if r.get("question_id") == q["id"]
                    and r.get("decision") == q["review_status"]
                    and r.get("label_version") == q["label_version"]
                    and r.get("corpus_version") == manifest["corpus_version"]
                ),
                None,
            )
            if approval is None:
                raise ValueError("missing matching human review record")
            require(approval, "reviewer_id", "reviewed_at", "notes")
            if not q["answerable"]:
                require(approval, "unanswerable_audit")
                require(
                    approval["unanswerable_audit"],
                    "reason",
                    "search_terms",
                    "candidate_sections",
                    "conclusion",
                )
    for left_id, left_split in span_splits.items():
        left = spans[left_id]
        for right_id, right_split in span_splits.items():
            right = spans[right_id]
            if (
                left_split != right_split
                and left["doc_id"] == right["doc_id"]
                and max(left["start_char"], right["start_char"])
                < min(left["end_char"], right["end_char"])
            ):
                raise ValueError("overlapping evidence intervals cross dev/test")
    return {
        "corpus_version": manifest["corpus_version"],
        "documents": len(documents),
        "spans": len(spans),
        "questions": len(questions),
        "human_review_required": not require_reviewed,
        "split_counts": {
            s: sum(q["split"] == s for q in questions) for s in ("dev", "test")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--require-reviewed", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_retrieval(args.dataset, args.require_reviewed)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"dataset invalid: {exc}\n")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
