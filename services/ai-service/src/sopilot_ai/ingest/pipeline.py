"""Steps 2–6 of an ingestion job (TECH-V2-ai-service §5.1): bytes in, chunks and the extraction
record out. Pure and synchronous; the worker runs it in a thread. All document logic lives in
``docproc`` (V2-20, V2-21, V2-22); this module only wires it together.
"""
from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass
from importlib import metadata

from sopilot_ai.docproc import (
    Chunk,
    ChunkConfig,
    CleanConfig,
    DocFamily,
    StructuredDocument,
    Tokenizer,
    chunk_document,
    clean_document,
    detect_family,
    extract,
    render,
)
from sopilot_ai.ingest.language import detect_language

# fileType of the job payload decides the parser; the original name is not trusted for it.
_SOURCE_NAME = {"PDF": "source.pdf", "MD": "source.md"}


@dataclass(frozen=True)
class ProcessedVersion:
    structure: dict
    markdown: str
    page_index: list[dict[str, int]] | None
    warnings: list[dict]
    normalizer_version: str
    page_count: int | None
    language: str | None
    family: DocFamily
    boilerplate: list[dict]
    meta: dict  # camelCase ExtractedMeta, as sent to core-api
    doc_code: str | None
    extractor: str
    chunks: list[Chunk]
    timings: dict[str, int]


def chunk_type(kind: str, family: DocFamily) -> str:
    """docproc ``Chunk.kind`` to ``rag.chunks.chunk_type`` (§3.3).

    docproc uses TEXT for every heading- or paragraph-based chunk; the schema names it after the
    unit it was cut on: PROSE in the PROSE family (paragraph packing), SECTION elsewhere.
    """
    if kind in ("PROCEDURE_STEP", "TABLE"):
        return kind
    return "PROSE" if family is DocFamily.PROSE else "SECTION"


def _library_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unknown"


def extractor_name(file_type: str) -> str:
    if file_type == "PDF":
        return f"docling {_library_version('docling')}"
    return f"markdown-it-py {_library_version('markdown-it-py')}"


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def process_document(data: bytes, file_type: str, *, title: str, tokenizer: Tokenizer,
                     chunk_config: ChunkConfig, clean_config: CleanConfig | None = None
                     ) -> ProcessedVersion:
    """Raises ``docproc.ExtractionError`` with the failure code for content errors."""
    timings: dict[str, int] = {}
    t = time.perf_counter()
    structured = extract(data, _SOURCE_NAME.get(file_type, f"source.{file_type.lower()}"))
    timings["extract_ms"] = _ms(t)

    t = time.perf_counter()
    clean_config = dataclasses.replace(clean_config or CleanConfig.from_env(),
                                       max_tokens=chunk_config.max_tokens)
    cleaned = clean_document(structured, clean_config, tokenizer)
    rendered = render(cleaned.document)
    timings["clean_ms"] = _ms(t)

    t = time.perf_counter()
    family = detect_family(rendered.elements)
    chunks = chunk_document(rendered, tokenizer, title=title, doc_code=cleaned.meta.doc_code,
                            config=chunk_config, family=family)
    timings["chunk_ms"] = _ms(t)

    doc = cleaned.document
    structure = StructuredDocument(
        file_type=doc.file_type, elements=rendered.elements, page_count=doc.page_count,
        frontmatter=doc.frontmatter, converter_warnings=doc.converter_warnings,
    ).model_dump(mode="json")
    page_index = ([{"page": p.page, "charStart": p.char_start, "charEnd": p.char_end}
                   for p in rendered.page_index] if doc.file_type == "PDF" else None)
    return ProcessedVersion(
        structure=structure,
        markdown=rendered.markdown,
        page_index=page_index,
        warnings=[w.model_dump(mode="json", exclude_none=True) for w in cleaned.warnings],
        normalizer_version=rendered.normalizer_version,
        page_count=doc.page_count,
        language=detect_language(rendered.markdown),
        family=family,
        boilerplate=[b.model_dump(mode="json") for b in cleaned.boilerplate],
        meta=cleaned.meta.model_dump(mode="json", by_alias=True),
        doc_code=cleaned.meta.doc_code,
        extractor=extractor_name(doc.file_type),
        chunks=chunks,
        timings=timings,
    )
