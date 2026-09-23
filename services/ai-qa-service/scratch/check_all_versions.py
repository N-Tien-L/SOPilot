import asyncio
import asyncpg
import sys

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    doc_ids = ['69f5c2d5-a117-4f21-8661-170e1ff5c77d', '7d8427e1-f202-4c2e-8458-7c51bcdafe14']
    for doc_id in doc_ids:
        r = await conn.fetchrow("""
            SELECT extracted_text
            FROM knowledge.document_versions
            WHERE document_id = $1 AND version_number = 1
        """, doc_id)
        if r:
            text = r['extracted_text'] or ""
            idx = text.lower().find("youtube")
            print(f"\nDocument ID: {doc_id}")
            if idx != -1:
                print(repr(text[idx-20:idx+80]))
            else:
                print("No 'youtube' found!")
        else:
            print(f"No text found for {doc_id}!")
            
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
