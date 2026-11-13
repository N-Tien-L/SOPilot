---
id: AUDIT-ingestion-sop-data-2026-10-19
title: "SOP ingestion pipeline analysis: formats, real document structure and gaps"
status: final
type: audit
scope: ingestion
verdict: conditional-recommendation
author: "Owner"
created: 2026-10-19
updated: 2026-11-13
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-09-ai-service-ingest-retrieval.md
  - docs/research/research-02-dataset-and-labeling.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Quoted Vietnamese document fragments are kept with an English gloss.

> **Owner decision 2026-10-20:** DOCX is deferred until after the V2 MVP to reduce extraction and testing complexity. The current scope is PDFs with a text layer, MD, TXT (PRD-V2 FR-06); DOCX returns `415` at upload, creates no job and points to exporting a PDF with a text layer. The DOCX observations in this audit are history, not MVP acceptance requirements. No ticket status or counter changes.


# SOP ingestion pipeline analysis

Scope: `services/ingestion-service` (main flow `pipeline.py`), `preview_extractor.py`, and the Tika/PDFBox extraction in knowledge-service. Code reading and one small probe only; no code changed.

## 1. Main conclusions

The pipeline was written for **a sample dataset of English Markdown handbooks** (`ingest_base_dataset.py`: `BASE_DATASET_PATH = "/app/base_dataset/handbook"`, scanning only `*.md`; the standardizer has a regex removing Hugo shortcodes). It was not designed for Vietnamese enterprise SOPs as DOCX/PDF. Multi-format support (images, OCR, XLSX) was bolted on, while understanding document structure was not done.

All three initial suspicions are correct:
1. Too many formats (images, OCR) while DOCX/PDF/MD are not handled cleanly yet.
2. The "frame" (national motto, slogan, signatures, headers/footers, approval tables) is not separated from the content.
3. It assumes a legal-text structure (Chương/Điều/Khoản: chapter/article/clause); ISO-style SOPs and non-standard documents are split wrongly.

## 2. Current state (checked in code and a probe)

### 2.1. Formats
- There are 3 extractors: `extractors/*` (main flow), `preview_extractor.py` (LLM metadata suggestions), Tika/PDFBox in knowledge-service (`DocumentParsingService`). `services/extractor.py` is dead code.
- knowledge-service's `FileType` allows `XLSX/DOC/XLS`, but ingestion has no extractor for these extensions: the upload succeeds, and the pipeline goes `FAILED` with `No extractor for extension`.
- PDF: tesseract OCR at 300 dpi for every page with fewer than `ocr_fallback_min_text_length=50` characters (including cover pages and signature pages). It runs synchronously inside an `async` function, blocking the event loop. Images are OCRed twice (`image_to_data` then `image_to_string`). The code default is `ocr_language="eng"`; `.env.example` sets `eng+vie` (whether compose passes this variable was not checked).

### 2.2. Extraction
- Extractors create `chunks` with heading styles and page numbers, but `pipeline.py` uses only `extracted.text`: page numbers are lost (no page-level citations possible) and DOCX heading styles are lost.
- DOCX (`extractors/docx.py`): tables are pushed to the end of the text; merged cells are repeated; Word's automatic numbering ("1.", "5.1", "a)") is not in `para.text`; `page_count` is the number of Word sections.
- PDF (`extractors/pdf.py`): raw `get_text("text")`; headers/footers repeated on every page ("Mã số · Lần ban hành · Trang x/y": code · issue · page x/y) mixed into the content; tables flattened; lines broken mid-sentence.

### 2.3. Standardizer (`standardizer.py`)
A probe with a Vietnamese SOP sample gives:

| Input | Result |
|---|---|
| `Điều 1. Mục đích` (Article 1. Purpose) | `title='1'`, the heading line removed from the chunk content |
| The 3rd section | `path=['', '1', '2', '5']` (accumulating siblings, not parents) |
| `...căn cứ ⏎ Điều 5 Luật Doanh nghiệp.` (…pursuant to ⏎ Article 5 of the Enterprise Law.) | Wrongly split into a new heading |
| `1. MỤC ĐÍCH` (1. PURPOSE), `5.1 Lập đề nghị...` (5.1 Prepare the request...) | Not recognized as headings |
| National motto, slogan, document code | Become a separate embedded section/chunk |

### 2.4. Chunking and embedding (`chunker.py`, `embedding_service.py`)
- Tokens are counted with `cl100k_base`, which does not match the embedding model; Vietnamese is about 2.3 tokens/word (probe: 32 tokens for 14 words).
- Cutting by tokens can cut in the middle of a UTF-8 character, producing "�" at chunk edges (probe: 1/31 cut points broken).
- Parent chunks have no size limit, but `embed_batch` truncates to 512 tokens: long sections only have their beginning embedded.
- Child chunks carry no title/context.
- `_build_token_char_index` is O(n²).

### 2.5. Dedup (`deduplicator.py`)
The semantic fingerprint takes 3 windows (the first 3000, middle 4000 and last 2000 characters), each truncated to 512 tokens, compared against a blocking threshold of 0.98 with every version. Risk (not measured on real data): a revision of the same SOP that changes a few steps outside the 3 windows is marked `DUPLICATE` and skipped; two different SOPs sharing a template may be treated as duplicates.

### 2.6. Other bugs
- `ALLOWED_BUCKETS` lacks `sopilot-documents`; `embedding_model="BGE_M3"` is hard-coded (already in the drift notes of `CLAUDE.md`).
- An empty extraction still becomes `READY` with 0 chunks.
- `mark_not_latest` is called before `bulk_insert`; if the insert fails it relies on rollback.

## 3. Real-world SOPs

> No real SOP file could be opened (the THADS PDFs returned 404). This section is compiled from search results and known standards, not an analysis of a real corpus.

| Document family | Signs | Informative part |
|---|---|---|
| ISO 9001 procedures (most common in VN) | A header table on each page (document code, issue number, effective date, page x/y); a Drafted/Reviewed/Approved table; a revision tracking table; numbered sections Purpose, Scope, Referenced documents, Definitions, Content, Forms, Records | "Content" is usually a table or flowchart: Responsibility / Steps / Description / Forms |
| Administrative documents (Decree 30/2020) | National motto, slogan, number/symbol, summary, recipients, signature, seal; regulations use Chapter/Article/Clause | The Article/Clause body |
| GMP/FDA SOPs, EPA QA/G-6 | Purpose, Scope, Responsibilities, Procedure (multi-level numbered steps), References, Revision history | Procedure |
| Wikis/handbooks (Markdown, Confluence) | Clear `#` headings, little frame | Everything |
| Non-standard | Bold-text headings, hand-typed numbers, continuous text | Structure has to be guessed |

The frame should be **removed from the index but kept as metadata**: document code, issue number, effective date, approver.

## 4. Similar systems

| System | Worth learning |
|---|---|
| Docling | A document tree with element types; HybridChunker splits by structure, merges small fragments, repeats table headers, tokenizer matching the embedding model |
| Unstructured | Typed elements (Title, NarrativeText, ListItem, Table, Header, Footer); `chunk_by_title` |
| RAGFlow | Chunk templates by document type (General, Laws, Manual, Table...) and layout recognition with a vision model |
| MarkItDown / Mammoth | DOCX → Markdown keeping Heading 1–6 and tables; does not recognize fake bold-text headings |
| Anthropic Contextual Retrieval | Prepends 50–100 tokens of context to each chunk before embedding and BM25 indexing |

## 5. Proposed approach

1. **A real SOP corpus (20–50 files)** across many document families, labelled by type, as the extraction quality yardstick.
2. **Narrow the formats** to DOCX, PDF with a text layer, MD, TXT; refuse images/scanned PDFs with a clear message; OCR behind a configuration flag.
3. **One extractor producing structured Markdown** (DOCX in body order with numbering, headings and tables in place; layout-aware PDF). Remove the duplicates.
4. **Separate the frame, keep the substance**: repeated headers/footers, national motto/slogan, signatures, recipients, approval and revision tables go into metadata.
5. **Recognize the document type and branch the chunking** (ISO, Article/Clause, Markdown, prose).
6. **Procedure tables**: each row (step) becomes a content unit with the column headers.
7. **Fix the chunker**: a tokenizer matching the model, chunks carrying the heading path, a parent chunk limit, merging small sections.
8. **Extract metadata from content**: document code, issue number, effective date, department.
9. **Dedup by version lifecycle**: never drop a new version of the same document automatically; only warn about duplicates between different documents.
10. **(Optional) Contextual retrieval** after items 3–7 are done.

## 6. Relation to V2

PRD-V2 and V2-09 already settled part of this: PDF/DOCX/MD/TXT formats, image OCR out of scope, duplicates only by SHA-256 within a workspace, keeping page numbers and section titles, no `tiktoken` cutting. `ingestion-service` will be replaced by `services/ai-service` (V2-09) and removed in V2-17. So items 3–9 should go into TECH-V2 (V2-03) and V2-09, not into the old `ingestion-service`.

V2-06's eval corpus (RESEARCH-02) is the English GitLab Handbook in Markdown: it cannot measure Vietnamese DOCX/PDF extraction quality. Item 1 needs a separate extraction corpus.

## 7. Not verified
- The pipeline was not run on real DOCX/PDF files; the DOCX numbering, table and PDF header/footer bugs are inferred from the code and known library behaviour.
- The risk of dedup wrongly blocking versions is not measured.
- The actual `OCR_LANGUAGE` in compose was not checked.

## Sources
- [QT.ISO.01 THADS Trà Vinh](https://thads.moj.gov.vn:443/travinh/noidung/thongbao/Lists/ThongBao/Attachments/185/QT%2001%20%20%20KSTT%20d%E1%BA%A1ng%20v%C4%83n%20b%E1%BA%A3n.pdf)
- [Document format under Decree 30 (luatvietnam)](https://luatvietnam.vn/hanh-chinh/the-thuc-van-ban-570-94255-article.html)
- [Layout of administrative document elements](https://thuviennhadat.vn/phap-luat/so-do-bo-tri-cac-thanh-phan-the-thuc-van-ban-hc-ap-dung-tu-0532020-640632.html)
- [ISO procedure flowcharts (MISA)](https://amis.misa.vn/133441/cach-ve-luu-do-quy-trinh-theo-iso/)
- [EPA QA/G-6](https://www.epa.gov/sites/default/files/2015-06/documents/g6-final.pdf)
- [GMP QMS-005](https://www.gmpsop.com/gmp_documents/qms-005/)
- [Docling + OpenSearch](https://opensearch.org/blog/building-powerful-rag-pipelines-with-docling-and-opensearch/)
- [Unstructured chunking](https://docs.unstructured.io/open-source/core-functionality/chunking)
- [RAGFlow (DataCamp)](https://www.datacamp.com/tutorial/ragflow)
- [Anthropic Contextual Retrieval](https://anthropic.com/news/contextual-retrieval)
- [MarkItDown office docs](https://www.mintlify.com/microsoft/markitdown/formats/office-documents)
