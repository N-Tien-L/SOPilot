"""V2-22 on the V2-19 corpus: extract -> clean -> render -> chunk, then check chunk invariants.

Reuses the extraction of ``predict_extraction.py --clean`` (``<results>/structured/*.json``), so
Docling does not run again. Run with the ai-service environment from the repository root:

    HF_HUB_OFFLINE=1 services/ai-service/.venv/Scripts/python.exe eval/check_chunks_corpus.py \
        --structured eval/results/extraction-clean/structured \
        --out eval/results/chunk-invariants/report.json

Tokens are counted with the active embedding tokenizer (``BAAI/bge-m3``, local Hugging Face
cache only); ``--whitespace-tokens`` uses a whitespace count instead when the cache is missing.
The invariants are defined in ``sopilot_eval/chunk_invariants.py``. The report holds counts and
short snippets of violating chunks; ``eval/results`` is gitignored.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sopilot_ai.docproc import (
    ChunkConfig,
    ExtractionError,
    StructuredDocument,
    chunk_document,
    clean_document,
    render,
)
from sopilot_eval.chunk_invariants import (
    INVARIANTS,
    check_chunks,
    continuation_blockers,
)

BGE_M3 = ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181")


class Words:
    def count(self, text: str) -> int:
        return len(text.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--structured", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--whitespace-tokens", action="store_true")
    args = ap.parse_args()
    if args.whitespace_tokens:
        tokenizer, tokenizer_name = Words(), "whitespace"
    else:
        from sopilot_ai.docproc.tokens import HFTokenizer

        tokenizer = HFTokenizer(*BGE_M3, local_files_only=True)
        tokenizer_name = "@".join(BGE_M3)
    config = ChunkConfig()
    documents, failures = {}, {}
    totals: Counter = Counter()
    violations: Counter = Counter()
    checked: Counter = Counter()
    examples: list[dict] = []
    continuation: Counter = Counter()
    for path in sorted(args.structured.glob("*.json")):
        doc_id = path.stem
        doc = StructuredDocument.model_validate_json(path.read_text(encoding="utf-8"))
        blockers = continuation_blockers([e.model_dump() for e in doc.elements])
        continuation.update(blockers)
        result = clean_document(doc)
        rendered = render(result.document)
        try:
            chunks = chunk_document(rendered, tokenizer, title=doc_id,
                                    doc_code=result.meta.doc_code, config=config)
        except ExtractionError as exc:
            failures[doc_id] = exc.code.value
            continue
        report = check_chunks(rendered.markdown,
                              [e.model_dump() for e in rendered.elements],
                              [c.model_dump() for c in chunks],
                              max_tokens=config.max_tokens, doc_id=doc_id)
        tables = [e for e in rendered.elements if e.kind == "table" and e.char_start is not None]
        multi_page = sum(1 for e in tables if len(set(e.row_pages or [])) > 1)
        documents[doc_id] = {
            "file_type": doc.file_type, "page_count": doc.page_count,
            "chunks": report["chunks"], "by_kind": report["by_kind"],
            "tables": len(tables), "multi_page_tables": multi_page,
            "multi_page_table_chunks": report["multi_page_table_chunks"],
            "violations": {k: v for k, v in report["violations"].items() if v},
            "table_continuation_blockers": dict(blockers),
        }
        totals["documents"] += 1
        totals["chunks"] += report["chunks"]
        totals["tables"] += len(tables)
        totals["multi_page_tables"] += multi_page
        totals["multi_page_table_chunks"] += report["multi_page_table_chunks"]
        for kind, n in report["by_kind"].items():
            totals[f"chunks_{kind}"] += n
        checked.update(report["checked"])
        violations.update(report["violations"])
        examples += report["examples"]
    out = {
        "kind": "chunk_invariants_v2_22",
        "tokenizer": tokenizer_name,
        "chunk_config": vars(config),
        "pipeline": "StructuredDocument (V2-20) -> clean_document -> render -> chunk_document",
        "totals": dict(totals),
        "checked": {k: checked[k] for k in INVARIANTS},
        "violations": {k: violations[k] for k in INVARIANTS},
        "failures": failures,
        # body tables on consecutive pages that the extractor did not join, by failed condition
        "table_continuation_blockers": dict(continuation),
        "by_document": documents,
        "examples": examples[:200],
        "examples_total": len(examples),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps({"totals": out["totals"], "violations": out["violations"],
                                 "table_continuation_blockers": out[
                                     "table_continuation_blockers"]}) + "\n")


if __name__ == "__main__":
    main()
