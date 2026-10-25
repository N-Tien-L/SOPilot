"""Acquire public corpus bytes with hash locks; probe PDF text without OCR (V2-06/19)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from pypdf import __version__ as pypdf_version
from pypdf.errors import PyPdfError

MAX_BYTES = 20 * 1024 * 1024


def confined(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("acquisition path must stay inside dataset")
    return path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def probe_pdf(path: Path) -> dict:
    """A text-layer inventory, not Docling output or a layout-quality benchmark."""
    reader = PdfReader(path)
    if reader.is_encrypted:
        return {"classification": "encrypted", "ocr_enabled": False}
    pages = []
    for number, page in enumerate(reader.pages, 1):
        text = unicodedata.normalize("NFC", page.extract_text() or "")
        pages.append(
            {
                "page": number,
                "non_whitespace_characters": sum(not c.isspace() for c in text),
                "replacement_characters": text.count("\ufffd"),
                "cid_markers": text.count("(cid:"),
            }
        )
    empty = [p["page"] for p in pages if not p["non_whitespace_characters"]]
    return {
        "parser": "pypdf",
        "parser_version": pypdf_version,
        "ocr_enabled": False,
        "page_count": len(pages),
        "pages_without_text": empty,
        "classification": "no_text"
        if len(empty) == len(pages)
        else "mixed"
        if empty
        else "text",
        "pages": pages,
    }


def acquire_one(root: Path, source: dict, previous: dict, offline: bool) -> dict:
    row = {**(previous if previous.get("url") == source["url"] else {}), **source}
    row.pop("verification_error", None)
    row.pop("error", None)
    try:
        path = confined(root, source["path"])
        url = source["url"]
        if not url.startswith("https://"):
            raise ValueError("only public HTTPS source URLs are supported")
        pinned = source.get("sha256") or (
            previous.get("sha256") if previous.get("url") == url else None
        )
        if path.exists():
            if not pinned:
                raise ValueError(
                    "existing file has no hash lock; move it aside explicitly"
                )
            data = path.read_bytes()
            retrieved = previous.get("retrieved_at")
        else:
            if offline:
                raise ValueError("source bytes missing in offline mode")
            request = urllib.request.Request(
                url, headers={"User-Agent": "SOPilot-corpus/0.1"}
            )
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read(MAX_BYTES + 1)
                row["resolved_url"] = response.url
                row["content_type"] = response.headers.get("Content-Type")
            retrieved = datetime.now(UTC).isoformat()
        if len(data) > MAX_BYTES:
            raise ValueError("source exceeds 20 MiB acquisition limit")
        actual = digest(data)
        if pinned and actual != pinned:
            raise ValueError("source hash changed; refusing to replace locked bytes")
        if path.suffix.lower() == ".pdf" and not data.startswith(b"%PDF-"):
            raise ValueError("source response is not PDF bytes")
        if path.suffix.lower() == ".md":
            text = data.decode("utf-8")
            if text.lstrip().lower().startswith(("<!doctype html", "<html")):
                raise ValueError("HTML response cannot be stored as Markdown")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        row.update(
            sha256=actual, bytes=len(data), retrieved_at=retrieved, status="acquired"
        )
        if path.suffix.lower() == ".pdf":
            row["probe"] = probe_pdf(path)
    except (OSError, ValueError, TypeError, KeyError, PyPdfError) as exc:
        row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = args.sources.resolve().parent
    spec = json.loads(args.sources.read_text(encoding="utf-8"))
    sources = spec["documents"]
    ids = [s["doc_id"] for s in sources]
    paths = [confined(root, s["path"]) for s in sources]
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
        parser.exit(1, "duplicate source ID or output path\n")
    lock_path = root / "acquisition.lock.json"
    old = (
        json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
    )
    previous = {s["doc_id"]: s for s in old.get("documents", [])}
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(
            executor.map(
                lambda s: acquire_one(
                    root, s, previous.get(s["doc_id"], {}), args.offline
                ),
                sources,
            )
        )
    # Preserve successful pins even if a later verification fails.
    locked = []
    for row in records:
        if row["status"] == "failed" and row["doc_id"] in previous:
            retained = dict(previous[row["doc_id"]])
            retained["verification_error"] = row["error"]
            locked.append(retained)
        else:
            locked.append(row)
    write_json(
        lock_path, {"corpus_version": spec["corpus_version"], "documents": locked}
    )
    sys.stdout.write(
        json.dumps(
            [
                {
                    "doc_id": r["doc_id"],
                    "status": r["status"],
                    **(
                        {"probe": {k: v for k, v in r["probe"].items() if k != "pages"}}
                        if "probe" in r
                        else {}
                    ),
                    **({"error": r["error"]} if "error" in r else {}),
                }
                for r in records
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    if any(r["status"] != "acquired" for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
