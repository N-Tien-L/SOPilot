"""Rebuild the draft V2-06 pilot from locked sources and explicit annotation seeds."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import pypdf

from .acquire import confined, digest
from .dataset import project_expected, validate_retrieval


def save_deterministic(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"refusing to overwrite edited pilot artifact: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def rows_bytes(rows: list[dict]) -> bytes:
    return ("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)).encode(
        "utf-8"
    )


def select_sections(text: str, titles: list[str]) -> str:
    sections = []
    headings = list(re.finditer(r"^(#{1,6}) (.+)$", text, re.MULTILINE))
    for title in titles:
        matches = [h for h in headings if h[2] == title]
        if len(matches) != 1:
            raise ValueError(f"section must resolve uniquely: {title}")
        h = matches[0]
        end = next(
            (
                n.start()
                for n in headings
                if n.start() > h.start() and len(n[1]) <= len(h[1])
            ),
            len(text),
        )
        section = text[h.start() : end]
        section = re.sub(r"<details\b.*?</details>", "", section, flags=re.DOTALL)
        if "{{" in section:
            raise ValueError("unresolved template/include in selected section")
        sections.append(section.strip())
    return "\n\n".join(sections) + "\n"


def build(root: Path, extraction_root: Path) -> dict:
    config = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    if pypdf.__version__ != config["pypdf_version"]:
        raise ValueError("pilot normalization requires the pinned pypdf version")
    retrieval_lock = json.loads(
        (root / "acquisition.lock.json").read_text(encoding="utf-8")
    )
    extraction_lock = json.loads(
        (extraction_root / "acquisition.lock.json").read_text(encoding="utf-8")
    )
    locks = {
        "gitlab": {d["doc_id"]: d for d in retrieval_lock["documents"]},
        "extraction": {d["doc_id"]: d for d in extraction_lock["documents"]},
    }
    documents, texts, page_map = [], {}, {}
    for selection in config["documents"]:
        doc_id, kind = selection["doc_id"], selection["source_dataset"]
        source = locks[kind][doc_id]
        source_root = root if kind == "gitlab" else extraction_root
        path = confined(source_root, source["path"])
        raw = path.read_bytes()
        if (
            source["status"] != "acquired"
            or source.get("verification_error")
            or digest(raw) != source["sha256"]
        ):
            raise ValueError(f"source lock verification failed: {doc_id}")
        if kind == "gitlab":
            text = unicodedata.normalize(
                "NFC", raw.decode("utf-8").replace("\r\n", "\n")
            )
            text = select_sections(text, selection["sections"])
        else:
            # Exploration only: no heading/table reconstruction or production docproc claim.
            reader = pypdf.PdfReader(path)
            text = ""
            page_map[doc_id] = []
            for number, page in enumerate(reader.pages, 1):
                part = " ".join(
                    unicodedata.normalize("NFC", page.extract_text() or "").split()
                )
                start = len(text)
                text += part + "\n\n"
                page_map[doc_id].append(
                    {"page": number, "start_char": start, "end_char": start + len(part)}
                )
        canonical = text.encode("utf-8")
        save_deterministic(root / "corpus" / f"{doc_id}.md", canonical)
        documents.append(
            {
                "doc_id": doc_id,
                "path": f"corpus/{doc_id}.md",
                "lang": source["lang"],
                "sha256": digest(canonical),
                "source": source["url"],
                "license": source["license"],
                "sha256_raw": source["sha256"],
                "source_commit": source.get("source_commit"),
                "redistribution": source["redistribution"],
                "selection": selection,
            }
        )
        texts[doc_id] = text
    seed = json.loads((root / "intents.seed.json").read_text(encoding="utf-8"))
    spans = []
    for item in seed["spans"]:
        text, quote = texts[item["doc_id"]], item["quote"]
        start, end = 0, len(text)
        if "page" in item:
            region = next(
                p for p in page_map[item["doc_id"]] if p["page"] == item["page"]
            )
            start, end = region["start_char"], region["end_char"]
        matches = list(re.finditer(re.escape(quote), text[start:end]))
        if len(matches) != 1:
            raise ValueError(f"evidence quote must resolve uniquely: {item['span_id']}")
        a = start + matches[0].start()
        spans.append(
            {
                "span_id": item["span_id"],
                "doc_id": item["doc_id"],
                "section_id": item["section_id"],
                "start_char": a,
                "end_char": a + len(quote),
                "quote": quote,
                "quote_sha": digest(quote.encode("utf-8")),
                **({"pages": [item["page"]]} if "page" in item else {}),
            }
        )
    by_span = {s["span_id"]: s for s in spans}
    by_doc = {d["doc_id"]: d for d in documents}
    questions = []
    for intent in seed["intents"]:
        for lang in ("vi", "en"):
            question = {
                "id": f"{intent['intent_id']}-{lang}",
                "intent_id": intent["intent_id"],
                "policy_family_id": intent["policy_family_id"],
                "leakage_group_id": intent["policy_family_id"],
                "split": "dev",
                "question": intent["questions"][lang],
                "lang": lang,
                "corpus_lang": intent["corpus_lang"],
                "cross_lingual": lang != intent["corpus_lang"],
                "answerable": bool(intent["evidence_sets"]),
                "evidence_sets": intent["evidence_sets"],
                "reference_answer": intent["answers"][lang],
                "query_types": intent["query_types"],
                "review_status": "draft",
                "label_version": "pilot-draft-v1",
                "drafted_by": "Codex",
            }
            question["expected"] = project_expected(question, by_span, by_doc)
            questions.append(question)
    manifest = {
        "corpus_version": config["corpus_version"],
        "normalization_version": "pilot-pypdf-flat-nfc-lf-v1+gitlab-sections-v1",
        "pypdf_version": pypdf.__version__,
        "purpose": "annotation-pilot-dev-only",
        "frozen": False,
        "production_docproc": False,
        "documents": documents,
    }
    for name, data in {
        "manifest.json": json_bytes(manifest),
        "page-map.json": json_bytes(page_map),
        "evidence.jsonl": rows_bytes(spans),
        "questions.master.jsonl": rows_bytes(questions),
    }.items():
        save_deterministic(root / name, data)
    if not (root / "review.jsonl").exists():
        (root / "review.jsonl").write_bytes(b"")
    return validate_retrieval(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--extraction-dataset", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.dataset.resolve(), args.extraction_dataset.resolve())
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"pilot preparation failed: {exc}\n")
    sys.stdout.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
