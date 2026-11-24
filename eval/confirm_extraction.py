"""V2-20 confirmation run: extract the V2-19 pilot PDFs with the ai-service adapter and record
time, peak RAM, and structure counts per document (ADR-008 section 5 / section 6).

Run with the ai-service environment so the measured code is the service's own ``docproc``:

    uv run --project services/ai-service --extra pdf python eval/confirm_extraction.py \
        --corpus datasets/extraction/pilot/local/corpus --out eval/results/extraction-confirm.json

Output holds counts and timings only, never document text.
"""
from __future__ import annotations

import argparse
import json
import sys
import platform
import threading
import time
import unicodedata
from importlib.metadata import version
from pathlib import Path

import psutil

from sopilot_ai.docproc import ExtractionError, extract, render


def say(message: str) -> None:
    sys.stdout.write(message + chr(10))
    sys.stdout.flush()


class PeakRss:
    """Samples this process's resident memory on a thread (peak, MB)."""

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

    @property
    def mb(self) -> float:
        return round(self.peak / 1e6, 1)


def measure(path: Path) -> dict:
    data = path.read_bytes()
    row: dict = {"file": path.name, "bytes": len(data)}
    start = time.perf_counter()
    with PeakRss() as rss:
        try:
            doc = extract(data, path.name)
            rendered = render(doc)
        except ExtractionError as exc:
            row.update(status="FAILED", failure_code=exc.code.value)
            row["seconds"] = round(time.perf_counter() - start, 1)
            row["peak_rss_mb"] = rss.mb
            return row
    seconds = time.perf_counter() - start
    content = [e for e in doc.elements if e.role == "content"]
    tables = [e for e in content if e.kind == "table"]
    row.update(
        status="OK",
        pages=doc.page_count,
        seconds=round(seconds, 1),
        seconds_per_page=round(seconds / max(doc.page_count or 1, 1), 2),
        peak_rss_mb=rss.mb,
        elements=len(doc.elements),
        content_elements=len(content),
        furniture_elements=len(doc.elements) - len(content),
        headings=sum(e.kind == "heading" for e in content),
        list_items=sum(e.kind == "list_item" for e in content),
        paragraphs=sum(e.kind == "paragraph" for e in content),
        tables=len(tables),
        multi_page_tables=sum((t.page_end or 0) > (t.page or 0) for t in tables),
        tables_with_cell_spans=sum(bool(t.cell_spans) for t in tables),
        cell_span_total=sum(len(t.cell_spans or []) for t in tables),
        pages_with_content=len({s.page for s in rendered.page_index}),
        markdown_chars=len(rendered.markdown),
        nfc=unicodedata.is_normalized("NFC", rendered.markdown),
        replacement_chars=rendered.markdown.count("�"),
        offsets_ok=all(
            rendered.markdown[e.char_start:e.char_end] for e in rendered.elements
            if e.role == "content"
        ),
    )
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*", help="file names to run (default: all PDFs)")
    args = ap.parse_args()

    files = sorted(args.corpus.glob("*.pdf"))
    if args.only:
        files = [f for f in files if f.name in args.only]
    machine = {
        "cpu": platform.processor(),
        "logical_cores": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
        "os": platform.platform(),
        "python": platform.python_version(),
        "docling": version("docling"),
        "docling_core": version("docling-core"),
        "device": "cpu",
        "ocr": False,
    }
    results = []
    for path in files:
        say(path.name)
        results.append(measure(path))
        say(json.dumps(results[-1], ensure_ascii=False))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"machine": machine, "documents": results},
                                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
