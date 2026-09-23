#!/usr/bin/env python3
"""Clear database and re-run ingestion script."""

import os
import sys
import asyncio
import asyncpg
from pathlib import Path

# Add parent directory to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from src.config.settings import settings

CLEAR_DB_SQL = """
-- Clear all ingestion-related data
DELETE FROM knowledge.embedding_cache;
DELETE FROM knowledge.processing_jobs;
DELETE FROM knowledge.chunks;
DELETE FROM knowledge.document_versions;
DELETE FROM knowledge.documents;
DELETE FROM metadata.document_tags;
DELETE FROM metadata.document_access_rules;
DELETE FROM metadata.document_metadata;
DELETE FROM metadata.categories;
DELETE FROM metadata.tags;
DELETE FROM core.user_profiles WHERE user_id = '00000000-0000-0000-0000-000000000001';
DELETE FROM core.users WHERE id = '00000000-0000-0000-0000-000000000001';
"""

async def clear_database():
    """Clear all ingestion data from the database."""
    print("🗑️  Connecting to database...")
    
    # Convert asyncpg URL to sync format for connection
    db_url = settings.database_url.replace('+asyncpg', '')
    
    conn = await asyncpg.connect(db_url)
    
    try:
        print("🧹 Clearing knowledge, metadata, and core tables...")
        await conn.execute(CLEAR_DB_SQL)
        print("✅ Database cleared successfully!")
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        raise
    finally:
        await conn.close()

async def main():
    """Clear DB and run ingestion."""
    print("=" * 60)
    print("🚀 Database Clear & Re-Ingestion Script")
    print("=" * 60)
    
    # Step 1: Clear database
    await clear_database()
    
    # Step 2: Run ingestion
    print("\n" + "=" * 60)
    print("📥 Starting ingestion...")
    print("=" * 60 + "\n")
    
    from src.scripts.ingest_base_dataset import HandbookIngestor
    
    ingestor = HandbookIngestor()
    await ingestor.ingest_all()
    
    print("\n" + "=" * 60)
    print("✨ All done!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
