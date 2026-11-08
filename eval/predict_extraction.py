"""Run the ai-service PDF adapter on a labelled corpus and write scorer predictions (V2-20).

Run with the ai-service environment so the measured code is the service's own ``docproc``:

    uv run --project services/ai-service --extra pdf python eval/predict_extraction.py \
        --dataset datasets/extraction/pilot --out eval/results/extraction-docling

Two prediction files are written from one extraction pass:
  predictions.docling.jsonl            headings = Docling heading elements only
  predictions.docling+numbering.jsonl  also treats a short numbered list item (``5.1 Title``)
                                       as a heading, level = depth of the number

Documents without labelled pages (for example scans) are skipped. Tables that continue over
several pages are split into one fragment per page, matching how the labels are written.
Output holds structure and measurements, no document text beyond heading strings.

``--clean`` (V2-21) runs extract -> ``clean_document`` -> render and writes, from one
extraction pass per file:
  predictions.raw.jsonl     render without cleaning (numbering headings, full Markdown)
  predictions.clean.jsonl   render after cleaning, plus the removed ``boilerplate`` blocks
  structured/<doc_id>.json  the extracted ``StructuredDocument`` before cleaning, so the chunk
                            check (``check_chunks_corpus.py``) does not run Docling again
Markdown files are included (no pages); rejection fixtures are not. ``--reuse-structured``
loads ``structured/<doc_id>.json`` when present instead of extracting (``elapsed_ms`` is then
null). These files hold document text; ``eval/results`` is gitignored. Score them with
``python -m sopilot_eval.cleaning``.
"""
from __future__ import annotations

import argparse
import json
import sys
import re
import threading
import time
from pathlib import Path

import psutil

from sopilot_ai.docproc import (
    ExtractionError,
    StructuredDocument,
    clean_document,
    extract,
    render,
)

NUMBERED = re.compile(r"^\d+(?:\.\d+)*\.?$")


def say(message: str) -> None:
    sys.stdout.write(message + chr(10))
    sys.stdout.flush()


class PeakRss:
    def __init__(self) -> None:
        self._proc = psutil.Process()
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._proc.memory_info().rss)
            time.sleep(0.05)

    def __enter__(self) -> PeakRss:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()


def table_fragments(el) -> list[dict]:
    rows = el.rows
    pages = el.row_pages or [el.page] * len(rows)
    header = el.header_rows
    out = []
    for page in dict.fromkeys(pages):  # keeps page order
        idx = [i for i, p in enumerate(pages) if p == page]
        has_header = header > 0 and 0 in idx
        skip = header if has_header else 0
        data = [i for i in idx if i >= skip]
        if not data:
            continue
        position = {row: n for n, row in enumerate(data)}
        spans = []
        for r, c, rs, cs in el.cell_spans or []:
            if r in position:
                spans.append({"row": position[r], "col": c,
                              "rowspan": min(rs, len(data) - position[r]), "colspan": cs})
        out.append({
            "page": page, "rows": len(data), "cols": len(rows[0]),
            "column_titles": [c.strip() for c in rows[0]] if has_header else [],
            "cell_spans": spans,
        })
    return out


def predict(path: Path, pages: list[int]) -> tuple[dict, dict]:
    data = path.read_bytes()
    start = time.perf_counter()
    with PeakRss() as rss:
        doc = extract(data, path.name)
        rendered = render(doc)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return rows_for(path.stem, doc, rendered, pages, round(elapsed_ms, 1),
                    round(rss.peak / 1e6, 1))


def rows_for(doc_id: str, doc, rendered, pages: list[int], elapsed_ms, peak_ram_mb,
             full_markdown: bool = False) -> tuple[dict, dict]:
    plain, numbered, tables = [], [], []
    for el in rendered.elements:
        if el.role != "content":
            continue
        if el.kind == "heading":
            h = {"text": el.text, "level": el.level or 1, "page": el.page}
            plain.append(h)
            numbered.append(h)
        elif el.kind == "list_item" and el.number and NUMBERED.match(el.number) \
                and len(el.text) <= 100:
            depth = len(el.number.rstrip(".").split("."))
            numbered.append({"text": f"{el.number} {el.text}", "level": min(depth, 6),
                             "page": el.page})
        elif el.kind == "table":
            tables.extend(table_fragments(el))
    by_page = {s.page: rendered.markdown[s.char_start:s.char_end] for s in rendered.page_index}
    base = {
        "doc_id": doc_id, "tables": tables, "metadata": {},
        "canonical_markdown": rendered.markdown if full_markdown else "",
        "page_markdown": {str(p): by_page.get(p, "") for p in pages},
        "page_count": doc.page_count, "elapsed_ms": elapsed_ms, "peak_ram_mb": peak_ram_mb,
    }
    return {**base, "headings": plain}, {**base, "headings": numbered}


def predict_clean(path: Path, pages: list[int], structured: Path,
                  reuse: bool) -> tuple[dict, dict]:
    """One extraction, two renders: before and after ``clean_document`` (V2-21)."""
    cached = structured / f"{path.stem}.json"
    elapsed_ms = peak = None
    if reuse and cached.exists():
        doc = StructuredDocument.model_validate_json(cached.read_text(encoding="utf-8"))
    else:
        start = time.perf_counter()
        with PeakRss() as rss:
            doc = extract(path.read_bytes(), path.name)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        peak = round(rss.peak / 1e6, 1)
        cached.write_text(doc.model_dump_json(), encoding="utf-8")
    if not pages and doc.page_count:
        pages = list(range(1, doc.page_count + 1))
    _, raw = rows_for(path.stem, doc, render(doc), pages, elapsed_ms, peak, True)
    result = clean_document(doc)
    _, clean = rows_for(path.stem, result.document, render(result.document), pages,
                        elapsed_ms, peak, True)
    clean["boilerplate"] = [b.model_dump() for b in result.boilerplate]
    clean["metadata"] = result.meta.model_dump(exclude_none=True)
    clean["warnings"] = [w.model_dump(exclude_none=True) for w in result.warnings]
    return raw, clean


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--clean", action="store_true",
                    help="also run clean_document; write predictions.raw/clean.jsonl")
    ap.add_argument("--reuse-structured", action="store_true",
                    help="with --clean: load structured/<doc_id>.json instead of extracting")
    args = ap.parse_args()
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    labels, rejected = {}, set()
    for line in (args.dataset / "annotations.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            labels[rec["doc_id"]] = rec.get("annotated_pages") or []
            if rec.get("expected_outcome") == "FAILED":
                rejected.add(rec["doc_id"])
    args.out.mkdir(parents=True, exist_ok=True)
    if args.clean:
        run_clean(args, manifest, labels, rejected)
        return
    plain_rows, numbered_rows, failures = [], [], {}
    for entry in manifest["documents"]:
        doc_id = entry["doc_id"]
        pages = labels.get(doc_id) or []
        if not pages or (args.only and doc_id not in args.only):
            continue
        say(doc_id)
        try:
            plain, numbered = predict(args.dataset / entry["path"], pages)
        except ExtractionError as exc:
            failures[doc_id] = exc.code.value
            continue
        plain_rows.append(plain)
        numbered_rows.append(numbered)
        say(f"  {plain['elapsed_ms'] / 1000:.1f}s, {plain['peak_ram_mb']} MB")
    for name, rows in (("docling", plain_rows), ("docling+numbering", numbered_rows)):
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        (args.out / f"predictions.{name}.jsonl").write_text(text, encoding="utf-8")
    (args.out / "failures.json").write_text(json.dumps(failures), encoding="utf-8")


def run_clean(args, manifest: dict, labels: dict, rejected: set) -> None:
    structured = args.out / "structured"
    structured.mkdir(exist_ok=True)
    raw_rows, clean_rows, failures = [], [], {}
    for entry in manifest["documents"]:
        doc_id = entry["doc_id"]
        if doc_id in rejected or doc_id not in labels or (args.only and doc_id not in args.only):
            continue
        say(doc_id)
        try:
            raw, clean = predict_clean(args.dataset / entry["path"], labels[doc_id], structured,
                                       args.reuse_structured)
        except ExtractionError as exc:
            failures[doc_id] = exc.code.value
            continue
        raw_rows.append(raw)
        clean_rows.append(clean)
        if raw["elapsed_ms"] is not None:
            say(f"  {raw['elapsed_ms'] / 1000:.1f}s, {raw['peak_ram_mb']} MB")
    for name, rows in (("raw", raw_rows), ("clean", clean_rows)):
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        (args.out / f"predictions.{name}.jsonl").write_text(text, encoding="utf-8")
    (args.out / "failures.json").write_text(json.dumps(failures), encoding="utf-8")


if __name__ == "__main__":
    main()
