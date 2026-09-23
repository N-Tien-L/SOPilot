import asyncio
import asyncpg

async def check_docs():
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    try:
        conn = await asyncpg.connect(database_url)
        print("Successfully connected to the database!")
        
        # Query documents from knowledge schema
        rows = await conn.fetch("""
            SELECT id, original_filename, status, current_version 
            FROM knowledge.documents 
            LIMIT 10
        """)
        print("\nDocuments in knowledge.documents (First 10):")
        for row in rows:
            print(f"- ID: {row['id']}")
            print(f"  Filename: {row['original_filename']}")
            print(f"  Status: {row['status']} | Version: {row['current_version']}")
            
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge.documents")
        print(f"\nTotal documents in knowledge.documents: {count}")
        
        # Let's also check if 'confidentiality-levels.md' or 'chat.md' are present in original_filename
        specific_docs = await conn.fetch("""
            SELECT id, original_filename, status
            FROM knowledge.documents
            WHERE original_filename ILIKE '%confidentiality%' OR original_filename ILIKE '%communication%' OR original_filename ILIKE '%chat%'
        """)
        print("\nSpecific targeted documents in knowledge.documents:")
        for row in specific_docs:
            print(f"- ID: {row['id']} | Filename: {row['original_filename']} | Status: {row['status']}")
            
        # Let's join with document_metadata
        metadata_rows = await conn.fetch("""
            SELECT dm.id, dm.title, d.original_filename, dm.status, dm.access_level
            FROM metadata.document_metadata dm
            JOIN knowledge.documents d ON d.id = dm.document_id
            LIMIT 10
        """)
        print("\nDocument Metadata joined with Documents:")
        for row in metadata_rows:
            print(f"- Title: {row['title']}")
            print(f"  Filename: {row['original_filename']}")
            print(f"  Status: {row['status']} | Access: {row['access_level']}")
            
        await conn.close()
    except Exception as e:
        print(f"Error querying DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_docs())
