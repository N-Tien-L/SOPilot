# Poliwise Ingestion Service

Python FastAPI service for document extraction, chunking, and embedding.

## Project Structure

```
services/ingestion-service/
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .dockerignore
├── src/
│   ├── main.py                          # FastAPI app entry point
│   ├── config/
│   │   ├── settings.py                  # Pydantic settings
│   │   └── rabbitmq.py                  # RabbitMQ connection setup
│   ├── api/
│   │   └── routes/
│   │       ├── health.py                # GET /health
│   │       └── ingest.py                # POST /ingest, GET /ingest/{job_id}/status
│   ├── services/
│   │   ├── extractor.py                 # Extraction orchestrator
│   │   ├── standardizer.py              # DocumentPolicyStandardizer
│   │   ├── chunker.py                   # Parent-child chunker
│   │   ├── embedding_service.py         # BGE-M3 via LitServe
│   │   ├── minio_service.py             # MinIO download client
│   │   └── processing_job_service.py    # Update job status
│   ├── models/
│   │   ├── extraction.py                # Extraction output models
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
│       ├── consumer.py                  # Consume ingestion.requested
│       └── publisher.py                 # Publish document.uploaded
└── tests/
```

## Quick Start

### 1. Environment Setup

Copy the environment example file and configure it:

```bash
cp .env.example .env
```

Update the `.env` file with your configuration values.

### 2. Running with Docker Compose

The service is integrated into the main Poliwise docker-compose setup. To run:

```bash
# From the project root
docker-compose up -d ingestion-service
```

The service will start on port `8088`.

### 3. Running Locally (Development)

```bash
# Install dependencies
pip install -e .

# Run the service
uvicorn src.main:app --reload --port 8088
```

### 4. Health Check

```bash
curl http://localhost:8088/health
```

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/ingest` - Trigger manual ingestion
- `GET /api/v1/ingest/{job_id}/status` - Check ingestion status

## Dependencies

Key dependencies include:

- **FastAPI** - Web framework
- **SQLAlchemy + asyncpg** - Async database access
- **aio-pika** - RabbitMQ client
- **MinIO** - Object storage
- **PyMuPDF, python-docx, openpyxl** - Document extraction
- **pytesseract** - OCR for images
- **tiktoken** - Token counting
- **pgvector** - Vector storage for embeddings

## Development

### Running Tests

```bash
pytest tests/
```

### Code Linting

```bash
ruff check src/
```

## Architecture

### Pipeline Flow

1. **Upload & Metadata Suggestion (Phase 1)** - Synchronous, handled by knowledge-service
2. **Persistence & Ingestion Launch (Phase 2)** - Async via RabbitMQ

### Event-Driven Processing

- **Consumes**: `ingestion.requested`, `document.deleted`
- **Publishes**: `document.uploaded`

### Extraction Strategy

Uses Registry/Strategy pattern with format-specific extractors:
- Markdown (`.md`) - Built-in
- Text (`.txt`) - Built-in
- PDF (`.pdf`) - PyMuPDF
- Word (`.docx`) - python-docx
- Excel (`.xlsx`) - openpyxl
- Images (`.png`, `.jpg`) - pytesseract + Pillow

## Configuration

See `.env.example` for all available configuration options.

## Next Steps (Phase 2+)

- [ ] Implement actual extraction logic for each format
- [ ] Complete hierarchical chunking algorithm
- [ ] Integrate embedding service (BGE-M3)
- [ ] Add Vietnamese document standardization
- [ ] Implement OCR fallback for scanned documents
- [ ] Add comprehensive tests
- [ ] Add monitoring and metrics
