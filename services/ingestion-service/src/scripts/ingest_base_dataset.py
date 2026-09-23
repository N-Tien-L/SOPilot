import os
import asyncio
import uuid
import structlog
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# Configure path to recognize src module
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from src.db.session import async_session
from src.db.repositories.chunk_repo import ChunkRepository
from src.services.standardizer import DocumentPolicyStandardizer
from src.services.chunker import ParentChildChunker
from src.services.embedding_service import embedding_service
from sqlalchemy import text

logger = structlog.get_logger()

# Config parameters
BASE_DATASET_PATH = "/app/base_dataset/handbook"
BATCH_SIZE = 1
MIN_CONTENT_LENGTH = 100 
TEST_LIMIT = 50 # Set to 0 to run all
BASE_DATASET_ACCESS_LEVEL = os.getenv("BASE_DATASET_ACCESS_LEVEL", "RESTRICTED").upper()

class HandbookIngestor:
    def __init__(self):
        self.standardizer = DocumentPolicyStandardizer()
        self.chunker = ParentChildChunker()
        self.user_id = uuid.UUID("00000000-0000-0000-0000-000000000001") 
        self.departments_cache = {} # name -> id (Major Divisions)
        self.categories_cache = {} # name -> id (The 38 folders)
        self.tags_cache = {} # slug -> id
        
        # Division Mapping
        self.dept_map = {
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
            "Eta": "Infrastructure & Operations"
        }

    def _parse_frontmatter(self, text_content: str) -> tuple[str, dict]:
        """Extract metadata from markdown header."""
        if not text_content.strip().startswith("---"):
            return text_content, {}
        
        try:
            parts = text_content.split("---", 2)
            if len(parts) < 3:
                return text_content, {}

            frontmatter_raw = parts[1]
            content = parts[2].strip()

            metadata = {}
            for line in frontmatter_raw.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip().strip('"').strip("'")

            return content, metadata
        except Exception:
            return text_content, {}

    async def ingest_all(self):
        abs_base_path = Path(BASE_DATASET_PATH)
        if not abs_base_path.exists():
            logger.error(f"❌ Error: Path {abs_base_path} does not exist.")
            return

        # Phase 1: Directory Parsing & Metadata Seeding
        logger.info("🏢 Phase 1: Seeding Divisions and Categories...")
        await self._seed_metadata(abs_base_path)

        # Gather files
        files = list(abs_base_path.rglob("*.md"))
        if TEST_LIMIT:
            files = files[:TEST_LIMIT]
            
        logger.info(f"🚀 Phase 2 & 3 & 4: Processing {len(files)} markdown files...")

        processed = 0
        skipped = 0
        errors = 0

        for i in range(0, len(files), BATCH_SIZE):
            batch = files[i:i + BATCH_SIZE]
            res = await self.process_batch(batch, abs_base_path)
            
            processed += res['processed']
            skipped += res['skipped']
            errors += res['errors']
            
            logger.info(f"📊 Progress: {min(i + BATCH_SIZE, len(files))}/{len(files)} | ✅ Success: {processed} | ⏩ Skipped: {skipped} | ❌ Errors: {errors}")

        logger.info("✨ Ingestion completed!")

    async def _seed_metadata(self, base_path: Path):
        async with async_session() as session:
            # 0. Seed Admin User if not exists
            admin_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
            await session.execute(text("""
                INSERT INTO core.users (id, username, email, password_hash, role, status)
                VALUES (:id, 'admin', 'admin@poliwise.com', 'hash', CAST('ADMIN' AS core.user_role), CAST('ACTIVE' AS core.account_status))
                ON CONFLICT (email) DO NOTHING
            """), {"id": admin_id})
            self.user_id = admin_id

            # 1. Seed Major Divisions (Departments)
            divisions = set(self.dept_map.values())
            for div_name in divisions:
                div_id = uuid.uuid4()
                div_code = div_name.replace("&", "AND").replace(" ", "_").upper()[:20]
                await session.execute(text("""
                    INSERT INTO core.departments (id, name, code, is_active)
                    VALUES (:id, :name, :code, true)
                    ON CONFLICT (code) DO NOTHING
                """), {"id": div_id, "name": div_name, "code": div_code})
                
                res = await session.execute(text("SELECT id FROM core.departments WHERE code = :code"), {"code": div_code})
                self.departments_cache[div_name] = res.fetchone()[0]

            # 2. Seed 38 Folders as Categories
            top_level_dirs = [d for d in base_path.iterdir() if d.is_dir()]
            for d in top_level_dirs:
                cat_name = d.name.replace("-", " ").title()
                cat_slug = d.name.lower()[:100]
                cat_id = uuid.uuid4()
                
                await session.execute(text("""
                    INSERT INTO metadata.categories (id, name, slug, is_active)
                    VALUES (:id, :name, :slug, true)
                    ON CONFLICT (slug) DO NOTHING
                """), {"id": cat_id, "name": cat_name, "slug": cat_slug})
                
                res = await session.execute(text("SELECT id FROM metadata.categories WHERE slug = :slug"), {"slug": cat_slug})
                self.categories_cache[d.name] = res.fetchone()[0]
                
            await session.commit()

    async def _get_or_create_tag(self, session, tag_name: str) -> uuid.UUID:
        slug = tag_name.lower().replace(" ", "-")[:100]
        if slug in self.tags_cache:
            return self.tags_cache[slug]
            
        tag_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO metadata.tags (id, name, slug)
            VALUES (:id, :name, :slug)
            ON CONFLICT (slug) DO NOTHING
        """), {"id": tag_id, "name": tag_name.title(), "slug": slug})
        
        res = await session.execute(text("SELECT id FROM metadata.tags WHERE slug = :slug"), {"slug": slug})
        self.tags_cache[slug] = res.fetchone()[0]
        return self.tags_cache[slug]

    async def process_batch(self, file_paths: List[Path], base_path: Path) -> Dict[str, int]:
        stats = {'processed': 0, 'skipped': 0, 'errors': 0}
        
        async with async_session() as session:
            for path in file_paths:
                try:
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        raw_text = f.read()

                    content, metadata = self._parse_frontmatter(raw_text)

                    if 'redirect_to' in metadata or len(content) < MIN_CONTENT_LENGTH:
                        stats['skipped'] += 1
                        continue

                    doc_id = uuid.uuid4()
                    version_id = uuid.uuid4()
                    metadata_id = uuid.uuid4()
                    rel_path = str(path.relative_to(base_path)).replace("\\", "/")
                    
                    # Hierarchy Logic
                    parts = list(path.relative_to(base_path).parts)
                    root_folder = parts[0] if len(parts) > 0 else "Company"
                    
                    # Map to Division
                    div_name = self.dept_map.get(root_folder, "Executive & Corporate")
                    dept_id = self.departments_cache.get(div_name)
                    cat_id = self.categories_cache.get(root_folder)
                    
                    now = datetime.utcnow()
                    title = metadata.get('title', path.name)[:500]

                    # 1. Insert knowledge.documents
                    await session.execute(text("""
                        INSERT INTO knowledge.documents (
                            id, original_filename, file_type, file_size_bytes, mime_type,
                            file_key, status, current_version, language, 
                            chunking_strategy, uploaded_by, created_at, updated_at
                        ) VALUES (
                            :id, :filename, CAST('MD' AS knowledge.file_type), :size, 'text/markdown',
                            :key, CAST('READY' AS knowledge.processing_status), 1, 'en',
                            CAST('SEMANTIC' AS knowledge.chunking_strategy), :user_id, :now, :now
                        )
                    """), {
                        "id": doc_id, "filename": title,
                        "size": path.stat().st_size, "key": rel_path,
                        "user_id": self.user_id, "now": now
                    })

                    # 2. Insert metadata.document_metadata
                    await session.execute(text("""
                        INSERT INTO metadata.document_metadata (
                            id, document_id, title, description, document_type,
                            category_id, department_id, access_level, status,
                            current_version, created_by, updated_by, published_by,
                            published_at, effective_date, created_at, updated_at
                        ) VALUES (
                            :id, :doc_id, :title, :description, 'HANDBOOK',
                            :cat_id, :dept_id, CAST(:access_level AS metadata.access_level), CAST('PUBLISHED' AS metadata.document_status),
                            1, :user_id, :user_id, :user_id,
                            :now, :now_date, :now, :now
                        )
                    """), {
                        "id": metadata_id, "doc_id": doc_id, "title": title,
                        "description": metadata.get('description', '')[:1000],
                        "cat_id": cat_id, "dept_id": dept_id,
                        "user_id": self.user_id, "now": now, "now_date": now.date(),
                        "access_level": BASE_DATASET_ACCESS_LEVEL
                    })

                    # 2.5 Tags Extraction (Subfolders)
                    if len(parts) > 2: # e.g. engineering/backend/index.md -> tag: backend
                        for folder in parts[1:-1]:
                            tag_id = await self._get_or_create_tag(session, folder.replace("-", " ").title())
                            await session.execute(text("""
                                INSERT INTO metadata.document_tags (id, document_metadata_id, tag_id)
                                VALUES (:id, :doc_meta_id, :tag_id)
                                ON CONFLICT DO NOTHING
                            """), {"id": uuid.uuid4(), "doc_meta_id": metadata_id, "tag_id": tag_id})

                    # 3. Insert knowledge.document_versions
                    await session.execute(text("""
                        INSERT INTO knowledge.document_versions (
                            id, document_id, version_number, file_key, file_size_bytes, 
                            extracted_text, is_current, created_by, created_at
                        ) VALUES (
                            :id, :doc_id, 1, :key, :size,
                            :text, true, :user_id, :now
                        )
                    """), {
                        "id": version_id, "doc_id": doc_id, "key": rel_path,
                        "size": path.stat().st_size, "text": content,
                        "user_id": self.user_id, "now": now
                    })

                    # 4. Chunking & Embedding (Same as before)
                    structured = self.standardizer.normalize(content)
                    chunk_metadata = {
                        "document_id": str(doc_id),
                        "document_version_id": str(version_id),
                        "document_version": 1,
                        "access_level": BASE_DATASET_ACCESS_LEVEL,
                        "department_id": str(dept_id) if dept_id else None,
                        "allowed_departments": [str(dept_id)] if dept_id and BASE_DATASET_ACCESS_LEVEL != "PUBLIC" else [],
                        "allowed_roles": ["ADMIN"] if BASE_DATASET_ACCESS_LEVEL == "RESTRICTED" else [],
                    }
                    chunks = self.chunker.chunk(structured, chunk_metadata)

                    if chunks:
                        chunk_contents = [c.content for c in chunks]
                        all_embeddings = []
                        for j in range(0, len(chunk_contents), 4):
                            sub_embeddings = await embedding_service.embed_batch_cached(chunk_contents[j:j+4], session)
                            all_embeddings.extend(sub_embeddings)
                        
                        for idx, emb in enumerate(all_embeddings):
                            chunks[idx].embedding_vector = emb
                            chunks[idx].embedding_model, chunks[idx].embedding_dimension, chunks[idx].is_latest = "BGE_M3", 1024, True
                            if dept_id and BASE_DATASET_ACCESS_LEVEL != "PUBLIC":
                                chunks[idx].allowed_departments = [str(dept_id)]

                        await ChunkRepository(session).bulk_insert(chunks)
                    
                    stats['processed'] += 1

                except Exception as e:
                    logger.error(f"Error processing file {path}: {e}")
                    stats['errors'] += 1

            try:
                await session.commit()
            except Exception as e:
                logger.error(f"Commit failed for batch: {e}")
                await session.rollback()
                stats['errors'] += len(file_paths)
                
        return stats

if __name__ == "__main__":
    ingestor = HandbookIngestor()
    asyncio.run(ingestor.ingest_all())
