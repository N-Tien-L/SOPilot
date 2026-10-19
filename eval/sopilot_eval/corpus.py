"""Load a corpus directory into page-aware chunks."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    doc: str
    page: int
    text: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    # Text/Markdown: a form feed (\f) marks a page break; otherwise one page.
    return path.read_text(encoding="utf-8").split("\f")


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Paragraph-aware window splitter."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > size:
            out.append(cur)
            cur = cur[-overlap:] + "\n\n" + p if overlap else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
        while len(cur) > size * 2:  # a single huge paragraph
            out.append(cur[:size])
            cur = cur[size - overlap :]
    if cur.strip():
        out.append(cur)
    return out


def load_chunks(corpus_dir: Path, size: int = 800, overlap: int = 100) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.iterdir()):
        if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        for page_no, page in enumerate(_pages(path), start=1):
            for piece in split_text(page, size, overlap):
                chunks.append(Chunk(doc=path.name, page=page_no, text=piece))
    return chunks
