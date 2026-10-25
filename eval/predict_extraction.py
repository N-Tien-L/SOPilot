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

from sopilot_ai.docproc import ExtractionError, extract, render

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
        "doc_id": path.stem, "tables": tables, "metadata": {}, "canonical_markdown": "",
        "page_markdown": {str(p): by_page.get(p, "") for p in pages},
        "page_count": doc.page_count, "elapsed_ms": round(elapsed_ms, 1),
        "peak_ram_mb": round(rss.peak / 1e6, 1),
    }
    return {**base, "headings": plain}, {**base, "headings": numbered}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    labels = {}
    for line in (args.dataset / "annotations.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            labels[rec["doc_id"]] = rec.get("annotated_pages") or []
    args.out.mkdir(parents=True, exist_ok=True)
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


if __name__ == "__main__":
    main()
