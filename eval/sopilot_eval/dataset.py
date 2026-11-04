"""V2-06 annotation preflight. Structural validity does not constitute human review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
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


FREEZE_KEYS = (
    "frozen_at",
    "frozen_by",
    "test_sha256",
    "frozen_corpus_version",
    "frozen_docproc_commit",
)


def fingerprint_test_split(questions: list[dict], spans: dict) -> str:
    """Stable SHA-256 of the test split: question text, answer, evidence and the spans they cite.

    Covers ``id``, ``question``, ``reference_answer`` and ``evidence_sets`` of every ``split=test``
    question (sorted by id), plus ``span_id``, ``doc_id``, offsets, ``quote`` and ``quote_sha`` of
    every span those questions cite. Review metadata and ``expected`` are excluded on purpose.
    """
    test = sorted((q for q in questions if q["split"] == "test"), key=lambda q: q["id"])
    cited = sorted({sid for q in test for es in q["evidence_sets"] for sid in es})
    payload = {
        "questions": [
            {k: q[k] for k in ("id", "question", "reference_answer", "evidence_sets")}
            for q in test
        ],
        "spans": [
            {
                k: spans[sid][k]
                for k in ("span_id", "doc_id", "start_char", "end_char", "quote", "quote_sha")
            }
            for sid in cited
        ],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(blob)


def check_frozen(
    manifest: dict, questions: list[dict], spans: dict, reviews: list[dict]
) -> None:
    """Enforce a frozen test split. Unfreezing is a manual manifest edit, never automatic."""
    if manifest.get("frozen") is not True:
        return
    require(manifest, *FREEZE_KEYS)
    if manifest["frozen_corpus_version"] != manifest["corpus_version"]:
        raise ValueError("frozen test split: corpus_version changed since freeze")
    if manifest.get("docproc", {}).get("commit") != manifest["frozen_docproc_commit"]:
        raise ValueError("frozen test split: canonical rebuilt from another docproc commit")
    for q in questions:
        if q["split"] != "test":
            continue
        if q["review_status"] not in {"reviewed", "adjudicated"}:
            raise ValueError(f"frozen test split: question not reviewed: {q['id']}")
        if not any(
            r.get("question_id") == q["id"]
            and r.get("decision") == q["review_status"]
            and r.get("corpus_version") == manifest["corpus_version"]
            for r in reviews
        ):
            raise ValueError(f"frozen test split: missing review record: {q['id']}")
    actual = fingerprint_test_split(questions, spans)
    if actual != manifest["test_sha256"]:
        raise ValueError(
            f"frozen test split changed: test_sha256 {actual} != {manifest['test_sha256']}"
        )


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
    check_frozen(manifest, questions, spans, reviews)
    return {
        "corpus_version": manifest["corpus_version"],
        "frozen": manifest.get("frozen") is True,
        **({"test_sha256": manifest["test_sha256"]} if manifest.get("frozen") is True else {}),
        "documents": len(documents),
        "spans": len(spans),
        "questions": len(questions),
        "human_review_required": not require_reviewed,
        "split_counts": {
            s: sum(q["split"] == s for q in questions) for s in ("dev", "test")
        },
    }


def freeze(root: Path, frozen_by: str, frozen_at: str) -> dict:
    """Freeze the test split once the reviewed gate is green. Refuses to re-freeze."""
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("frozen") is True:
        raise ValueError("already frozen; unfreeze by hand first (see the dataset README)")
    if manifest.get("docproc", {}).get("docproc_dirty") is not False:
        raise ValueError("refusing to freeze a canonical built from uncommitted docproc")
    validate_retrieval(root, require_reviewed=True)
    spans = {s["span_id"]: s for s in read_jsonl(root / "evidence.jsonl")}
    questions = read_jsonl(root / "questions.master.jsonl")
    manifest.update(
        {
            "frozen": True,
            "frozen_at": frozen_at,
            "frozen_by": frozen_by,
            "test_sha256": fingerprint_test_split(questions, spans),
            "frozen_corpus_version": manifest["corpus_version"],
            "frozen_docproc_commit": manifest["docproc"]["commit"],
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return validate_retrieval(root, require_reviewed=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument(
        "--freeze", metavar="FROZEN_BY", help="freeze the test split (one-time, deliberate)"
    )
    args = parser.parse_args()
    try:
        if args.freeze:
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            result = freeze(args.dataset, args.freeze, stamp)
        else:
            result = validate_retrieval(args.dataset, args.require_reviewed)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"dataset invalid: {exc}\n")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
