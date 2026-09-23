import asyncio
import asyncpg
import sys

async def main():
    # Force utf-8 stdout
    sys.stdout.reconfigure(encoding='utf-8')
    
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    # Query extracted_text from document_versions
    doc = await conn.fetchrow("""
        SELECT extracted_text, version_number 
        FROM knowledge.document_versions 
        WHERE document_id = '7d8427e1-f202-4c2e-8458-7c51bcdafe14'
        ORDER BY version_number DESC
        LIMIT 1
    """)
    
    if doc:
        text = doc['extracted_text'] or ""
        print(f"Document version: {doc['version_number']}, length: {len(text)}")
    else:
        text = ""
        print("No version found for document ID!")
    
    # Search for "Hear what"
    idx = text.lower().find("hear what")
    if idx != -1:
        print("\n--- Substring in full document text ---")
        sub = text[idx:idx+250]
        print(repr(sub))
        print("Chars:")
        for c in sub[:120]:
            print(f"{repr(c)} ({ord(c)})", end=" ")
        print()
    else:
        print("Not found in document!")
        
    # Search for chunk containing "Hear what"
    chunk = await conn.fetchrow("""
        SELECT content 
        FROM knowledge.chunks 
        WHERE content ILIKE '%Hear what%'
        LIMIT 1
    """)
    if chunk:
        print("\n--- Substring in chunk content ---")
        chunk_content = chunk['content']
        print(repr(chunk_content))
        print("Chars in chunk:")
        for c in chunk_content[:120]:
            print(f"{repr(c)} ({ord(c)})", end=" ")
        print()
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
