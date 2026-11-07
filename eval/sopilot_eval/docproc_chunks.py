"""Chunk a docproc dataset (V2-06 ``sop-main``) with ``sopilot_ai.docproc``, as ai-service indexes it.

The dataset keeps only canonical Markdown, but the chunker needs the rendered elements. They are
rebuilt from the cached extraction (``StructuredDocument`` JSON from ``predict_extraction.py``)
or, for Markdown sources, by extracting the source again; ``clean_document -> render`` must then
reproduce the frozen canonical **byte for byte** (``manifest.json`` ``sha256``), else this fails.
That makes chunk offsets valid against ``evidence.jsonl`` spans.

Tokens are counted with the tokenizer of the model being measured (TECH-V2-ai-service §6.5), from
the local Hugging Face cache only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .corpus import Chunk


def _source_document(doc_id: str, root: Path, structured_dir: Path | None, pilot_dir: Path | None):
    from sopilot_ai.docproc import StructuredDocument, extract

    if structured_dir is not None and (structured_dir / f"{doc_id}.json").is_file():
        text = (structured_dir / f"{doc_id}.json").read_text(encoding="utf-8")
        return StructuredDocument.model_validate_json(text), "structured"
    selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    sel = next((d for d in selection["documents"] if d["doc_id"] == doc_id), None)
    if sel and sel.get("source_dataset") == "pilot" and pilot_dir is not None:
        manifest = json.loads((pilot_dir / "manifest.json").read_text(encoding="utf-8"))
        doc = next(d for d in manifest["documents"] if d["doc_id"] == doc_id)
        path = pilot_dir / doc["path"]
        if path.suffix.lower() != ".md":
            raise ValueError(f"{doc_id}: only Markdown sources are re-extracted here; add a structured JSON")
        return extract(path.read_bytes(), path.name), "markdown"
    raise ValueError(f"{doc_id}: no cached extraction and no Markdown source")


def load_docproc_chunks(root: Path, tokenizer_model: str, tokenizer_revision: str | None,
                        structured_dir: Path | None, pilot_dir: Path | None,
                        target_tokens: int = 384, max_tokens: int = 512) -> tuple[list[Chunk], dict]:
    from sopilot_ai.docproc import (
        NORMALIZER_VERSION,
        ChunkConfig,
        chunk_document,
        clean_document,
        render,
    )
    from sopilot_ai.docproc.tokens import HFTokenizer

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    tokenizer = HFTokenizer(tokenizer_model, tokenizer_revision, local_files_only=True)
    config = ChunkConfig(target_tokens=target_tokens, max_tokens=max_tokens)
    chunks: list[Chunk] = []
    sources: dict[str, str] = {}
    for doc in manifest["documents"]:
        doc_id = doc["doc_id"]
        structured, sources[doc_id] = _source_document(doc_id, root, structured_dir, pilot_dir)
        result = clean_document(structured)
        rendered = render(result.document)
        if hashlib.sha256(rendered.markdown.encode("utf-8")).hexdigest() != doc["sha256"]:
            raise ValueError(f"{doc_id}: rebuilt canonical differs from the frozen corpus; offsets invalid")
        name = Path(doc["path"]).name
        for c in chunk_document(rendered, tokenizer, title=doc_id, doc_code=result.meta.doc_code, config=config):
            chunks.append(Chunk(
                doc=name, page=c.page_start, text=c.content, index_text=c.index_text,
                char_start=c.char_start, char_end=c.char_end, page_end=c.page_end,
                lang=doc.get("lang"), kind=c.kind, section_path=tuple(c.section_path), doc_id=doc_id,
            ))
    info = {
        "mode": "docproc",
        "normalizer_version": NORMALIZER_VERSION,
        "corpus_normalization_version": manifest.get("normalization_version"),
        "docproc_commit_of_corpus": manifest.get("docproc", {}).get("commit"),
        "tokenizer": f"{tokenizer_model}@{tokenizer_revision}",
        "target_tokens": target_tokens,
        "max_tokens": max_tokens,
        "title": "doc_id",
        "sources": sources,
        "chunks_sha256": hashlib.sha256(
            "\n".join(f"{c.doc_id}:{c.char_start}:{c.char_end}:{c.index_text}" for c in chunks).encode("utf-8")
        ).hexdigest(),
    }
    return chunks, info
