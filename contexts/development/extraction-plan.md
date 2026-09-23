---
title: Extraction Service Implementation Plan
description: Detailed implementation plan for Poliwise ingestion-service (Python FastAPI)
type: development
version: 1.3
---

# Extraction Service Implementation Plan

## Purpose

This document provides the **complete technical implementation plan** for building the ingestion-service (Python FastAPI) that extracts, chunks, and embeds documents for the Poliwise AI platform.

## When to Use

- Implementing the ingestion-service from scratch
- Understanding document processing pipeline flow
- Reference for architecture decisions and technical specifications
- Onboarding developers to the ingestion layer

---

## Core Architecture

### Pipeline Flow

The ingestion pipeline uses a **two-phase** approach: AI suggests metadata → user reviews/confirms → ingestion executes.

```
PHASE 1: UPLOAD & METADATA SUGGESTION (Cross-Service Synchronous, < 5s)
════════════════════════════════════════════════════════════════════

User uploads file → Gateway → Knowledge-Service (Java)
  1. Java: Save uploaded file to MinIO → get `file_key`.
  2. Java: Fetch DB Context (Active Categories + Top 20 Tags).
  3. Java: Sync HTTP POST to Ingestion-Service (Python): 
     `POST /api/v1/metadata/suggest` with `{file_key, bucket_name, categories, top_tags}`.
  4. Python: Download file from MinIO → Extract first 4000 chars (PyMuPDF) → Run AI prompt.
  5. Python: Return metadata JSON to Java.
  6. Java: Forward JSON to UI → User reviews & confirms.

PHASE 2: PERSISTENCE & INGESTION LAUNCH (async via RabbitMQ)
═══════════════════════════════════════════

Knowledge Service
  1. Create `knowledge.documents`, `knowledge.document_versions`, `knowledge.processing_jobs` entities.
  2. Create 1-1 `metadata.document_metadata` mapping `category_id`, `department_id`, etc.
  3. Resolve the tag list: create missing tags in `metadata.tags` and map via `metadata.document_tags`.
  4. Publish `ingestion.requested` to RabbitMQ with `document_id` and raw metadata.

└────────────────────────┬──────────────────────────────────────┘
                         │ ingestion.requested (RabbitMQ)
                         ▼

Ingestion Service (Python FastAPI :8088)
  ↓ EXTRACTION LAYER
    • Download file from MinIO using file_key + bucket_name
    • Route to format-specific extractor
    • Extract raw text + structural metadata
    • Return ExtractedDocument with text + metadata

  ↓ STANDARDIZATION LAYER
    • Unicode NFC, whitespace cleanup
    • Document heading detection

  ↓ CHUNKING LAYER
    • Parent-child chunking with metadata assignment from event payload

  ↓ EMBEDDING LAYER
    • BGE-M3 dense (1024-dim) + sparse BM25 via LitServe

  ↓ STORAGE LAYER
    • Save chunks to knowledge.chunks with access control tags
    • Update knowledge.documents (extracted_text, page_count, etc.)
    • Update knowledge.processing_jobs (status = COMPLETED)

  ↓ PUBLISH `document.uploaded` to RabbitMQ
```

### Project Structure

```
services/ingestion-service/
├── Dockerfile
├── pyproject.toml
├── .env.example
├── src/
│   ├── main.py                          # FastAPI app entry point
│   ├── config/
│   │   ├── settings.py                  # Pydantic settings (MinIO, DB, RabbitMQ)
│   │   └── rabbitmq.py                  # RabbitMQ connection + exchange/queue setup
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py                # GET /health
│   │   │   └── ingest.py                # POST /ingest, GET /ingest/{job_id}/status
│   ├── services/
│   │   ├── extractor.py                 # Extraction orchestrator + format-specific extractors
│   │   ├── standardizer.py              # DocumentPolicyStandardizer
│   │   ├── chunker.py                   # Parent-child chunker
│   │   ├── embedding_service.py         # BGE-M3 via LitServe
│   │   ├── minio_service.py             # MinIO download client
│   │   └── processing_job_service.py    # Update job status in DB
│   ├── models/
│   │   ├── extraction.py                # Pydantic/dataclass models for extraction output
│   │   ├── chunk.py                     # SQLAlchemy chunk model
│   │   ├── document.py                  # SQLAlchemy document model
│   │   ├── document_version.py          # SQLAlchemy document_version model
│   │   └── processing_job.py            # SQLAlchemy job model
│   ├── db/
│   │   ├── session.py                   # asyncpg engine + session factory
│   │   └── repositories/
│   │       ├── chunk_repo.py
│   │       ├── document_repo.py
│   │       ├── version_repo.py
│   │       └── job_repo.py
│   └── events/
│       ├── consumer.py                  # Consume ingestion.requested, document.deleted
│       └── publisher.py                 # Publish document.uploaded
└── tests/
```

---

## Database Schema Alignment

**CRITICAL PRINCIPLE (Single Source of Truth):**
Do NOT rely on table structures written directly in implementation plans. You **MUST** read the definitive database schema models directly from the database context folder to avoid hallucination or outdated DB structures.

### Reference Schemas
When implementing SQLAlchemy models, queries, or inserts, **always refer to these files**:

- **[Knowledge Schema (`contexts/database/tables/knowledge.md`)](file:///c:/Users/Tien/university/TTCS/do_an_cuoi_ky/Poliwise/contexts/database/tables/knowledge.md)**
  - `knowledge.documents` (Written globally by Phase 1, updated tracking in Phase 2)
  - `knowledge.document_versions` (Phase 1 establishes it; Phase 2 adds `file_checksum`, `content_hash`, `similarity_to_previous`)
  - `knowledge.chunks` (Phase 2 inserts massive chunking/embedding data)
  - `knowledge.processing_jobs` (Phase 1 creates; Phase 2 updates percent/logs)
- **[Metadata Schema (`contexts/database/tables/metadata.md`)](file:///c:/Users/Tien/university/TTCS/do_an_cuoi_ky/Poliwise/contexts/database/tables/metadata.md)**
  - `metadata.document_metadata` (Phase 1 writes mapped category, title, description)
  - `metadata.categories` (Phase 1 uses `slug` + `is_active` as DB-Context list)
  - `metadata.tags` / `metadata.document_tags` (Phase 1 fetches top 20 usages, inserts novel tags)

### Schema Requirements

- **Soft Delete**: All tables have `deleted_at` for soft deletion
- **Timestamps**: All tables have `created_at`, `updated_at` (except join tables)
- **UUID Primary Keys**: All IDs are UUIDs
- **Foreign Keys**: Proper foreign key constraints between related tables

---

## Environment Configuration

```env
# Server
HOST=0.0.0.0
PORT=8088
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql+asyncpg://poliwise:poliwise_secure_password@postgres:5432/poliwise
DATABASE_SCHEMA=knowledge

# RabbitMQ
RABBITMQ_URL=amqp://poliwise:poliwise_secure_password@rabbitmq:5672
RABBITMQ_EXCHANGE=poliwise.events

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# LitServe
EMBEDDING_URL=http://localhost:8001
RERANKER_URL=http://localhost:8002

# LLM API (Groq for Metadata Suggestion)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile  # Or llama-3.1-8b-instant for speed

# Chunking
CHUNKING_PARENT_SIZE=1500
CHUNKING_CHILD_SIZE=400
CHUNKING_CHILD_OVERLAP=80
CHUNKING_DEFAULT_STRATEGY=parent_child

# OCR Fallback
OCR_FALLBACK_MIN_TEXT_LENGTH=50
OCR_FALLBACK_MIN_IMAGE_COUNT=1
OCR_LANGUAGE=eng

# Redundancy Detection
SIMILARITY_THRESHOLD=0.90
SIMILARITY_THRESHOLD_DIGITAL=0.98
SIMILARITY_THRESHOLD_OCR=0.90
```

---

## Dependencies

```toml
[project]
name = "poliwise-ingestion"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # FastAPI & Web
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    
    # Database
    "asyncpg>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "pgvector>=0.3.0",
    
    # Message Queue
    "aio-pika>=9.4.0",
    
    # Configuration
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    
    # Document Extraction (local libraries only — no AI model required)
    "PyMuPDF>=1.23.0",        # PDF — text extraction + OCR fallback
    "python-docx>=1.1.0",     # DOCX — heading detection, tables
    "openpyxl>=3.1.0",        # XLSX — sheet to markdown
    "pytesseract>=0.3.10",    # OCR for scanned images/PDFs
    "Pillow>=10.0.0",         # Image processing
    "ruamel.yaml>=0.18.0",    # Hugo frontmatter parsing (preserves comments)
    
    # NLP, LLM & Tokenization
    "groq>=0.11.0",           # Fast LLM inference for metadata suggestion
    "instructor>=1.6.0",      # Structured JSON output from LLMs
    "transformers>=4.38.0",   # Accurate token counting for BGE-M3
    "underthesea>=6.8.0",     # Vietnamese NLP
    
    # HTTP Client
    "httpx>=0.27.0",
    
    # Object Storage
    "minio>=7.2.0",
    
    # Observability
    "structlog>=24.1.0",
    "prometheus-client>=0.21.0",
    "starlette-exporter>=0.24.0",
]
```

---

## Core Services Implementation

### 1. Extraction Orchestrator

**Pattern**: Registry/Strategy pattern for format-specific extractors

```python
class DocumentExtractor(ABC):
    @abstractmethod
    async def extract(self, file_bytes: bytes, document_id: UUID, version_id: UUID) -> ExtractedDocument:
        ...

class ExtractionOrchestrator:
    def __init__(self):
        self._extractors: dict[str, DocumentExtractor] = {}
    
    def register(self, extractor: DocumentExtractor):
        for ext in extractor.supported_extensions():
            self._extractors[ext] = extractor
    
    async def extract(self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID) -> ExtractedDocument:
        ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
        extractor = self._extractors.get(ext)
        if not extractor:
            raise ValueError(f"No extractor for extension: .{ext}")
        return await extractor.extract(file_bytes, document_id, version_id)
```

### 2. Supported Extractors

| Format | Extension | Library | Key Features |
|--------|-----------|---------|--------------|
| Markdown | `.md` | Built-in | UTF-8 decode, Hugo frontmatter parsing, heading detection (`#`, `##`, etc.) |
| Text | `.txt` | Built-in | UTF-8 decode, basic structure preservation |
| PDF | `.pdf` | PyMuPDF (`fitz`) | Text extraction, page-level metadata, image detection, OCR fallback |
| Word | `.docx` | `python-docx` | Heading detection, paragraph structure, table extraction |
| Excel | `.xlsx` | `openpyxl` | Sheet iteration, cell-to-markdown conversion |
| Images | `.png`, `.jpg`, etc. | `pytesseract` + `Pillow` | OCR with Vietnamese language support |

**Design Principle**: All extractors are **local library-based** — no external AI model dependencies for extraction. This ensures:
- **Stability**: No GPU free-tier sleep, no tunnel drops, no API rate limits
- **Speed**: 200ms-2s/file on CPU-only
- **Zero cost**: No token usage during extraction
- **Predictability**: Deterministic output for testing and reproducibility

**Optional Plugin — MinerU Extractor (Future)**:
When dealing with complex scanned PDFs (multi-column layouts, complex tables, image-heavy documents), an optional `MinerUExtractor` can be added using the `opendatalab/MinerU2.5` model. This should be implemented as an opt-in plugin, not a core dependency:

```python
class MinerUExtractor(DocumentExtractor):
    """Optional extractor for complex/scanned PDFs using MinerU model.
    Requires: GPU access, MinerU API endpoint configured.
    Falls back to PyMuPDFExtractor if unavailable."""

    def supported_extensions(self):
        return [".pdf"]  # Only activated when MINERU_ENABLED=true

    async def extract(self, file_bytes, document_id, version_id):
        if not settings.mineru_enabled:
            raise MinerUNotAvailableError("Falling back to PyMuPDF")
        # Call MinerU API endpoint (self-hosted or HF Space + tunnel)
        ...
```

**When to enable MinerU**:
- Bulk ingestion of scanned PDFs (not applicable to GitLab Handbook — all `.md`)
- Complex table/column layouts that PyMuPDF fails to parse
- When a stable GPU endpoint is available (not free-tier)

**For now**: Stick with libraries only. GitLab Handbook is 100% `.md` files. PDF/DOCX demo files work fine with PyMuPDF + python-docx.

### 2b. AI Metadata Suggestion (Phase 1 — Cross-Service Sync)

To keep extraction logic centralized (DRY), `knowledge-service` (Java) delegates the heavy lifting of parsing and LLM prompts to `ingestion-service` (Python) via a synchronous HTTP call. This avoids running bulky Apache Tika parsing in Java just to preview 4000 characters.

**Execution Flow:**
1. **Java** retrieves available context from DB:
   - `categories`: `SELECT slug FROM metadata.categories WHERE is_active = true`
   - `top_tags`: `SELECT name FROM metadata.tags ORDER BY usage_count DESC LIMIT 20`
2. **Java** sends a synchronous REST request to Python: 
   `POST /api/v1/metadata/suggest`
   Payload: `{ "file_key": "...", "bucket_name": "...", "available_categories": [...], "top_tags": [...] }`.
3. **Python** connects to MinIO safely, downloads the file stream using `file_key`, and uses native PyMuPDF/docx to perfectly extract the first 4000 text characters.
4. **Python** injects the text and the Java-provided context into the AI Prompt and returns the following JSON fields:

| Field | Source / Target | Notes |
|-------|-----------------|-------|
| `category_slug` | Maps to `metadata.document_metadata.category_id` | AI MUST choose this from the injected context array. |
| `title` | `metadata.document_metadata.title` | Extract from first heading or summarize. |
| `description` | `metadata.document_metadata.description` | AI summarizes first 2000 chars into 1 sentence. |
| `tags` | Array of strings | Prioritizes reusing `top_tags`. UI creates new rows in `metadata.tags` if missing. |

**AI prompt pattern (Constructed in Python, lightweight < 500 tokens):**

```text
You are a document classifier for a policy platform. Given the first 4000 characters of a document, return ONLY a JSON object evaluating its metadata.

Constraints:
1. "category_slug" MUST be chosen from this exact list: [{available_categories}]
2. For "tags", generate 3-5 keywords. Prioritize reusing these existing tags if relevant: [{top_tags}]. Only invent new tags if absolutely necessary.

{
  "category_slug": "chosen-slug",
  "title": "extracted title or null",
  "description": "one-sentence summary or null",
  "tags": ["keyword1", "keyword2"],
  "language": "en or vi",
  "is_policy": true/false
}

Document content:
---
{first_4000_chars}
---
```

**Fallback behavior:** If Python AI endpoint is unavailable or times out (>5s), Java should catch the exception and return an empty framework to the UI for user manual override.

### 2c. GitLab Handbook Batch Ingestion (Markdown Processing)

When bulk-ingesting `.md` files from the GitLab Handbook repository, the flow skips Phase 1 (no user to review) and uses **deterministic extraction** tailored for Markdown properties:

1. **`domain`** — derive from path: `content/handbook/<domain>/...` → first segment after `handbook/`
2. **`content_quality`** — `REDIRECT` if frontmatter contains `redirect_to`, `LOW` if < 500 bytes after frontmatter removal, otherwise `HIGH`
3. **`is_current = TRUE`** — mark this version as active, set `FALSE` on previous versions
4. **Parse frontmatter** — merge all frontmatter keys into `knowledge.chunks.metadata` JSONB
5. **Shortcode Cleanup** — Remove or process Hugo/Kramdown shortcodes (e.g., `{{% alert %}}`, `{{< include >}}`) to prevent semantic noise during embedding.

### 3. Vietnamese Standardizer

Detects Vietnamese document structure:

```python
class DocumentPolicyStandardizer:
    # Supports both English and Vietnamese Enterprise Policies
    HEADING_PATTERNS = [
        (r"^(PHẦN|Phần|PART|Part)\s+([IVXLCDM]+|\d+)\s*[:\-]?\s*(.*)$", 1),
        (r"^(CHƯƠNG|Chương|CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\s*[:\-]?\s*(.*)$", 2),
        (r"^(MỤC|Mục|SECTION|Section)\s+(\d+)\s*[:\-]?\s*(.*)$", 3),
        (r"^(ĐIỀU|Điều|ARTICLE|Article)\s+(\d+)\s*[:\-]?\s*(.*)$", 4),
        (r"^(KHOẢN|Khoản|CLAUSE|Clause)\s+(\d+)\s*[:\-]?\s*(.*)$", 5),
        (r"^(ĐIỂM|Điểm|POINT|Point)\s+([a-zđ])\s*[:\-]?\s*(.*)$", 6),
    ]
    
    def normalize(self, raw_text: str) -> StructuredText:
        # Unicode normalization (NFC), whitespace cleanup
        # Strip Hugo/Markdown shortcodes if raw_text is from .md
        # Returns structured text with detected sections and headings
```

### 4. Parent-Child Chunker

**Strategy**: Hierarchical chunking for structured documents, recursive for unstructured

```python
class ParentChildChunker:
    def __init__(self, parent_size=1500, child_size=400, child_overlap=80):
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap
        # Uses BGE-M3 tokenizer for accurate VI/EN token counts
        from transformers import AutoTokenizer
        self.enc = AutoTokenizer.from_pretrained("BAAI/bge-m3", local_files_only=False)
    
    def chunk(self, structured_text, metadata: dict, is_markdown: bool = False) -> list[Chunk]:
        if is_markdown:
            return self._markdown_header_chunk(structured_text, metadata)
        elif structured_text.headings:
            return self._hierarchical_chunk(structured_text, metadata)
        else:
            return self._recursive_chunk(structured_text.normalized_text, metadata)

    def _markdown_header_chunk(self, structured_text, metadata: dict) -> list[Chunk]:
        # Preserve Markdown heading hierarchy (##, ###) directly
        pass
```

### 5. Embedding Service

**Integration**: LitServe for BGE-M3 embeddings

```python
class EmbeddingService:
    def __init__(self):
        self.embedding_url = settings.litserve_embedding_url
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.embedding_url}/predict",
                json={"inputs": texts},
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()["outputs"]
```

---

## Database Operations

### Chunk Bulk Insert with ACL Flattening

```python
async def bulk_insert(self, chunks: list[Chunk]):
    values = []
    for c in chunks:
        values.append({
            "document_id": c.document_id,
            "document_version_id": c.document_version_id,
            "chunk_type": c.chunk_type,
            "parent_chunk_id": str(c.parent_chunk_id) if c.parent_chunk_id else None,
            "content": c.content,
            "section_title": c.section_title,
            "section_level": c.section_level,
            "section_path": c.section_path,
            "chunk_index": c.chunk_index,
            "start_char_index": c.start_char_index,
            "end_char_index": c.end_char_index,
            "token_count": c.token_count,
            "embedding_vector": c.embedding_vector,
            "embedding_model": c.embedding_model,
            "embedding_dimension": c.embedding_dimension,
            "allowed_roles": c.allowed_roles,
            "allowed_departments": c.allowed_departments,
            "allowed_users": c.allowed_users,
            "access_level": c.access_level,
            "is_latest": True,
            "metadata": c.metadata,  # frontmatter extras → JSONB
        })

    await self.session.execute(text("""
        INSERT INTO knowledge.chunks (
            document_id, document_version_id, chunk_type, parent_chunk_id,
            content, section_title, section_level, section_path,
            chunk_index, start_char_index, end_char_index, token_count,
            embedding_vector, embedding_model, embedding_dimension,
            allowed_roles, allowed_departments, allowed_users, access_level,
            is_latest, metadata
        ) VALUES (
            :document_id, :document_version_id, :chunk_type, :parent_chunk_id,
            :content, :section_title, :section_level, :section_path,
            :chunk_index, :start_char_index, :end_char_index, :token_count,
            :embedding_vector, :embedding_model, :embedding_dimension,
            :allowed_roles, :allowed_departments, :allowed_users, :access_level,
            :is_latest, :metadata
        )
        ON CONFLICT (document_version_id, chunk_index, chunk_type) DO NOTHING
    """), values)
```

### Version Management

```sql
-- Mark previous chunks as not latest
UPDATE knowledge.chunks
SET is_latest = false
WHERE document_id = :document_id AND is_latest = true;

-- Mark previous versions as not current
UPDATE knowledge.document_versions
SET is_current = false
WHERE document_id = :document_id AND is_current = true;

-- Insert new version as current
INSERT INTO knowledge.document_versions (..., is_current) VALUES (..., true);

-- Insert new chunks with is_latest = true
INSERT INTO knowledge.chunks (..., is_latest) VALUES (..., true);
```

---

## Event-Driven Architecture

### Consumed Events

| Event | Queue | Action |
|-------|-------|--------|
| `ingestion.requested` | `ingestion.requests` | Start extraction pipeline |
| `document.deleted` | `ingestion.document.deleted` | Soft-delete chunks |

### Published Events

| Event | Routing Key | Purpose |
|-------|-------------|---------|
| `document.uploaded` | `document.uploaded` | Notify system document is ready |

### Event Payload Example

```json
{
  "event_type": "ingestion.requested",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0",
  "payload": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_version_id": "660e8400-e29b-41d4-a716-446655440001",
    "file_key": "documents/2024/01/550e8400.pdf",
    "bucket_name": "poliwise-documents",
    "job_id": "770e8400-e29b-41d4-a716-446655440002",
    "metadata": {
      "domain": "legal",              ← AI suggested, user confirmed (or modified)
      "content_quality": "HIGH",      ← Rule-based (redirect detection, size check)
      "title": "GitLab Acceptable Use Policy",
      "description": "Policy defining acceptable use of GitLab services",
      "tags": ["policy", "legal", "compliance"],
      "allowed_roles": ["USER", "MANAGER", "ADMIN"],
      "allowed_departments": ["dept-uuid-1", "dept-uuid-2"],
      "allowed_users": ["user-uuid-1"],
      "access_level": "PUBLIC",
      "department_id": "dept-uuid-1",
      "document_metadata": {
        "category_id": "cat-uuid",
        "effective_date": "2024-01-01",
        "expiry_date": "2025-01-01"
      }
    }
  }
}
```

---

## Error Handling & Resilience

### Retry Strategy

| Error Type | Retry | Max Attempts | Action |
|------------|-------|--------------|--------|
| Network timeout | Yes | 3 | Exponential backoff |
| Invalid file format | No | 0 | Fail immediately |
| Database constraint violation | No | 0 | Idempotent skip |
| RabbitMQ connection loss | Yes | Infinite | Reconnect with backoff |

### Circuit Breaker Configuration

```python
circuit_breaker = circuit(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=EmbeddingServiceError
)
```

### Dead Letter Queue

```python
await channel.declare_queue(
    "ingestion.requests.dlq",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "ingestion.requests"
    }
)
```

---

## Idempotency Guarantees

### Unique Constraint

```sql
ALTER TABLE knowledge.chunks
ADD CONSTRAINT uniq_chunk_per_version
UNIQUE (document_version_id, chunk_index, chunk_type);
```

### Idempotent Processing

```python
async def on_ingestion_requested(message):
    payload = json.loads(message.body.decode("utf-8"))
    job_id = payload.get("job_id")
    
    # Check if job already completed
    existing_job = await job_repo.get_by_id(job_id)
    if existing_job and existing_job.status in ["COMPLETED", "FAILED"]:
        await message.ack()  # Skip duplicate
        return
    
    # Process with idempotent bulk insert
    await chunk_repo.bulk_insert(chunks, on_conflict="DO NOTHING")
```

---

## Performance Tuning

### Default Settings

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| Workers | 2 | 2-4 | Concurrent document processing |
| Embedding batch size | 32 | 16-64 | GPU memory bound |
| Parent chunk size | 1500 tokens | 1000-2000 | Auto-merging threshold |
| Child chunk size | 400 tokens | 300-500 | Retrieval-optimized |
| Child overlap | 80 tokens | 50-150 | Context preservation |
| DB connection pool | 10 | 10-20 | SQLAlchemy engine |

### Throughput Expectations

- **CPU-only**: 10-20 documents/hour per worker
- **GPU (T4+)**: 50-100 documents/hour per worker
- **Embedding speed**: ~2000 tokens/sec (GPU), ~50 tokens/sec (CPU)

### Memory Management

- **Streaming extraction**: For large documents (>50MB)
- **Batch embedding**: Don't accumulate all chunks in memory
- **Database streaming**: Insert chunks as they're embedded

---

## Security & Compliance

### File Validation

```python
async def validate_file(file_bytes: bytes, mime_type: str) -> None:
    if len(file_bytes) > settings.max_file_size:
        raise FileTooLargeError(f"File size exceeds limit")
    
    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ...]
    if mime_type not in allowed_types:
        raise InvalidFileTypeError(f"Unsupported MIME type")
```

### Data Retention

- `processing_jobs`: Keep COMPLETED for 30 days (configurable)
- Chunk `is_latest`: Prevents old version data from being used
- Soft delete: Never hard delete for audit trail

---

## Monitoring & Observability

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `ingestion_total` | Counter | Total ingestion jobs by status |
| `ingestion_duration_seconds` | Histogram | Duration by pipeline stage |
| `chunks_created_total` | Counter | Chunks created by type |
| `embedding_latency_seconds` | Histogram | LitServe embedding latency |
| `minio_errors_total` | Counter | MinIO download errors |

### Health Checks

- `/health`: Overall health (all dependencies)
- `/health/live`: Liveness (process running)
- `/health/ready`: Readiness (can accept traffic)

### Structured Logging

```python
import structlog

logger = structlog.get_logger()
logger.info("processing.started", document_id=document_id, version_id=version_id)
logger.error("embedding.failed", document_id=document_id, error=str(e), exc_info=True)
```

---

## Testing Strategy

### Unit Tests

```
tests/
├── fixtures/
│   ├── sample_vietnamese_policy.pdf
│   ├── sample_hr_document.docx
│   ├── sample_timesheet.xlsx
│   ├── sample_policy.md
│   └── sample_scanned_image.png
├── test_extractors.py
├── test_standardizer.py
├── test_chunker.py
├── test_embedding_service.py
└── test_repositories.py
```

### Integration Tests

Test full pipeline with:
- Mock MinIO returning fixture files
- In-memory PostgreSQL with pgvector mock
- Mock RabbitMQ for event verification
- Test coverage ≥ 80% for extractor and chunker

---

## Implementation Checklist

### Phase 1: API Cross-Boundary Setup

**Knowledge Service (Java) Task:**
- [ ] **Enforce Boundaries:** Completely remove explicit internal `processDocument()` logic and `/{documentId}/process` API from Java.
- [ ] DB Context Query: Fetch active category slugs & top 20 used tag names.
- [ ] HTTP Client: Implement a Sync HTTP POST call to Ingestion Service's `/api/v1/metadata/suggest` endpoint passing `file_key`, `bucket_name` & contexts.
- [ ] Validation & DB Insert: On user UI confirm, resolve `category_slug` -> `category_id` (UUID). Insert records accurately across `knowledge` & `metadata` schemas according to definitive Database Definitions.
- [ ] Async Dispatch: Publish `ingestion.requested` RabbitMQ event payload with finalized UUIDs to trigger Phase 2.

**Ingestion Service (Python FastAPI) Task:**
- [ ] Endpoint Setup: Implement `POST /api/v1/metadata/suggest` accepting Pydantic schema model (`file_key`, DB context arrays).
- [ ] MinIO Tooling: Function to quickly download stream of `file_key` bytes.
- [ ] Extractor Core: Extract first 4000 chars natively (using PyMuPDF/Python-docx) directly from bytes.
- [ ] AI Engine Call: Feed exact categories logic into structured LLM output (instructor / json_schema). Return clean JSON to Java.

### Phase 2: Ingestion (Ingestion Service)
- [ ] All table/column names match `contexts/database/tables/*.md` exactly
- [ ] NO `summary` or `child_chunk_ids` columns in chunk model (use `parent_chunk_id` self-reference)
- [ ] NO `embedding_dimension` in document model (only on chunks)
- [ ] Unique constraint on `knowledge.chunks` (document_version_id, chunk_index, chunk_type)
- [ ] `content_tsv` TSVECTOR generated column — PostgreSQL auto-computes it, no need to set in code
- [ ] HNSW index on `knowledge.chunks.embedding_vector`
- [ ] GIN indexes on `allowed_roles`, `allowed_departments`, `allowed_users`, `content_tsv`
- [ ] Read `domain` + `content_quality` from event payload → write to `knowledge.documents`
- [ ] Set `is_current = true` on new version, `false` on all previous versions
- [ ] Query children via `WHERE parent_chunk_id = :parent_id` (not `child_chunk_ids` array)
- [ ] All extractors use local libraries only (no external AI model for extraction)
- [ ] Markdown extractor parses Hugo frontmatter → metadata JSONB
- [ ] PDF extractor uses PyMuPDF with OCR fallback
- [ ] MinerU extractor NOT a core dependency — opt-in plugin for future

### Phase 2b: Redundancy Detection (Hybrid Two-Layer)

The ingestion pipeline includes hybrid redundancy detection to handle both digital and OCR'd documents.

#### Detection Flow

```
Upload File
    │
    ▼
Layer 1: Compute file_checksum (SHA256)
         │
         ▼ query
    ┌─────────────┐ No match ──▶ Layer 2
    │ file_exists?│
    └─────────────┘
         │ match found
         ▼
    Link to existing version
    Skip ingestion, update reference
```

```
Layer 2: On new file (no file hash match)
         │
         ▼
    Extract text
         │
         ▼ query content_hash
    ┌──────────────────────┐ Match ──▶ Reject Ingestion (Duplicate Content)
    │ existing content?    │
    └──────────────────────┘
         │ No match
         ▼
    Embed text & query cosine_similarity
         │
    ┌──────────────────────┐ Similarity > threshold ──▶ Warn/Review
    │ existing embeddings? │
    └──────────────────────┘
         │ No match
         ▼
    Full ingestion pipeline
```

#### Layer 1: Exact Duplicate (file_checksum)

```python
import hashlib

async def compute_file_checksum(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

async def check_exact_duplicate(session, file_checksum: str) -> Optional[UUID]:
    result = await session.execute(text("""
        SELECT id FROM knowledge.document_versions
        WHERE file_checksum = :checksum
        ORDER BY created_at DESC LIMIT 1
    """), {"checksum": file_checksum})
    return result.scalar_one_or_none()
```

#### Layer 2: Exact Content Duplicate (content_hash)

Handles cases where the same text is extracted from different file formats (e.g., a `.docx` file converted to `.pdf`). We hash the cleaned, extracted text using SHA256.

```python
async def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

async def check_content_duplicate(session, content_hash: str) -> list[UUID]:
    result = await session.execute(text("""
        SELECT id FROM knowledge.document_versions
        WHERE content_hash = :hash
        LIMIT 5
    """), {"hash": content_hash})
    return result.scalars().all()
```

#### Layer 3: Near-Duplicate (Semantic Fingerprint)

To optimize resource usage, we do NOT embed the entire document for Layer 3. Instead, we generate a **Semantic Fingerprint** by embedding only the first 4000 characters of the extracted text. This is sufficient to identify the document's identity and detect minor revisions or similar documents without the overhead of full-document vectorization.

```python
async def check_near_duplicate(
    session,
    fingerprint_embedding: list[float],
    threshold: float = 0.90
) -> list[dict]:
    # Query semantic similarity against existing fingerprints
    result = await session.execute(text("""
        SELECT d.id, d.title,
               (1 - (cv.embedding_vector <=> :embedding::vector)) as similarity
        FROM knowledge.document_versions cv
        JOIN knowledge.documents d ON d.id = cv.document_id
        WHERE cv.embedding_vector <=> :embedding::vector < :threshold
        ORDER BY similarity DESC
        LIMIT 5
    """), {"embedding": fingerprint_embedding, "threshold": 1 - threshold})
    return result.fetchall()
```

#### Configuration

| Parameter | Default | Description |
|------------|---------|-------------|
| `SIMILARITY_THRESHOLD` | 0.90 | General threshold for near-duplicate |
| `SIMILARITY_THRESHOLD_DIGITAL` | 0.98 | Strict match for digital docs |
| `SIMILARITY_THRESHOLD_OCR` | 0.90 | Allow OCR variation |

#### Schema Additions

```sql
ALTER TABLE knowledge.document_versions
ADD COLUMN IF NOT EXISTS file_checksum VARCHAR(64),
ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64),
ADD COLUMN IF NOT EXISTS similarity_to_previous FLOAT;

CREATE INDEX idx_versions_file_checksum ON knowledge.document_versions(file_checksum);
CREATE INDEX idx_documents_content_hash ON knowledge.document_versions(content_hash);
```

#### Redundancy Detection Checklist

- [ ] Compute `file_checksum` (SHA256) from raw file bytes before extraction
- [ ] Query existing versions by `file_checksum` → if match, link to existing and skip ingestion
- [ ] Store `file_checksum` in version record after successful ingestion
- [ ] Compute `content_hash` (SHA256 of extracted text) for digital docs
- [ ] Query by `content_hash` for exact content match → if match, reject ingestion (Duplicate Content - prevents RAG pollution)
- [ ] Configurable similarity thresholds per content type
- [ ] Embedding similarity query via HNSW distance operator (`<=>`)
- [ ] Publish `document.duplicate.detected` event when similarity > threshold for admin review
- [ ] Deduplication API: `GET /api/v1/duplicates?document_id={id}` to list similar docs

### GitLab Handbook Batch Ingestion (deterministic, no Phase 1)
- [ ] Extract `domain` from file path (`content/handbook/<domain>/...`)
- [ ] Detect `redirect_to` frontmatter → `content_quality = 'REDIRECT'`
- [ ] Detect empty/tiny files (< 500 bytes) → `content_quality = 'LOW'`
- [ ] Parse Hugo frontmatter → merge into `knowledge.chunks.metadata` JSONB

### Resilience
- [ ] RabbitMQ DLQ configured for `ingestion.requests`
- [ ] Health check endpoints return proper status
- [ ] Metrics endpoint enabled in production
- [ ] Structured JSON logging enabled
- [ ] Idempotency tested: replay same event twice → no duplicate chunks
- [ ] Versioning tested: v1 → ingest → re-ingest → v2 chunks `is_latest=true`, old v1 `is_latest=false`
- [ ] OCR fallback configurable and logged
- [ ] Token count validated on Vietnamese sample
- [ ] Memory usage profiled on large documents
- [ ] Soft delete: set `deleted_at` on chunks when `document.deleted` event received

### Operational (Post-Merge TODOs)
- [ ] HNSW index load testing on target dataset size (see `contexts/database/migration-strategy.md`)
- [ ] Background ACL sync job: when `document_access_rules` changes, update flattened `allowed_*` arrays in `knowledge.chunks`
- [ ] Cleanup cron: hard-delete soft-deleted records older than retention period (users: 1 year, feedbacks: 90 days, chunks: 3 months)
- [ ] Cleanup cron: delete expired tokens from `core.access_token_blacklist` (`expired_at < NOW()`)
- [ ] Cleanup cron: delete old `is_latest = false` chunks older than 3 months to free vector storage

---

## References

- **Database Schema**: `contexts/database/tables/*.md` — Table definitions (source of truth)
- **SQL Init Scripts**: `docs/supbase_sql/*.sql` — Actual DDL
- **Authorization**: `contexts/authorization/dual-strategy.md` — ACL flattening strategy
- **Service Boundaries**: `contexts/service-boundaries/responsibilities.md` — Service ownership
- **Event Contracts**: `contexts/service-boundaries/events.md` — RabbitMQ event specifications
- **API Standards**: `contexts/service-boundaries/api-contracts.md` — Response formats
- **GitLab Handbook Analysis**: `contexts/development/extraction-plan.md` ← this document
- **Maintenance Checklists**: `contexts/database/maintenance/*.md` — Schema sync status