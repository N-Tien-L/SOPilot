import asyncio
import asyncpg

async def clear():
    conn = await asyncpg.connect('postgresql://poliwise:poliwise_secure_password@postgres:5432/poliwise')
    await conn.execute("""
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
    """)
    print('✅ Database cleared!')
    await conn.close()

asyncio.run(clear())
