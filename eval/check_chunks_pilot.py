"""V2-47: chunk quality over the pilot corpus, through the real ingest path.

Mirrors ``ingest.pipeline.process_document`` without DB or S3: extract -> clean -> render ->
detect_family -> chunk. Reports per file the family, chunk counts, chunks under the minimum size,
chunks with no letters, uncovered body elements, step chunks and the V2-22 chunk invariants
(``sopilot_eval/chunk_invariants.py``). Metric definitions: ``sopilot_eval/pilot_chunks.py``.

Run from ``services/ai-service`` (PowerShell):

    $env:PYTHONPATH="src"; $env:HF_HUB_OFFLINE="1"; uv run --extra pdf python ../../eval/check_chunks_pilot.py --corpus ../../datasets/extraction/pilot/local/corpus --cache ../../eval/results/pilot-chunks/cache --out ../../eval/results/pilot-chunks/<label>.json

Only the raw ``extract()`` output is cached (``<cache>/<doc id>.<sha256[:16]>.json``); cleaning and
chunking always rerun. ``datasets/extraction/pilot/local`` and ``eval/results`` are gitignored.
Tokens use the active embedding tokenizer from ``models.yaml`` (local Hugging Face cache only);
``--whitespace-tokens`` counts whitespace words instead.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sopilot_ai.docproc import (
    NORMALIZER_VERSION,
    CleanConfig,
    ExtractionError,
    StructuredDocument,
    chunk_document,
    clean_document,
    detect_family,
    render,
)
from sopilot_ai.docproc.chunk.headings import resolve_outline

from sopilot_eval import pilot_chunks as pc
from sopilot_eval.chunk_invariants import INVARIANTS, check_chunks

DEFAULT_MODELS = REPO_ROOT / "services" / "ai-service" / "config" / "models.yaml"
# file suffix -> (job fileType, source name), as ingest.pipeline._SOURCE_NAME
FILE_TYPES = {".pdf": ("PDF", "source.pdf"), ".md": ("MD", "source.md")}
UNPINNED = "unpinned"


class Words:
    def count(self, text: str) -> int:
        return len(text.split())


def _extract(data: bytes, source_name: str, cache_file: Path):
    """``(StructuredDocument | None, failure | None)``; the raw extract() output is cached."""
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if "failure" in cached:
            return None, cached["failure"]
        return StructuredDocument.model_validate(cached["structured"]), None
    from sopilot_ai.docproc import (
        extract,  # Docling is only needed when nothing is cached
    )

    try:
        structured = extract(data, source_name)
    except ExtractionError as exc:
        failure = {"stage": "extract", "code": exc.code.value}
        payload, result = {"failure": failure}, (None, failure)
    else:
        payload, result = {"structured": structured.model_dump(mode="json")}, (structured, None)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return result


def _process(path: Path, cache: Path, tokenizer, chunk_config) -> dict:
    doc_id = path.stem
    data = path.read_bytes()
    file_type, source_name = FILE_TYPES[path.suffix.lower()]
    digest = hashlib.sha256(data).hexdigest()[:16]
    structured, failure = _extract(data, source_name, cache / f"{doc_id}.{digest}.json")
    if failure:
        return {"file_type": file_type, "failure": failure}
    stage = "clean"
    try:
        clean_config = dataclasses.replace(CleanConfig.from_env(), max_tokens=chunk_config.max_tokens)
        cleaned = clean_document(structured, clean_config, tokenizer)
        rendered = render(cleaned.document)
        stage = "chunk"
        family = detect_family(rendered.elements)
        chunks = chunk_document(rendered, tokenizer, title=doc_id, doc_code=cleaned.meta.doc_code,
                                config=chunk_config, family=family)
    except ExtractionError as exc:
        return {"file_type": file_type, "page_count": structured.page_count,
                "failure": {"stage": stage, "code": exc.code.value}}
    elements = [e.model_dump() for e in rendered.elements]
    chunk_dicts = [c.model_dump() for c in chunks]
    report = check_chunks(rendered.markdown, elements, chunk_dicts,
                          max_tokens=chunk_config.max_tokens, doc_id=doc_id)
    nodes = resolve_outline(rendered.elements)
    spans = [(n.el.char_start, n.el.char_end, n.level is None)
             for n in nodes if n.el.char_start is not None]
    uncovered, examples = pc.uncovered_body(spans, chunk_dicts, rendered.markdown)
    return {
        "file_type": file_type, "page_count": structured.page_count, "family": family.value,
        "chunks": report["chunks"], "by_kind": report["by_kind"],
        "under_min": pc.under_min(chunk_dicts, chunk_config.min_tokens),
        "no_letters": pc.no_letters(chunk_dicts),
        "step_chunks": pc.step_chunks(chunk_dicts),
        "uncovered_body": uncovered, "uncovered_examples": examples,
        "markdown_sha256": pc.markdown_sha256(rendered.markdown),
        "violations": {k: v for k, v in report["violations"].items() if v},
        "_violations_all": report["violations"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models-config", type=Path, default=DEFAULT_MODELS)
    ap.add_argument("--whitespace-tokens", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from sopilot_ai.providers.registry import ModelsConfig

    models = ModelsConfig.load(args.models_config)
    chunk_config = models.chunking()
    if args.whitespace_tokens:
        tokenizer, tokenizer_name = Words(), "whitespace"
    else:
        from sopilot_ai.docproc.tokens import HFTokenizer

        spec = models.embedding()
        revision = None if spec.revision == UNPINNED else spec.revision
        tokenizer = HFTokenizer(spec.tokenizer, revision, local_files_only=True)
        tokenizer_name = f"{spec.tokenizer}@{revision}"

    files = sorted((p for p in args.corpus.iterdir() if p.suffix.lower() in FILE_TYPES),
                   key=lambda p: p.name)
    documents: dict[str, dict] = {}
    totals: Counter = Counter()
    failures: Counter = Counter()
    violations: Counter = Counter({k: 0 for k in INVARIANTS})
    for path in files:
        result = _process(path, args.cache, tokenizer, chunk_config)
        all_violations = result.pop("_violations_all", None)
        documents[path.stem] = result
        totals["documents"] += 1
        if "failure" in result:
            failures[result["failure"]["code"]] += 1
            continue
        for key in ("chunks", "under_min", "no_letters", "step_chunks", "uncovered_body"):
            totals[key] += result[key]
        violations.update(all_violations)

    out = {
        "kind": "pilot_chunk_quality_v2_47",
        "tokenizer": tokenizer_name,
        "chunk_config": vars(chunk_config),
        "normalizer_version": NORMALIZER_VERSION,
        "totals": {**totals, "failures": dict(failures),
                   "violations": {k: violations[k] for k in INVARIANTS}},
        "by_document": documents,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("| file | family | chunks | <64 | no letters | uncovered | steps | md sha | "
          "violations or failure |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, d in documents.items():
        if "failure" in d:
            print(f"| {name} | - | - | - | - | - | - | - | "
                  f"{d['failure']['stage']}:{d['failure']['code']} |")
            continue
        viol = ", ".join(f"{k}={v}" for k, v in d["violations"].items()) or "0"
        print(f"| {name} | {d['family']} | {d['chunks']} | {d['under_min']} | {d['no_letters']} | "
              f"{d['uncovered_body']} | {d['step_chunks']} | {d['markdown_sha256'][:8]} | {viol} |")
    print("violations: " + ", ".join(f"{k}={violations[k]}" for k in INVARIANTS))


if __name__ == "__main__":
    main()
