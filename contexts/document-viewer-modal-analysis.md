# Document Viewer Modal — Analysis & Issues

> Generated: 2026-05-19
> Scope: Only the Document Viewer Modal, chunk highlighting, and the full data flow from click → backend → render.

---

## 1. Complete File List

### Core Frontend Files

| # | File Path | Role |
|---|-----------|------|
| 1 | `frontend/web/components/documents/DocumentViewerModal.tsx` | Main modal component — renders markdown content, applies mark.js highlights, shows minimap sidebar |
| 2 | `frontend/web/components/chat/SourcesPanel.tsx` | Right-side accordion panel with "Xem chi tiết bản toàn văn" button that opens the modal |
| 3 | `frontend/web/components/chat/ChatContainer.tsx` | Parent container that mounts `<DocumentViewerModal />` in the component tree |
| 4 | `frontend/web/store/ui-store.ts` | Zustand store managing `activeDocumentViewer` state (isOpen, documentId, documentName, highlights[], chunks[]) |

### Types & Interfaces

| # | File Path | Role |
|---|-----------|------|
| 5 | `frontend/web/types/ai.ts` | Defines `ChunkRef` (chunkId, sectionTitle, excerpt, similarityScore), `SourceDocument`, `Source` |
| 6 | `frontend/web/types/document.ts` | Defines `Document`, `ProcessingStatus`, `ChunkingStrategy` |
| 7 | `frontend/web/interfaces/models/knowledge/chunk.model.ts` | Backend-facing Chunk model (chunkIndex, content, tokenCount, pageNumber, startCharIndex, endCharIndex) |

### Services & API Layer

| # | File Path | Role |
|---|-----------|------|
| 8 | `frontend/web/services/document.service.ts` | `getDocumentContent()` — calls `api.documents.getContent()` |
| 9 | `frontend/web/lib/api.ts` | Centralized API client. `api.documents.getContent()` (line 931) fetches `/api/v1/documents/{id}/content`. `mapBackendSourceToFrontend()` (line 190) maps backend chunk data to frontend `ChunkRef` |

### Styling

| # | File Path | Role |
|---|-----------|------|
| 10 | `frontend/web/app/globals.css` | CSS for `mark.chunk-highlight` (lines 144–170) — amber/yellow background with left border, light/dark mode variants, `.prose` override |

### Backend Files

| # | File Path | Role |
|---|-----------|------|
| 11 | `services/knowledge-service/.../controller/DocumentController.java` | `GET /{documentId}/content` (line 245) — returns raw extracted text |
| 12 | `services/knowledge-service/.../service/DocumentManagementService.java` | `getExtractedText()` (line 328) — reads `extractedText` from Document or DocumentVersion entity |
| 13 | `services/knowledge-service/.../service/DocumentParsingService.java` | Parses PDF/DOCX/TXT/etc → raw text using Apache Tika + PDFBox |
| 14 | `services/knowledge-service/.../service/TextChunkingService.java` | Splits extracted text into chunks using RECURSIVE/SENTENCE/FIXED_SIZE/SEMANTIC strategies |
| 15 | `services/knowledge-service/.../entity/Document.java` | Entity with `extractedText` field (line 55–56, column `text` type) |
| 16 | `services/knowledge-service/.../entity/DocumentVersion.java` | Entity with `extractedText` field (line 37–38) |
| 17 | `services/ai-qa-service/src/api/routes/chat.py` | `build_sources()` (line 123) — creates `ChunkRef` with `excerpt` from `chunk.content[:200] + "..."` |
| 18 | `services/ai-qa-service/src/models/retrieval.py` | `RetrievalChunk` model — `content: str` is the full chunk text from vector store |

---

## 2. Data Flow: Click → Backend → Render

### Step 1: User clicks "Xem chi tiết bản toàn văn"
**File:** `SourcesPanel.tsx:149`
```
onClick={() => handleViewDocument(source)}
```

### Step 2: Build highlights array & open modal
**File:** `SourcesPanel.tsx:39–42`
```typescript
const handleViewDocument = (source: SourceDocument) => {
    const highlights = source.chunks.map((c) => c.excerpt);
    openDocumentViewer(source.documentId, source.documentName, highlights, source.chunks);
};
```
- `highlights` = array of excerpt strings (each max ~200 chars + "...")
- `chunks` = array of `ChunkRef` objects with full metadata

### Step 3: Zustand store updates
**File:** `ui-store.ts:66–75`
```typescript
openDocumentViewer: (documentId, documentName, highlights, chunks) =>
    set({
        activeDocumentViewer: {
            isOpen: true,
            documentId,
            documentName,
            highlights,
            chunks: chunks || [],
        },
    }),
```

### Step 4: DocumentViewerModal mounts
**File:** `DocumentViewerModal.tsx:47–48`
```typescript
const { activeDocumentViewer, closeDocumentViewer } = useUIStore();
const { isOpen, documentId, documentName, highlights, chunks } = activeDocumentViewer;
```
- `isOpen === true` → modal renders (line 132: `if (!isOpen) return null`)

### Step 5: Fetch full document content from backend
**File:** `DocumentViewerModal.tsx:60–84`
```typescript
useEffect(() => {
    if (!isOpen || !documentId) return;
    const fetchContent = async () => {
        const text = await documentService.getDocumentContent(documentId);
        setContent(text);
        setCleanedContent(cleanMarkdown(text));
    };
    fetchContent();
}, [isOpen, documentId]);
```

**Call chain:**
```
documentService.getDocumentContent(documentId)
  → api.documents.getContent(documentId, version)       [api.ts:931]
    → GET http://localhost:3001/api/v1/documents/{id}/content
      → API Gateway (NestJS) proxies to Knowledge Service (Spring Boot :8083)
```

### Step 6: Backend handles the request

**DocumentController.java:245–252**
```java
@GetMapping("/{documentId}/content")
public ResponseEntity<String> getDocumentContent(@PathVariable UUID documentId,
                                                  @RequestParam(required = false) Integer version) {
    String content = documentManagementService.getExtractedText(documentId, version);
    return ResponseEntity.ok(content);  // Returns RAW TEXT, not wrapped
}
```

**DocumentManagementService.java:328–345**
```java
public String getExtractedText(UUID documentId, Integer versionNumber) {
    if (versionNumber != null) {
        // Read from DocumentVersion entity
        DocumentVersion version = versionRepository.findByDocumentIdAndVersionNumber(...);
        return version.getExtractedText() != null ? version.getExtractedText() : "";
    } else {
        // Read from Document entity, fallback to current version
        Document document = documentRepository.findById(documentId)...;
        if (document.getExtractedText() != null && !document.getExtractedText().isBlank()) {
            return document.getExtractedText();
        }
        // Fallback to version's text
        return versionRepository.findByDocumentIdAndVersionNumber(documentId, currentVer)
                .map(v -> v.getExtractedText() != null ? v.getExtractedText() : "")
                .orElse("");
    }
}
```

### Step 7: Frontend receives & processes response
**File:** `api.ts:931–937`
```typescript
getContent: async (documentId, version) => {
    const res = await this.client.get(`/api/v1/documents/${documentId}/content`, { params: { version } });
    return typeof res.data === 'string' ? res.data : res.data?.content ?? '';
};
```
- Backend returns raw string → `res.data` is string → returned directly
- Fallback handles wrapped `{ content: "..." }` format (used by version content endpoint)

### Step 8: Clean markdown & render
**File:** `DocumentViewerModal.tsx:15–44`
```typescript
function cleanMarkdown(raw: string): string {
    // Remove HTML comments: <!-- ... -->
    // Remove Hugo block shortcodes: {{% ... %}}
    // Remove Hugo inline shortcodes: {{< ... >}}
    // Remove frontmatter: --- ... ---
    // Collapse excessive blank lines: \n{3,} → \n\n
    return text.trim();
}
```

### Step 9: Apply mark.js highlights
**File:** `DocumentViewerModal.tsx:87–111`
```typescript
useEffect(() => {
    const markInstance = new Mark(markdownRef.current);
    markInstance.unmark();

    const cleanExcerpts = (chunks && chunks.length > 0)
        ? chunks.map(c => c.excerpt)
        : highlights;

    cleanExcerpts.forEach((excerpt, index) => {
        const clean = excerpt.replace(/\.{3}$/, '').trim();  // Strip trailing "..."
        if (clean.length < 10) return;

        markInstance.mark(clean, {
            className: 'chunk-highlight',
            separateWordSearch: false,
            accuracy: 'partially',   // ← PROBLEM: matches partial text
            element: 'mark',
            each: (element) => {
                element.setAttribute('data-highlight-index', String(index));
            },
        });
    });
}, [cleanedContent, chunks, highlights]);
```

### Step 10: Render content
**File:** `DocumentViewerModal.tsx:181–189`
```tsx
<div ref={markdownRef} className="prose prose-sm max-w-none dark:prose-invert">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {cleanedContent}
    </ReactMarkdown>
</div>
```
- If no full text available → falls back to `renderChunksView()` (line 193–284)

### Step 11: Compute minimap positions
**File:** `DocumentViewerModal.tsx:143–177`
```typescript
const getMinimapPositions = (): { percent: number; label: string; index: number }[] => {
    const marks = markdownRef.current.querySelectorAll('mark.chunk-highlight');
    // Computes percentage position of each mark within the scrollable container
};

const minimapPositions = hasFullText ? getMinimapPositions() : [];
```

---

## 3. Chunk Text Content — Full Pipeline

This section describes how the `excerpt` / `content` text of a chunk is created, from the original document file to what the frontend receives.

### 3.1 Source: Original File Upload

**Supported formats:** PDF, DOCX, DOC, XLSX, XLS, TXT, PNG, JPG, JPEG, MD

**File:** `DocumentParsingService.java`

| File Type | Parser | Method |
|-----------|--------|--------|
| PDF | Apache PDFBox `PDFTextStripper` | `parsePdf()` — line 43–51 |
| DOCX/DOC | Apache Tika `tika.parseToString()` | `parseWord()` — line 54–60 |
| XLSX/XLS | Apache Tika `tika.parseToString()` | `parseExcel()` — line 63–69 |
| TXT | Raw UTF-8 read | `parseText()` — line 72–76 |
| PNG/JPG | Apache Tika (OCR-ready) | `parseImage()` — line 79–86 |

### 3.2 Extracted Text Storage

**Entity:** `Document.java:55–56`
```java
@Column(name = "extracted_text", columnDefinition = "text")
private String extractedText;
```

**Entity:** `DocumentVersion.java:37–38`
```java
@Column(name = "extracted_text", columnDefinition = "text")
private String extractedText;
```

**What `extractedText` contains:**
- Raw text extracted from the file by the parser
- **NO cleaning or normalization** is applied at this stage
- Preserves original whitespace, newlines, page breaks, headers/footers (depending on parser)
- For PDF: PDFBox `PDFTextStripper` extracts text in reading order, but may include:
  - Page break characters
  - Repeated headers/footers on each page
  - Table text in linearized (non-tabular) format
  - OCR artifacts if the PDF is scanned
- For DOCX: Tika extracts text including:
  - Paragraph breaks as newlines
  - May include metadata, footnotes, endnotes
  - Table cells concatenated with spaces/newlines
- **No markdown conversion** — the text is plain text, not markdown
- Stored as-is in PostgreSQL `text` column

### 3.3 Chunking Process

**File:** `TextChunkingService.java`

**Input:** The raw `extractedText` string from the document entity

**Strategies (default: SENTENCE, configured in `application.properties`):**
```properties
knowledge.chunking.default-strategy=RECURSIVE
knowledge.chunking.default-chunk-size=1000
knowledge.chunking.default-overlap=200
```

**Chunking strategies:**

| Strategy | Method | How it works |
|----------|--------|--------------|
| RECURSIVE | `recursiveCharacterSplit()` (line 35–77) | Splits by separators in priority order: `\n\n` → `\n` → `. ` → `! ` → `? ` → `; ` → `, ` → ` `. Tries to find a separator near the chunk boundary. |
| SENTENCE | `sentenceChunk()` (line 106–145) | Splits by sentence boundaries (`[.!?]\s+` regex). Accumulates sentences until `targetSize` is reached. |
| FIXED_SIZE | `fixedSizeChunk()` (line 79–103) | Hard split at `chunkSize` characters. No semantic awareness. |
| SEMANTIC | `semanticChunk()` (line 148–192) | Splits by paragraphs (`\n\n`), merges small paragraphs together until `targetSize`. |

**Chunk record structure:**
```java
public record Chunk(int index, int startChar, int endChar, String text) {}
```

**What each chunk's `text` field contains:**
- A substring of the original `extractedText`
- **Trimmed** (`.trim()` called on each chunk)
- **No further cleaning** — retains all original formatting artifacts
- May contain:
  - Multiple newlines (`\n\n\n`)
  - Leading/trailing whitespace (before trim)
  - Page break artifacts
  - Header/footer repetitions
  - Table text in linearized format
  - Mixed content from different document sections

**Overlap handling:**
- Chunks overlap by `chunkOverlap` characters (default: 200)
- Overlap text is copied from the end of the previous chunk
- This means the same text appears in multiple chunks

### 3.4 Embedding & Vector Storage

Chunks are sent to the Python ingestion service via RabbitMQ event (`DocumentUploadedEvent`).

The ingestion service:
1. Parses the file (may re-extract text)
2. Chunks the text
3. Generates embeddings via embedding API
4. Stores chunks + embeddings in vector store (pgvector or similar)

**The `content` field stored in the vector store:**
- Same as the chunk `text` from `TextChunkingService`
- No additional cleaning or normalization
- Raw substring of the original extracted text

### 3.5 Retrieval & Excerpt Creation

**File:** `chat.py:123–154` — `build_sources()`

```python
async def build_sources(chunks: List[RetrievalChunk]) -> List[SourceDocument]:
    for chunk in chunks[:10]:
        excerpt = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content

        chunk_ref = ChunkRef(
            chunk_id=chunk.id,
            section_title=chunk.section_title,
            excerpt=excerpt,
            similarity_score=chunk.similarity_score,
        )
```

**What `excerpt` contains:**
- First 200 characters of the chunk's `content`
- Appended with `"..."` if truncated
- **No cleaning** — retains all artifacts from the original text
- May start/end mid-word, mid-sentence
- May contain newlines, special characters, table artifacts

### 3.6 Frontend Processing

**File:** `api.ts:190–217` — `mapBackendSourceToFrontend()`
```typescript
function mapBackendSourceToFrontend(s: any): SourceDocument {
    const chunks = rawChunks.map((c: any) => ({
        chunkId: c.chunk_id ?? c.chunkId ?? c.id ?? '',
        sectionTitle: c.section_title ?? c.sectionTitle ?? undefined,
        excerpt: c.excerpt ?? '',
        similarityScore: c.similarity_score ?? c.similarityScore ?? 0,
    }));
    // Handles both snake_case (backend) and camelCase
}
```

**File:** `DocumentViewerModal.tsx:97–98` — Highlight preparation
```typescript
const clean = excerpt.replace(/\.{3}$/, '').trim();  // Only strips trailing "..."
```

### 3.7 Summary: What the excerpt field actually contains

```
Original File (PDF/DOCX/etc)
    ↓
[Parser: PDFBox/Tika] → extractedText (raw, uncleaned, with artifacts)
    ↓
[TextChunkingService] → chunk.text (substring, trimmed, with overlap)
    ↓
[Ingestion Service] → vector store content (same as chunk.text)
    ↓
[Hybrid Search] → RetrievalChunk.content (from vector store)
    ↓
[build_sources()] → excerpt = content[:200] + "..." (truncated, uncleaned)
    ↓
[Frontend mapBackendSourceToFrontend] → ChunkRef.excerpt (snake→camel mapping)
    ↓
[DocumentViewerModal] → clean = excerpt.replace(/\.{3}$/, '').trim()
    ↓
[mark.js] → searches for `clean` in rendered markdown
```

**Key problems in this pipeline:**
1. **No text normalization** at any stage — whitespace, newlines, artifacts are preserved
2. **Excerpt is truncated** at 200 chars, often mid-sentence
3. **Excerpt may not match** the full document text due to:
   - Markdown rendering changes whitespace/formatting
   - `cleanMarkdown()` strips Hugo shortcodes, comments, frontmatter — but the excerpt was created from raw text that may contain these
   - Trailing `"..."` stripping is naive — doesn't handle Unicode ellipsis (`…`) or leading ellipsis
4. **Overlap means duplicate content** — the same text appears in multiple chunks, causing mark.js to highlight multiple times

---

## 4. Identified Issues

### Issue 1: `accuracy: 'partially'` causes false positive highlights
**File:** `DocumentViewerModal.tsx:104`
**Severity:** HIGH

`accuracy: 'partially'` means mark.js will match text that partially contains the search term. For excerpts like `"điều khoản lao động"` (after stripping `...`), this will also match `"điều khoản lao động mới"`, `"điều khoản lao động cũ"`, etc.

**Fix:** Use `accuracy: 'exactly'` or implement a custom accuracy function.

### Issue 2: Excerpt truncation causes match failures
**File:** `chat.py:131`
**Severity:** HIGH

Excerpts are truncated to 200 chars, often mid-sentence. When mark.js tries to find this partial text in the full document, it may:
- Match multiple locations (ambiguous)
- Not match at all (if the truncation point is at a unique boundary)
- Match the wrong occurrence

### Issue 3: Race condition — minimap positions computed before marks exist
**File:** `DocumentViewerModal.tsx:87–111` vs line 177
**Severity:** MEDIUM

- `useEffect` (line 87) runs **after** render → creates marks in DOM
- `getMinimapPositions()` (line 177) runs **during** render → reads marks from DOM
- **Result:** First render after content loads → marks don't exist yet → `minimapPositions = []` → minimap is empty. Requires a re-render to show pins.

### Issue 4: Markdown rendering changes text → excerpt doesn't match
**File:** `DocumentViewerModal.tsx:186–188`
**Severity:** MEDIUM

`ReactMarkdown` converts markdown syntax to HTML:
- `**bold**` → `<strong>bold</strong>`
- `# Heading` → `<h1>Heading</h1>`
- Multiple spaces → single space
- Newlines → `<br>` or `<p>`

The excerpt was created from **raw extracted text** (not markdown). When mark.js searches for the excerpt in the **rendered HTML**, the text may differ due to markdown transformations.

### Issue 5: `getMinimapPositions()` not memoized — performance issue
**File:** `DocumentViewerModal.tsx:143`
**Severity:** LOW

Called on every render, reads from DOM via `getBoundingClientRect()`, forcing layout recalculation. Should be wrapped in `useMemo` or computed via `useEffect` + state.

### Issue 6: Overlapping marks → `data-highlight-index` is unreliable
**File:** `DocumentViewerModal.tsx:107`
**Severity:** LOW

When excerpts overlap (due to chunk overlap), mark.js may create overlapping `<mark>` elements. The `data-highlight-index` attribute may be overwritten, causing the minimap and scroll-to-highlight features to point to the wrong chunk.

### Issue 7: `cleanMarkdown()` strips content that excerpts may reference
**File:** `DocumentViewerModal.tsx:15–44`
**Severity:** LOW

`cleanMarkdown()` removes Hugo shortcodes, HTML comments, and frontmatter. If the original extracted text contains these and the excerpt includes them, mark.js will fail to find the excerpt in the cleaned content.

### Issue 8: No cleanup of mark.js instance on unmount
**File:** `DocumentViewerModal.tsx:87–111`
**Severity:** LOW

If the component unmounts while marks are present, there is no explicit cleanup. Minor concern since the modal DOM is removed, but worth noting for memory safety.

---

## 5. Recommended Fixes (Priority Order)

1. **Change `accuracy` to `'exactly'`** — prevents false positive highlights
2. **Use full chunk content instead of truncated excerpt** for mark.js search — increases match accuracy
3. **Move `getMinimapPositions()` to `useEffect` + state** — fixes race condition
4. **Normalize text before chunking** — clean whitespace, remove artifacts at the extraction stage
5. **Add text normalization in `cleanMarkdown()`** — ensure consistency between excerpt and rendered content
6. **Memoize `getMinimapPositions()`** — improve performance
7. **Handle overlapping marks** — deduplicate or merge overlapping highlights
