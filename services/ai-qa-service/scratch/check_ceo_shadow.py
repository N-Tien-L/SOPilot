import asyncio
import asyncpg

async def check_ceo_shadow():
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    try:
        conn = await asyncpg.connect(database_url)
        print("Connected to DB successfully!")
        
        # Let's inspect column names first
        columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'knowledge' AND table_name = 'documents'
        """)
        print("\nColumns in knowledge.documents:")
        print([c['column_name'] for c in columns])
        
        # Search across all documents in knowledge.documents for 'Hear what'
        found_docs = await conn.fetch("""
            SELECT id, original_filename, char_length(extracted_text) as len
            FROM knowledge.documents
            WHERE extracted_text ILIKE '%Hear what%'
        """)
        print("\nDocuments containing 'Hear what':")
        for fd in found_docs:
            print(f"- ID: {fd['id']} | Filename: {fd['original_filename']} | Length: {fd['len']}")
            
        # Search across all chunks in knowledge.chunks for 'Hear what'
        found_chunks = await conn.fetch("""
            SELECT id, document_id, section_title, content
            FROM knowledge.chunks
            WHERE content ILIKE '%Hear what%'
        """)
        print("\nChunks containing 'Hear what':")
        for fc in found_chunks:
            print(f"- ID: {fc['id']} | Doc ID: {fc['document_id']} | Section: {fc['section_title']}")
            print(f"  Content: {repr(fc['content'])}")
            
            # Print the document content for this chunk's document around the chunk content
            doc = await conn.fetchrow("""
                SELECT extracted_text 
                FROM knowledge.documents 
                WHERE id = $1
            """, fc['document_id'])
            if doc and doc['extracted_text']:
                idx = doc['extracted_text'].lower().find("hear what")
                if idx != -1:
                    print("\nDocument extracted_text around chunk:")
                    print(repr(doc['extracted_text'][idx:idx+300]))
                else:
                    print("NOT found in document extracted_text!")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_ceo_shadow())
