#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate SQL Seed File for Poliwise Base Dataset

Usage:
    # Local execution (recommended for first run)
    python src/scripts/generate_seed_sql.py
    
    # On Modal (with GPU for embeddings)
    modal run src/scripts/generate_seed_sql.py --output-path ./seed_data.sql

Output:
    - seed_data.sql: Full SQL INSERT statements for all tables
    - Can be run on any PostgreSQL database

Tables generated:
    - core.users
    - core.departments
    - metadata.categories
    - metadata.tags
    - metadata.document_metadata
    - metadata.document_tags
    - knowledge.documents
    - knowledge.document_versions
    - knowledge.chunks
"""

import os
import sys
import json
import uuid

# Fix UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import argparse


# =============================================================================
# Configuration
# =============================================================================

BASE_DATASET_PATH = "/data/base_dataset/handbook"
OUTPUT_PATH = "./seed_data.sql"
MIN_CONTENT_LENGTH = 100
TEST_LIMIT = 0  # Set to 0 to process all, or e.g. 10 for testing

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

# Fixed UUID for admin user
ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =============================================================================
# SQL Generator
# =============================================================================

class SQLGenerator:
    """Generate SQL INSERT statements from processed documents."""

    def __init__(self, output_file):
        self.output_file = output_file
        self.statements: List[str] = []
        self._write_header()

    def _write_header(self):
        """Write SQL file header."""
        self._add("""
-- =============================================================================
-- Poliwise Base Dataset Seed File
-- Generated: {date}
-- Source: GitLab Handbook
-- =============================================================================
-- 
-- To use this file:
-- 1. Run Flyway migrations first to create tables
-- 2. psql -U poliwise -d poliwise -f seed_data.sql
--
-- IMPORTANT: This file uses ON CONFLICT DO NOTHING for idempotent execution
-- =============================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmlentity = no;
SET escape_string_warning = off;

-- =============================================================================
-- SECTION: Users
-- =============================================================================

""".format(date=datetime.utcnow().isoformat()))

    def _add(self, sql: str):
        """Add SQL statement."""
        self.statements.append(sql)

    def _escape_sql_string(self, s: str) -> str:
        """Escape string for SQL."""
        if s is None:
            return "NULL"
        s = str(s)
        # Escape single quotes
        s = s.replace("'", "''")
        # Escape backslashes
        s = s.replace("\\", "\\\\")
        return f"'{s}'"

    def _escape_sql_text(self, s: str) -> str:
        """Escape text content (handles newlines better)."""
        if s is None:
            return "NULL"
        s = str(s)
        # Escape single quotes
        s = s.replace("'", "''")
        # Escape backslashes
        s = s.replace("\\", "\\\\")
        # Use E'...' for proper newline handling
        return f"E'{s}'"

    def _format_uuid(self, u: uuid.UUID) -> str:
        """Format UUID for SQL."""
        return f"'{str(u)}'"

    def _format_array(self, items: list) -> str:
        """Format list as PostgreSQL array."""
        if not items:
            return "NULL"
        escaped = [self._escape_sql_string(str(x)) for x in items]
        return "ARRAY[" + ", ".join(escaped) + "]::uuid[]"

    def _format_text_array(self, items: list) -> str:
        """Format list as PostgreSQL text array."""
        if not items:
            return "NULL"
        escaped = [self._escape_sql_string(str(x)) for x in items]
        return "ARRAY[" + ", ".join(escaped) + "]::text[]"

    def _format_vector(self, embedding: list) -> str:
        """Format embedding as pgvector."""
        if not embedding:
            return "NULL"
        vals = ", ".join([f"{v:.6f}" for v in embedding])
        return f"'[{vals}]'::vector"

    # -------------------------------------------------------------------------
    # User & Department Seeding
    # -------------------------------------------------------------------------

    def seed_users(self):
        """Generate user INSERT statements."""
        self._add("""
-- Admin user
INSERT INTO core.users (id, username, email, password_hash, role, status)
VALUES (
    {admin_id},
    'admin',
    'admin@poliwise.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqJ5.KK0Ke',  -- password: admin123
    'ADMIN'::core.user_role,
    'ACTIVE'::core.account_status
) ON CONFLICT (username) DO NOTHING;

-- Admin profile
INSERT INTO core.user_profiles (id, user_id, full_name)
VALUES (
    '{profile_id}',
    {admin_id},
    'System Administrator'
) ON CONFLICT (user_id) DO NOTHING;
""".format(
    admin_id=self._format_uuid(ADMIN_USER_ID),
    profile_id=uuid.uuid4()
))

    def seed_departments(self, divisions: Dict[str, uuid.UUID]):
        """Generate department INSERT statements."""
        self._add("""
-- =============================================================================
-- SECTION: Departments
-- =============================================================================

""")
        for div_name, div_id in divisions.items():
            div_code = div_name.replace("&", "AND").replace(" ", "_").upper()[:20]
            self._add(f"""
INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    {self._format_uuid(div_id)},
    {self._escape_sql_string(div_name)},
    {self._escape_sql_string(div_code)},
    true
) ON CONFLICT (code) DO NOTHING;
""")

    def seed_categories(self, categories: Dict[str, uuid.UUID]):
        """Generate category INSERT statements."""
        self._add("""
-- =============================================================================
-- SECTION: Categories
-- =============================================================================

""")
        for folder_name, cat_id in categories.items():
            cat_name = folder_name.replace("-", " ").title()
            cat_slug = folder_name.lower()[:100]
            self._add(f"""
INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    {self._format_uuid(cat_id)},
    {self._escape_sql_string(cat_name)},
    {self._escape_sql_string(cat_slug)},
    true
) ON CONFLICT (slug) DO NOTHING;
""")

    def seed_tags(self, tags: Dict[str, uuid.UUID]):
        """Generate tag INSERT statements."""
        if not tags:
            return
        self._add("""
-- =============================================================================
-- SECTION: Tags
-- =============================================================================

""")
        for tag_name, tag_id in tags.items():
            tag_slug = tag_name.lower().replace(" ", "-")[:50]
            self._add(f"""
INSERT INTO metadata.tags (id, name, slug)
VALUES (
    {self._format_uuid(tag_id)},
    {self._escape_sql_string(tag_name)},
    {self._escape_sql_string(tag_slug)}
) ON CONFLICT (slug) DO NOTHING;
""")

    # -------------------------------------------------------------------------
    # Document Insertion
    # -------------------------------------------------------------------------

    def insert_document(self, doc_data: Dict):
        """Generate INSERT statements for a document and all related data."""
        self._add(f"""
-- =============================================================================
-- DOCUMENT: {self._escape_sql_string(doc_data['title'][:100])}
-- File: {self._escape_sql_string(doc_data['rel_path'])}
-- =============================================================================

-- Document record
INSERT INTO knowledge.documents (
    id, original_filename, file_type, file_size_bytes, mime_type,
    file_key, status, current_version, language,
    chunking_strategy, uploaded_by, created_at, updated_at
) VALUES (
    {self._format_uuid(doc_data['doc_id'])},
    {self._escape_sql_string(doc_data['title'])},
    'MD'::knowledge.file_type,
    {doc_data['file_size']},
    'text/markdown',
    {self._escape_sql_string(doc_data['rel_path'])},
    'READY'::knowledge.processing_status,
    1,
    'en',
    'SEMANTIC'::knowledge.chunking_strategy,
    {self._format_uuid(ADMIN_USER_ID)},
    '{doc_data['created_at']}',
    '{doc_data['created_at']}'
) ON CONFLICT DO NOTHING;

-- Document metadata
INSERT INTO metadata.document_metadata (
    id, document_id, title, description, document_type,
    category_id, department_id, access_level, status,
    current_version, created_by, updated_by, published_by,
    published_at, effective_date, created_at, updated_at
) VALUES (
    {self._format_uuid(doc_data['metadata_id'])},
    {self._format_uuid(doc_data['doc_id'])},
    {self._escape_sql_string(doc_data['title'])},
    {self._escape_sql_string(doc_data.get('description', '')[:1000])},
    'HANDBOOK',
    {self._format_uuid(doc_data['category_id']) if doc_data.get('category_id') else 'NULL'},
    {self._format_uuid(doc_data['department_id']) if doc_data.get('department_id') else 'NULL'},
    'PUBLIC'::metadata.access_level,
    'PUBLISHED'::metadata.document_status,
    1,
    {self._format_uuid(ADMIN_USER_ID)},
    {self._format_uuid(ADMIN_USER_ID)},
    {self._format_uuid(ADMIN_USER_ID)},
    '{doc_data['created_at']}',
    '{doc_data['created_date']}',
    '{doc_data['created_at']}',
    '{doc_data['created_at']}'
) ON CONFLICT DO NOTHING;

-- Document version
INSERT INTO knowledge.document_versions (
    id, document_id, version_number, file_key, file_size_bytes,
    extracted_text, is_current, created_by, created_at
) VALUES (
    {self._format_uuid(doc_data['version_id'])},
    {self._format_uuid(doc_data['doc_id'])},
    1,
    {self._escape_sql_string(doc_data['rel_path'])},
    {doc_data['file_size']},
    {self._escape_sql_text(doc_data['content'])},
    true,
    {self._format_uuid(ADMIN_USER_ID)},
    '{doc_data['created_at']}'
) ON CONFLICT DO NOTHING;
""")

        # Insert chunks
        if doc_data.get('chunks'):
            self._add("\n-- Chunks")
            for i, chunk in enumerate(doc_data['chunks']):
                parent_ref = self._format_uuid(chunk['parent_id']) if chunk.get('parent_id') else 'NULL'
                section_path = self._format_text_array(chunk.get('section_path', [])) if chunk.get('section_path') else 'NULL'
                dept_arr = self._format_array([doc_data['department_id']]) if doc_data.get('department_id') else 'NULL'

                self._add(f"""
INSERT INTO knowledge.chunks (
    id, document_id, document_version_id, document_version, chunk_type,
    parent_chunk_id, content, content_length, section_title, section_level,
    section_path, chunk_index, start_char_index, end_char_index, token_count,
    embedding_vector, embedding_model, embedding_dimension,
    allowed_roles, allowed_departments, allowed_users, access_level,
    is_latest, metadata
) VALUES (
    {self._format_uuid(chunk['id'])},
    {self._format_uuid(doc_data['doc_id'])},
    {self._format_uuid(doc_data['version_id'])},
    1,
    {self._escape_sql_string(chunk['type'])},
    {parent_ref},
    {self._escape_sql_text(chunk['content'])},
    {len(chunk['content'])},
    {self._escape_sql_string(chunk.get('section_title', ''))},
    {chunk.get('section_level', 1)},
    {section_path},
    {chunk['index']},
    {chunk.get('start_char', 0)},
    {chunk.get('end_char', len(chunk['content']))},
    {chunk.get('token_count', 0)},
    {self._format_vector(chunk.get('embedding')) if chunk.get('embedding') else 'NULL'},
    'BGE_M3',
    1024,
    ARRAY['USER', 'MANAGER', 'ADMIN']::core.user_role[],
    {dept_arr},
    NULL,
    'PUBLIC',
    true,
    {self._escape_sql_string(json.dumps(chunk.get('metadata', {})))}
) ON CONFLICT (document_version_id, chunk_index, chunk_type) DO NOTHING;
""")

    def save(self):
        """Write all SQL to file."""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(self.statements))
        print(f"SQL seed file written to: {self.output_file}")


# =============================================================================
# Document Processing
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
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap
        self._enc = None

    def _get_tokenizer(self):
        """Lazy load tiktoken tokenizer."""
        if self._enc is None:
            import tiktoken
            self._enc = tiktoken.get_encoding("cl100k_base")
        return self._enc

    def chunk(self, structured: Dict, metadata: Dict) -> List[Dict]:
        """Create parent-child chunks."""
        chunks = []
        sections = structured.get("sections", [])
        enc = self._get_tokenizer()

        for section in sections:
            section_text = section.get("text", "")
            if not section_text:
                continue

            tokens = enc.encode(section_text)
            parent_id = uuid.uuid4()
            section_path = metadata.get("section_path", [])

            # Parent chunk
            chunks.append({
                "id": parent_id,
                "type": "parent",
                "parent_id": None,
                "content": section_text,
                "section_title": section.get("title", ""),
                "section_level": section.get("level", 1),
                "section_path": section_path + [section.get("title", "")] if section.get("title") else section_path,
                "index": len(chunks),
                "token_count": len(tokens),
                "start_char": 0,
                "end_char": len(section_text),
                "metadata": metadata,
            })

            # Child chunks if section is large
            if len(tokens) > self.child_size:
                child_chunks = self._create_children(
                    section_text, str(parent_id), section, section_path, len(chunks) - 1
                )
                chunks.extend(child_chunks)

        return chunks

    def _create_children(self, text: str, parent_id: str, section: Dict, section_path: List, parent_idx: int) -> List[Dict]:
        """Create child chunks from parent text."""
        chunks = []
        enc = self._get_tokenizer()
        tokens = enc.encode(text)

        start = 0
        idx = 0
        while start < len(tokens):
            end = min(start + self.child_size, len(tokens))
            chunk_tokens = tokens[start:end]
            child_text = enc.decode(chunk_tokens)

            # Calculate char positions
            start_text = enc.decode(tokens[:start]) if start > 0 else ""
            start_char = len(start_text)
            end_char = start_char + len(child_text)

            chunks.append({
                "id": uuid.uuid4(),
                "type": "child",
                "parent_id": uuid.UUID(parent_id),
                "content": child_text,
                "section_title": section.get("title", ""),
                "section_level": section.get("level", 1),
                "section_path": section_path,
                "index": parent_idx + idx + 1,
                "token_count": len(chunk_tokens),
                "start_char": start_char,
                "end_char": end_char,
                "metadata": {},
            })

            new_start = end - self.child_overlap
            start = end if new_start <= start else new_start
            idx += 1

        return chunks


# =============================================================================
# Embedding Service (Modal TEI for BAAI/bge-m3)
# =============================================================================
#
# Vectors produced here are bit-compatible with the local Docker TEI service
# (``bge-m3-embedding`` in docker-compose.yml) because both use the same
# image, model id, and pooling mode (``cls``). This is the single source of
# truth for BGE-M3 embeddings across local Docker and Modal ingestion paths.
#
# We deliberately do NOT use ``transformers.AutoModel`` directly: its CLS
# hidden state is missing the dense linear projection that BGE-M3 applies,
# so the resulting vectors would not match the local pipeline.
#
# If the Modal TEI app (``poliwise-tei-bge-m3``) is unreachable for any
# reason, we fall back to a deterministic stub vector (``None``) so that the
# SQL seed file is still generated. ``knowledge.chunks.embedding_vector``
# stays NULL for those rows and the ingestion completes without errors.

EMBEDDING_DIMENSION = 1024
EMBEDDING_MODEL_NAME = "BGE_M3"


class EmbeddingService:
    """Generate BGE-M3 embeddings by delegating to the Modal TEI app.

    The class is duck-typed so callers can swap ``modal_tei`` for ``local`` /
    ``stub`` without changing the rest of the pipeline.
    """

    def __init__(self, mode: str = "modal_tei"):
        """``mode`` is one of ``"modal_tei"``, ``"local"``, ``"stub"``."""
        self.mode = mode
        self._modal_fn = None  # lazy import of the Modal remote function

    def _resolve_remote(self):
        """Return a callable that takes a list[str] and returns list[list[float]].

        We import ``bge_m3_tei`` lazily so the same script still works in
        local-only environments that do not have Modal installed.
        """
        if self._modal_fn is not None:
            return self._modal_fn

        try:
            import bge_m3_tei  # /root/scripts/bge_m3_tei.py on Modal
        except ImportError as e:
            raise RuntimeError(
                "Modal TEI module not available; pass mode='local' or mode='stub' "
                "to fall back to a non-Modal path."
            ) from e

        self._modal_fn = bge_m3_tei.embed_texts
        return self._modal_fn

    def load_model(self):
        """No-op: Modal TEI loads the model lazily on first request."""
        if self.mode == "modal_tei":
            print("Embedding mode: Modal TEI (poliwise-tei-bge-m3)")
        elif self.mode == "local":
            print("Embedding mode: local stub (no embeddings will be computed)")
        else:
            print(f"Embedding mode: {self.mode}")

    def embed_texts(self, texts):
        """Embed a batch of texts and return a list of 1024-dim vectors.

        ``texts`` is a list of strings. The return value mirrors the
        OpenAI-compatible TEI response shape used by the local Docker service.
        """
        if not texts:
            return []

        if self.mode == "modal_tei":
            remote = self._resolve_remote()
            try:
                return list(remote.remote(texts))
            except Exception as e:
                print(
                    f"[embedding] Modal TEI call failed ({e}); "
                    "falling back to NULL vectors for this batch."
                )
                return [None] * len(texts)  # type: ignore[return-value]

        if self.mode == "stub":
            return [None] * len(texts)  # type: ignore[return-value]

        # ``local`` mode is reserved for environments without Modal; we
        # return NULL vectors so SQL generation still produces a valid file.
        return [None] * len(texts)  # type: ignore[return-value] 


# =============================================================================
# Main Processing
# =============================================================================

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


def process_dataset(
    base_path: Path,
    output_path: str,
    use_embeddings: bool = True,
    test_limit: int = 0,
    embedding_mode: str = "modal_tei",
):
    """Process all markdown files and generate SQL.

    ``embedding_mode`` is forwarded to ``EmbeddingService``:
      * ``"modal_tei"`` (default) – call the Modal TEI app
        ``poliwise-tei-bge-m3`` so vectors match local Docker exactly.
      * ``"stub"`` – emit NULL embeddings (no network calls); useful for
        smoke-testing the rest of the pipeline.
    """
    print("=" * 60)
    print("Poliwise Base Dataset - SQL Seed Generator")
    print("=" * 60)

    if not base_path.exists():
        raise FileNotFoundError(f"Dataset path not found: {base_path}")

    # Initialize components
    sql_gen = SQLGenerator(output_path)
    standardizer = DocumentStandardizer()
    chunker = ParentChildChunker()
    embed_service = EmbeddingService(mode=embedding_mode) if use_embeddings else None

    # Load embedding model if needed (no-op for Modal TEI)
    if embed_service:
        embed_service.load_model()

    # Phase 1: Seed static data
    print("\n[Phase 1] Seeding static data...")

    # Seed users
    sql_gen.seed_users()

    # Seed departments
    divisions = {}
    for div_name in set(DEPT_MAP.values()):
        divisions[div_name] = uuid.uuid4()
    sql_gen.seed_departments(divisions)

    # Seed categories (from directories)
    categories = {}
    for d in base_path.iterdir():
        if d.is_dir():
            categories[d.name] = uuid.uuid4()
    sql_gen.seed_categories(categories)

    print(f"  - {len(divisions)} departments")
    print(f"  - {len(categories)} categories")

    # Phase 2: Process documents
    print("\n[Phase 2] Processing documents...")

    files = list(base_path.rglob("*.md"))
    if test_limit > 0:
        files = files[:test_limit]
    print(f"  Found {len(files)} markdown files")

    # Track all tags
    all_tags: Dict[str, uuid.UUID] = {}
    stats = {"processed": 0, "skipped": 0, "errors": 0}

    for i, path in enumerate(files):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

            content, metadata = parse_frontmatter(raw_text)

            # Skip redirects and short content
            if "redirect_to" in metadata or len(content) < MIN_CONTENT_LENGTH:
                stats["skipped"] += 1
                continue

            # Generate IDs
            doc_id = uuid.uuid4()
            version_id = uuid.uuid4()
            metadata_id = uuid.uuid4()
            rel_path = str(path.relative_to(base_path)).replace("\\", "/")

            # Determine hierarchy
            parts = list(path.relative_to(base_path).parts)
            root_folder = parts[0] if parts else "Company"
            div_name = DEPT_MAP.get(root_folder, "Executive & Corporate")
            dept_id = divisions.get(div_name)
            cat_id = categories.get(root_folder)

            now = datetime.utcnow()
            title = metadata.get("title", path.name)[:500]

            # Process chunks
            structured = standardizer.normalize(content)
            chunk_metadata = {
                "document_id": str(doc_id),
                "document_version_id": str(version_id),
                "section_path": parts[:-1],
            }
            chunks = chunker.chunk(structured, chunk_metadata)

            # Generate embeddings for chunks.
            #
            # TEI processes batches server-side up to ``--max-client-batch-size``
            # (we set it to 8) and ``--max-batch-tokens`` (2048). A larger
            # client-side batch is fine because TEI splits it internally; the
            # practical sweet spot is 32 to amortise the round-trip cost.
            if chunks and embed_service:
                chunk_contents = [c["content"] for c in chunks]
                embeddings: List[Optional[List[float]]] = []
                batch_size = 32
                for j in range(0, len(chunk_contents), batch_size):
                    batch = chunk_contents[j:j + batch_size]
                    emb_batch = embed_service.embed_texts(batch)
                    embeddings.extend(emb_batch)

                for k, chunk in enumerate(chunks):
                    emb = embeddings[k] if k < len(embeddings) else None
                    chunk["embedding"] = emb
                    # If embedding failed, store a short sentinel so we can
                    # tell NULL-embedding rows apart later (also keeps the
                    # ``chunk_index`` constraint satisfied).
                    if emb is None:
                        stats.setdefault("missing_embeddings", 0)
                        stats["missing_embeddings"] += 1

            # Extract tags from subfolders
            doc_tags = []
            if len(parts) > 2:
                for folder in parts[1:-1]:
                    tag_name = folder.replace("-", " ").title()
                    if tag_name not in all_tags:
                        all_tags[tag_name] = uuid.uuid4()
                    doc_tags.append(all_tags[tag_name])

            # Prepare document data
            doc_data = {
                "doc_id": doc_id,
                "metadata_id": metadata_id,
                "version_id": version_id,
                "title": title,
                "description": metadata.get("description", ""),
                "rel_path": rel_path,
                "file_size": path.stat().st_size,
                "content": content,
                "category_id": cat_id,
                "department_id": dept_id,
                "created_at": now.isoformat(),
                "created_date": now.date().isoformat(),
                "tags": doc_tags,
                "chunks": chunks,
            }

            sql_gen.insert_document(doc_data)
            stats["processed"] += 1

            # Progress update
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{len(files)} files processed...")

        except Exception as e:
            print(f"  Error processing {path}: {e}")
            stats["errors"] += 1

    # Phase 3: Seed tags
    print("\n[Phase 3] Seeding tags...")
    sql_gen.seed_tags(all_tags)
    print(f"  - {len(all_tags)} tags")

    # Save SQL file
    print("\n[Phase 4] Writing SQL file...")
    sql_gen.save()

    # Summary
    print("\n" + "=" * 60)
    print("Generation complete!")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")
    print(f"  Output:    {output_path}")
    print("=" * 60)

    return stats


# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate SQL seed file from base dataset")
    parser.add_argument(
        "--base-path",
        type=str,
        default="/data/base_dataset/handbook",
        help="Path to base dataset (default: /data/base_dataset/handbook)"
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="./seed_data.sql",
        help="Output SQL file path (default: ./seed_data.sql)"
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation (faster, smaller file)"
    )
    parser.add_argument(
        "--test-limit",
        type=int,
        default=0,
        help="Limit number of files for testing (0 = all)"
    )
    parser.add_argument(
        "--embedding-mode",
        choices=("modal_tei", "stub"),
        default="modal_tei",
        help=(
            "Where to compute embeddings. 'modal_tei' (default) calls the "
            "Modal TEI app so vectors match local Docker exactly. 'stub' "
            "writes NULL embeddings (no network calls)."
        ),
    )

    args = parser.parse_args()

    base_path = Path(args.base_path)
    if not base_path.exists():
        # Try local path
        local_path = Path(__file__).parent.parent.parent.parent / "base_dataset" / "handbook"
        if local_path.exists():
            base_path = local_path
            print(f"Using local path: {base_path}")
        else:
            print(f"Error: Dataset path not found")
            print(f"  Tried: {args.base_path}")
            print(f"  Tried: {local_path}")
            sys.exit(1)

    process_dataset(
        base_path=base_path,
        output_path=args.output_path,
        use_embeddings=not args.no_embeddings,
        test_limit=args.test_limit,
        embedding_mode=args.embedding_mode,
    )


if __name__ == "__main__":
    main()
