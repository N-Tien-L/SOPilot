#!/usr/bin/env python3
"""
Modal Ingestion Script for Poliwise Base Dataset

Usage:
    # Option 1: Generate SQL seed file (recommended - no DB connection needed)
    modal run src/scripts/ingest_modal.py --mode sql --output-path ./seed_data.sql
    
    # Option 2: Direct ingestion to PostgreSQL (requires DB connection)
    modal run src/scripts/ingest_modal.py --mode ingest --database-url "postgresql://..."
    
    # Option 3: Run locally with GPU
    python src/scripts/generate_seed_sql.py --output-path ./seed_data.sql

Environment Variables:
    MODAL_TOKEN_ID, MODAL_TOKEN_SECRET (auto-set by Modal CLI)
    
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/poliwise
    HF_API_KEY=hf_xxxxx (optional, for API-based embeddings)
    USE_HF_API=true (optional)
"""

import os
import sys
import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import modal

# Modal app definition
app = modal.App("poliwise-ingestion")

# Path of the scripts folder on the *local* machine (this file lives inside it).
_SCRIPTS_DIR = Path(__file__).resolve().parent

# Volume for persistent cache (BGE-M3 model) and base dataset.
# NOTE: `.add_local_dir(...)` must be the *last* builder step; any later
# build step (pip_install, env, run_commands, ...) forces a full rebuild
# every time a local file changes.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # We no longer run transformers/torch in this image: BGE-M3 is
        # served by a separate Modal app (poliwise-tei-bge-m3) that uses
        # the official HuggingFace TEI container. We still need httpx for
        # talking to that TEI service and tiktoken for token-aware chunking.
        "asyncpg>=0.30.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "pgvector>=0.3.0",
        "pydantic>=2.9.0",
        "tiktoken>=0.7.0",
        "httpx>=0.27.0",
        "structlog>=24.1.0",
    )
    .env({"PYTHONUNBUFFERED": "1"})
    .add_local_dir(str(_SCRIPTS_DIR), remote_path="/root/scripts")
)


# =============================================================================
# Configuration
# =============================================================================

BASE_DATASET_PATH = "/poliwise-data/handbook"
BATCH_SIZE = 4  # Process 4 files at a time
MIN_CONTENT_LENGTH = 100
TEST_LIMIT = 0  # Set to 0 to process all files

# Division mapping from folder names to major divisions
DEPT_MAP = {
    "Engineering": "Engineering & Product",
    "Product": "Engineering & Product",
    "Product Development": "Engineering & Product",
    "Security": "Engineering & Product",
    "Support": "Engineering & Product",
    "It": "Infrastructure & Operations",
    "Business Technology": "Infrastructure & Operations",
    "Enterprise Data": "Engineering & Product",
    "Quản trị hệ thống": "Engineering & Product",
    "Upstream Studios": "Engineering & Product",
    "Sales": "Sales & Marketing",
    "Marketing": "Sales & Marketing",
    "Alliances": "Sales & Marketing",
    "Resellers": "Sales & Marketing",
    "Solutions Architects": "Sales & Marketing",
    "Customer Experience": "Sales & Marketing",
    "Customer Success": "Sales & Marketing",
    "People Group": "People & Legal",
    "People Policies": "People & Legal",
    "Legal": "People & Legal",
    "Hiring": "People & Legal",
    "Total Rewards": "People & Legal",
    "Teamops": "People & Legal",
    "Labor And Employment Notices": "People & Legal",
    "Eba": "People & Legal",
    "Ceo": "Executive & Corporate",
    "Board Meetings": "Executive & Corporate",
    "Company": "Executive & Corporate",
    "About": "Executive & Corporate",
    "Leadership": "Executive & Corporate",
    "Values": "Executive & Corporate",
    "Acquisitions": "Executive & Corporate",
    "Communication": "Infrastructure & Operations",
    "Job Description Library": "People & Legal",
    "Tools And Tips": "Infrastructure & Operations",
    "Entity": "Executive & Corporate",
    "Eta": "Infrastructure & Operations",
}


# =============================================================================
# Document Processing Classes
# =============================================================================

class DocumentStandardizer:
    """Normalize document text and detect structure."""

    HEADING_PATTERNS = [
        (r"^(CHAPTER|Chapter|Chương|CHƯƠNG)\s+([IVXLCDM]+|\d+)\s*[:\-]?\s*(.*)$", 1),
        (r"^(ARTICLE|Article|Điều|ĐIỀU)\s+(\d+)\s*[:\-]?\s*(.*)$", 2),
        (r"^(CLAUSE|Clause|Khoản|KHOẢN)\s+(\d+)\s*[:\-]?\s*(.*)$", 3),
        (r"^(POINT|Point|Điểm|ĐIỂM)\s+([a-z])\s*[:\-]?\s*(.*)$", 4),
        (r"^(SECTION|Section|Mục|MỤC)\s+(\d+)\s*[:\-]?\s*(.*)$", 2),
        (r"^#{1,6}\s+(.+)$", 1),
    ]

    def normalize(self, raw_text: str) -> Dict:
        """Parse text into structured sections."""
        import unicodedata
        import re

        normalized = unicodedata.normalize("NFC", raw_text)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        sections = []
        current = {"title": "", "level": 1, "text": ""}

        for line in normalized.split("\n"):
            matched = False
            for pattern, level in self.HEADING_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    if current["text"]:
                        sections.append(current.copy())
                    title = match.group(2) if len(match.groups()) >= 2 else line.strip()
                    current = {"title": title, "level": level, "text": ""}
                    matched = True
                    break

            if not matched:
                if current["text"]:
                    current["text"] += "\n"
                current["text"] += line

        if current["text"]:
            sections.append(current.copy())

        if not sections:
            sections.append({"title": "", "level": 1, "text": normalized})

        return {
            "normalized_text": normalized,
            "sections": sections,
            "heading_count": len([s for s in sections if s["title"]]),
        }


class ParentChildChunker:
    """Create hierarchical chunks from structured text."""

    def __init__(self, parent_size: int = 1500, child_size: int = 400, child_overlap: int = 80):
        import tiktoken
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap
        self._enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, structured: Dict, metadata: Dict) -> List[Dict]:
        """Create parent-child chunks."""
        chunks = []
        sections = structured.get("sections", [])

        for section in sections:
            section_text = section.get("text", "")
            if not section_text:
                continue

            tokens = self._enc.encode(section_text)
            parent_id = str(uuid.uuid4())

            # Parent chunk
            chunks.append({
                "chunk_id": parent_id,
                "chunk_type": "parent",
                "content": section_text,
                "section_title": section.get("title", ""),
                "section_level": section.get("level", 1),
                "token_count": len(tokens),
                "metadata": metadata,
            })

            # Child chunks if section is large
            if len(tokens) > self.child_size:
                child_chunks = self._create_children(
                    section_text, parent_id, section, metadata
                )
                chunks.extend(child_chunks)

        return chunks

    def _create_children(self, text: str, parent_id: str, section: Dict, metadata: Dict) -> List[Dict]:
        """Create child chunks from parent text."""
        chunks = []
        tokens = self._enc.encode(text)

        start = 0
        idx = 0
        while start < len(tokens):
            end = min(start + self.child_size, len(tokens))
            chunk_tokens = tokens[start:end]
            child_text = self._enc.decode(chunk_tokens)

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "parent_chunk_id": parent_id,
                "chunk_type": "child",
                "content": child_text,
                "section_title": section.get("title", ""),
                "section_level": section.get("level", 1),
                "chunk_index": idx,
                "token_count": len(chunk_tokens),
                "metadata": metadata,
            })

            new_start = end - self.child_overlap
            start = end if new_start <= start else new_start
            idx += 1

        return chunks


# =============================================================================
# Embedding Service
# =============================================================================

class EmbeddingService:
    """Generate embeddings using BGE-M3 (local GPU or HuggingFace API)."""

    def __init__(self, use_hf_api: bool = False, hf_api_key: Optional[str] = None):
        self.use_hf_api = use_hf_api or bool(os.getenv("HF_API_KEY"))
        self.hf_api_key = hf_api_key or os.getenv("HF_API_KEY")
        self._model = None

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        if not texts:
            return []

        if self.use_hf_api:
            return await self._embed_via_api(texts)
        else:
            return await self._embed_via_local(texts)

    async def _embed_via_local(self, texts: List[str]) -> List[List[float]]:
        """Embed using local BGE-M3 model (GPU)."""
        import torch
        from transformers import AutoTokenizer, AutoModel
        import asyncio

        if self._model is None:
            from transformers import AutoTokenizer, AutoModel
            model_name = "BAAI/bge-m3"
            print(f"Loading BGE-M3 model from local cache/GPU...")
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModel.from_pretrained(model_name)
            self._model.eval()
            if torch.cuda.is_available():
                self._model = self._model.cuda()
                print("Model loaded on GPU")
            else:
                print("Warning: No GPU available, using CPU (slow)")

        # Truncate long texts
        truncated = []
        for text in texts:
            tokens = self._tokenizer.encode(text, add_special_tokens=True)
            if len(tokens) > 512:
                text = self._tokenizer.decode(tokens[:512], skip_special_tokens=True)
            truncated.append(text)

        # Batch encode
        with torch.no_grad():
            inputs = self._tokenizer(
                truncated,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            outputs = self._model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0]  # CLS token

            # Normalize
            norms = torch.norm(embeddings, p=2, dim=1, keepdim=True)
            embeddings = embeddings / norms

            return embeddings.cpu().numpy().tolist()

    async def _embed_via_api(self, texts: List[str]) -> List[List[float]]:
        """Embed using HuggingFace Inference API."""
        import httpx

        truncated = [t[:2000] for t in texts]  # API length limit

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api-inference.huggingface.co/pipeline/feature-extraction/BAAI/bge-m3",
                headers={"Authorization": f"Bearer {self.hf_api_key}"},
                json={"inputs": truncated},
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()


# =============================================================================
# Database Operations
# =============================================================================

async def get_db_pool(database_url: str):
    """Create asyncpg connection pool."""
    import asyncpg
    return await asyncpg.create_pool(
        database_url.replace("+asyncpg", ""),
        min_size=2,
        max_size=10,
    )


async def seed_metadata(pool, base_path: Path, user_id: uuid.UUID):
    """Seed departments and categories."""
    import asyncpg

    async with pool.acquire() as conn:
        # Seed admin user
        await conn.execute("""
            INSERT INTO core.users (id, username, email, password_hash, role, status)
            VALUES ($1, 'admin', 'admin@poliwise.com', 'hash', 'ADMIN', 'ACTIVE')
            ON CONFLICT (email) DO NOTHING
        """, user_id)

        # Seed departments
        divisions = set(DEPT_MAP.values())
        dept_cache = {}
        for div_name in divisions:
            div_id = uuid.uuid4()
            div_code = div_name.replace("&", "AND").replace(" ", "_").upper()[:20]
            await conn.execute("""
                INSERT INTO core.departments (id, name, code, is_active)
                VALUES ($1, $2, $3, true)
                ON CONFLICT (code) DO NOTHING
            """, div_id, div_name, div_code)

            row = await conn.fetchrow(
                "SELECT id FROM core.departments WHERE code = $1", div_code
            )
            if row:
                dept_cache[div_name] = row["id"]

        # Seed categories from directories
        cat_cache = {}
        for d in base_path.iterdir():
            if d.is_dir():
                cat_name = d.name.replace("-", " ").title()
                cat_slug = d.name.lower()[:100]
                cat_id = uuid.uuid4()

                await conn.execute("""
                    INSERT INTO metadata.categories (id, name, slug, is_active)
                    VALUES ($1, $2, $3, true)
                    ON CONFLICT (slug) DO NOTHING
                """, cat_id, cat_name, cat_slug)

                row = await conn.fetchrow(
                    "SELECT id FROM metadata.categories WHERE slug = $1", cat_slug
                )
                if row:
                    cat_cache[d.name] = row["id"]

        return dept_cache, cat_cache


async def get_or_create_tag(conn, tag_name: str) -> uuid.UUID:
    """Get or create a tag."""
    slug = tag_name.lower().replace(" ", "-")[:100]
    tag_id = uuid.uuid4()

    await conn.execute("""
        INSERT INTO metadata.tags (id, name, slug)
        VALUES ($1, $2, $3)
        ON CONFLICT (slug) DO NOTHING
    """, tag_id, tag_name.title(), slug)

    row = await conn.fetchrow(
        "SELECT id FROM metadata.tags WHERE slug = $1", slug
    )
    return row["id"] if row else tag_id


def parse_frontmatter(text: str) -> tuple[str, dict]:
    """Extract metadata from markdown frontmatter."""
    if not text.strip().startswith("---"):
        return text, {}

    try:
        parts = text.split("---", 2)
        if len(parts) < 3:
            return text, {}

        frontmatter_raw = parts[1]
        content = parts[2].strip()

        metadata = {}
        for line in frontmatter_raw.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip().lower()] = value.strip().strip('"').strip("'")

        return content, metadata
    except Exception:
        return text, {}


# =============================================================================
# Main Ingestion Logic
# =============================================================================

async def process_file(
    pool,
    path: Path,
    base_path: Path,
    dept_cache: dict,
    cat_cache: dict,
    user_id: uuid.UUID,
    embed_service: EmbeddingService,
    standardizer: DocumentStandardizer,
    chunker: ParentChildChunker,
) -> dict:
    """Process a single markdown file."""
    import asyncpg

    stats = {"processed": 0, "skipped": 0, "errors": 0}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()

        content, metadata = parse_frontmatter(raw_text)

        # Skip redirects and short content
        if "redirect_to" in metadata or len(content) < MIN_CONTENT_LENGTH:
            stats["skipped"] += 1
            return stats

        # Generate IDs
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        metadata_id = uuid.uuid4()
        rel_path = str(path.relative_to(base_path)).replace("\\", "/")

        # Determine hierarchy
        parts = list(path.relative_to(base_path).parts)
        root_folder = parts[0] if parts else "Company"
        div_name = DEPT_MAP.get(root_folder, "Executive & Corporate")
        dept_id = dept_cache.get(div_name)
        cat_id = cat_cache.get(root_folder)

        now = datetime.utcnow()
        title = metadata.get("title", path.name)[:500]

        async with pool.acquire() as conn:
            # Insert document
            await conn.execute("""
                INSERT INTO knowledge.documents (
                    id, original_filename, file_type, file_size_bytes, mime_type,
                    file_key, status, current_version, language,
                    chunking_strategy, uploaded_by, created_at, updated_at
                ) VALUES (
                    $1, $2, 'MD', $3, 'text/markdown',
                    $4, 'READY', 1, 'en',
                    'SEMANTIC', $5, $6, $6
                )
            """, doc_id, title, path.stat().st_size, rel_path, user_id, now)

            # Insert metadata
            await conn.execute("""
                INSERT INTO metadata.document_metadata (
                    id, document_id, title, description, document_type,
                    category_id, department_id, access_level, status,
                    current_version, created_by, updated_by, published_by,
                    published_at, effective_date, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, 'HANDBOOK',
                    $5, $6, 'PUBLIC', 'PUBLISHED',
                    1, $7, $7, $7,
                    $8, $9, $8, $8
                )
            """, metadata_id, doc_id, title, metadata.get("description", "")[:1000],
                cat_id, dept_id, user_id, now, now.date())

            # Insert tags from subfolders
            if len(parts) > 2:
                for folder in parts[1:-1]:
                    tag_id = await get_or_create_tag(conn, folder.replace("-", " ").title())
                    await conn.execute("""
                        INSERT INTO metadata.document_tags (id, document_metadata_id, tag_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT DO NOTHING
                    """, uuid.uuid4(), metadata_id, tag_id)

            # Insert version
            await conn.execute("""
                INSERT INTO knowledge.document_versions (
                    id, document_id, version_number, file_key, file_size_bytes,
                    extracted_text, is_current, created_by, created_at
                ) VALUES (
                    $1, $2, 1, $3, $4,
                    $5, true, $6, $7
                )
            """, version_id, doc_id, rel_path, path.stat().st_size, content, user_id, now)

            # Chunk and embed
            structured = standardizer.normalize(content)
            chunk_metadata = {
                "document_id": str(doc_id),
                "document_version_id": str(version_id),
                "document_version": 1,
                "access_level": "PUBLIC",
                "department_id": str(dept_id) if dept_id else None,
            }
            chunks = chunker.chunk(structured, chunk_metadata)

            if chunks:
                # Get embeddings
                chunk_contents = [c["content"] for c in chunks]
                embeddings = await embed_service.embed_batch(chunk_contents)

                # Insert chunks
                for i, chunk in enumerate(chunks):
                    emb = embeddings[i] if i < len(embeddings) else None
                    chunk_id = uuid.uuid4()
                    parent_id = uuid.UUID(chunk["parent_chunk_id"]) if chunk.get("parent_chunk_id") else None

                    await conn.execute("""
                        INSERT INTO knowledge.chunks (
                            id, document_id, document_version_id, document_version,
                            chunk_type, parent_chunk_id, content, content_length,
                            section_title, section_level, chunk_index, token_count,
                            embedding_vector, embedding_model, embedding_dimension,
                            access_level, is_latest, metadata
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                            $13, 'BGE_M3', 1024, $14, true, $15
                        )
                        ON CONFLICT (document_version_id, chunk_index, chunk_type) DO NOTHING
                    """,
                        chunk_id, doc_id, version_id, 1,
                        chunk["chunk_type"], parent_id,
                        chunk["content"], len(chunk["content"]),
                        chunk.get("section_title"), chunk.get("section_level", 1),
                        chunk.get("chunk_index", 0), chunk.get("token_count", 0),
                        emb, chunk_metadata["access_level"],
                        json.dumps(chunk_metadata)
                    )

            stats["processed"] += 1

    except Exception as e:
        print(f"Error processing {path}: {e}")
        stats["errors"] += 1

    return stats


async def run_ingestion(database_url: str, base_dataset_path: str = BASE_DATASET_PATH):
    """Main ingestion entry point."""
    print("=" * 60)
    print("Poliwise Base Dataset Ingestion on Modal")
    print("=" * 60)

    base_path = Path(base_dataset_path)
    if not base_path.exists():
        raise FileNotFoundError(f"Dataset path not found: {base_path}")

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Initialize services
    embed_service = EmbeddingService()
    standardizer = DocumentStandardizer()
    chunker = ParentChildChunker()

    # Connect to database
    print("\nConnecting to database...")
    pool = await get_db_pool(database_url)

    try:
        # Seed metadata
        print("\nSeeding departments and categories...")
        dept_cache, cat_cache = await seed_metadata(pool, base_path, user_id)
        print(f"Seeded {len(dept_cache)} departments and {len(cat_cache)} categories")

        # Get all markdown files
        files = list(base_path.rglob("*.md"))
        if TEST_LIMIT > 0:
            files = files[:TEST_LIMIT]

        print(f"\nProcessing {len(files)} markdown files...")

        # Process files
        stats = {"processed": 0, "skipped": 0, "errors": 0}

        for i in range(0, len(files), BATCH_SIZE):
            batch = files[i:i + BATCH_SIZE]
            tasks = [
                process_file(
                    pool, path, base_path, dept_cache, cat_cache,
                    user_id, embed_service, standardizer, chunker
                )
                for path in batch
            ]
            results = await asyncio.gather(*tasks)

            for r in results:
                stats["processed"] += r["processed"]
                stats["skipped"] += r["skipped"]
                stats["errors"] += r["errors"]

            print(f"Progress: {min(i + BATCH_SIZE, len(files))}/{len(files)} | "
                  f"OK: {stats['processed']} | Skip: {stats['skipped']} | Err: {stats['errors']}")

    finally:
        await pool.close()

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")
    print("=" * 60)

    return stats


# =============================================================================
# Modal Entry Point
# =============================================================================

@app.function(
    image=image,
    gpu="T4",  # Free tier; TEI runs as its own service so GPU is optional here
    timeout=3600,
    retries=1,
    volumes={
        "/data": modal.Volume.from_name("poliwise-data", create_if_missing=True),
    },
)
def generate_sql(
    output_path: str = "/data/seed_data.sql",
    base_path: str = "/data/handbook",
    use_embeddings: bool = True,
    test_limit: int = 0
):
    """
    Generate SQL seed file on Modal (no database connection needed).
    
    The SQL file can be downloaded and run on any PostgreSQL database.
    """
    # Import and run the generator
    import sys
    sys.path.insert(0, "/root/scripts")
    from generate_seed_sql import process_dataset

    # Run generation. By default we use ``modal_tei`` so the resulting
    # vectors are bit-compatible with the local Docker ``bge-m3-embedding``
    # service (same model, same pooling, same batch limits).
    process_dataset(
        base_path=Path(base_path),
        output_path=output_path,
        use_embeddings=use_embeddings,
        test_limit=test_limit,
        embedding_mode="modal_tei",
    )


@app.function(
    image=image,
    gpu="T4",
    timeout=3600,
    retries=1,
    volumes={
        "/data": modal.Volume.from_name("poliwise-data", create_if_missing=True),
    },
)
def ingest_to_database(
    database_url: str,
    base_path: str = "/data/handbook",
    test_limit: int = 0
):
    """
    Direct ingestion to PostgreSQL (requires accessible database).
    
    This function:
    1. Mounts the base_dataset volume at /data
    2. Uses GPU for BGE-M3 embedding
    3. Connects to the specified PostgreSQL database
    """
    import os
    import asyncio
    import sys
    sys.path.insert(0, "/root/scripts")

    from generate_seed_sql import process_dataset

    # Run ingestion via asyncio
    asyncio.run(run_ingestion(database_url, base_path, test_limit))


@app.local_entrypoint()
def entrypoint(
    mode: str = None,
    database_url: str = None,
    output_path: str = None,
    base_path: str = None,
    no_embeddings: bool = False,
    test_limit: int = 0
):
    """
    Local entrypoint that dispatches to Modal functions.

    Examples:
        # Generate SQL on Modal GPU using the poliwise-data volume
        modal run ingest_modal.py --mode sql

        # Ingest directly to a remote PostgreSQL on Modal GPU
        modal run ingest_modal.py --mode ingest --database-url "postgresql://..."

        # Run a small smoke test (10 files) on Modal
        modal run ingest_modal.py --mode sql --test-limit 10

    Notes:
        - The base dataset is expected to live on the Modal volume
          'poliwise-data' (created automatically) at the path 'handbook/'.
        - That volume is mounted at '/data' inside the Modal container,
          so base_path='/data/handbook' is the default.
        - The generated SQL is written to '/data/seed_data.sql' inside
          the volume; download it with:
              modal volume get poliwise-data /seed_data.sql ./seed_data.sql
    """
    import os

    if not mode:
        mode = "sql"

    if not base_path:
        base_path = "/data/handbook"
    if not output_path:
        output_path = "/data/seed_data.sql"

    if mode == "ingest":
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("Error: DATABASE_URL required for ingest mode.")
            print("Provide --database-url or set DATABASE_URL env var,")
            print("or use --mode sql to generate a SQL seed file instead.")
            sys.exit(1)

        print(f"Running ingestion to database on Modal...")
        print(f"  base_path:   {base_path}")
        print(f"  test_limit:  {test_limit}")
        ingest_to_database.remote(
            database_url=database_url,
            base_path=base_path,
            test_limit=test_limit,
        )
        return

    if mode != "sql":
        print(f"Error: unknown mode '{mode}'. Use 'sql' or 'ingest'.")
        sys.exit(2)

    # mode == "sql" — dispatch to the GPU-backed Modal function.
    print(f"Generating SQL seed file on Modal...")
    print(f"  base_path:     {base_path}")
    print(f"  output_path:   {output_path}")
    print(f"  embeddings:    {'off' if no_embeddings else 'on (BGE-M3)'}")
    print(f"  test_limit:    {test_limit}")
    generate_sql.remote(
        output_path=output_path,
        base_path=base_path,
        use_embeddings=not no_embeddings,
        test_limit=test_limit,
    )


if __name__ == "__main__":
    entrypoint()
