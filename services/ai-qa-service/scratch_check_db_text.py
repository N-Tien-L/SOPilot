import asyncio
import asyncpg
import json

async def check_docs():
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    try:
        conn = await asyncpg.connect(database_url)
        print("Connected to database!")
        
        # Check columns of knowledge.documents
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'knowledge' AND table_name = 'documents'
        """)
        print("\nColumns in knowledge.documents:")
        for col in columns:
            print(f"- {col['column_name']}: {col['data_type']}")
            
        # Check if there is extracted_text in knowledge.documents
        rows = await conn.fetch("""
            SELECT id, original_filename, 
                   (extracted_text IS NOT NULL) as has_text, 
                   LENGTH(extracted_text) as text_len
            FROM knowledge.documents 
            WHERE extracted_text IS NOT NULL AND LENGTH(extracted_text) > 0
            LIMIT 5
        """)
        print(f"\nDocuments with extracted_text in knowledge.documents: {len(rows)}")
        for r in rows:
            print(f"- ID: {r['id']} | Filename: {r['original_filename']} | Has Text: {r['has_text']} | Length: {r['text_len']}")

        # Check in knowledge.document_versions
        v_rows = await conn.fetch("""
            SELECT id, document_id, version_number,
                   (extracted_text IS NOT NULL) as has_text, 
                   LENGTH(extracted_text) as text_len
            FROM knowledge.document_versions
            WHERE extracted_text IS NOT NULL AND LENGTH(extracted_text) > 0
            LIMIT 5
        """)
        print(f"\nVersions with extracted_text in knowledge.document_versions: {len(v_rows)}")
        for r in v_rows:
            print(f"- ID: {r['id']} | DocID: {r['document_id']} | Has Text: {r['has_text']} | Length: {r['text_len']}")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_docs())
