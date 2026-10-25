"""Build a self-contained review page for the V2-19 PDF labels.

    python eval/review_ui/build.py

Reads datasets/extraction/pilot/{annotations.jsonl,manifest.json,local/previews}; writes
datasets/extraction/pilot/local/review.html (local/ is git-ignored). Open the file in a browser,
review, download ``annotations.review.json``, then run ``apply_review.py``.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "datasets" / "extraction" / "pilot"


def say(message: str) -> None:
    sys.stdout.write(message + chr(10))
    sys.stdout.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, default=PILOT)
    args = ap.parse_args()
    pilot: Path = args.pilot

    manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))
    families = {d["doc_id"]: d.get("family", "") for d in manifest.get("documents", [])}
    docs = []
    for line in (pilot / "annotations.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        images = {}
        for img in sorted((pilot / "local" / "previews").glob(f"{rec['doc_id']}-p*.png")):
            m = re.search(r"-p(\d+)\.png$", img.name)
            if m:
                b64 = base64.b64encode(img.read_bytes()).decode("ascii")
                images[int(m.group(1))] = f"data:image/png;base64,{b64}"
        pdf = pilot / "local" / "corpus" / f"{rec['doc_id']}.pdf"
        docs.append({
            "doc_id": rec["doc_id"],
            "family": families.get(rec["doc_id"], ""),
            "annotated_pages": rec.get("annotated_pages", []),
            "headings": rec.get("headings", []),
            "tables": rec.get("tables", []),
            "furniture": rec.get("furniture", []),
            "metadata": rec.get("metadata", {}),
            "cross_references": rec.get("cross_references", []),
            "drafted_by": rec.get("drafted_by"),
            "coverage_note": rec.get("coverage_note"),
            "images": images,
            "pdf_href": f"corpus/{pdf.name}" if pdf.exists() else None,
        })
    label_version = next((json.loads(x).get("label_version", "draft")
                          for x in (pilot / "annotations.jsonl").read_text(encoding="utf-8").splitlines()
                          if x.strip()), "draft")
    payload = json.dumps({"label_version": label_version, "docs": docs}, ensure_ascii=False)
    template = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    out = pilot / "local" / "review.html"
    out.write_text(template.replace("__DATA__", payload.replace("</", "<" + chr(92) + "/")), encoding="utf-8")
    say(f"wrote {out} ({out.stat().st_size // 1024} KB, {len(docs)} documents)")


if __name__ == "__main__":
    main()
