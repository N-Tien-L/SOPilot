import asyncio
import asyncpg
import sys

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    # Search for any row in document_versions containing 'youtube.watch'
    rows = await conn.fetch("""
        SELECT id, document_id, version_number, extracted_text
        FROM knowledge.document_versions
        WHERE extracted_text ILIKE '%youtube.watch%'
    """)
    print(f"Found {len(rows)} matching versions for 'youtube.watch':")
    for r in rows:
        text = r['extracted_text'] or ""
        idx = text.lower().find("youtube.watch")
        print(f"ID: {r['id']} | DocID: {r['document_id']} | Version: {r['version_number']}")
        print(repr(text[idx-20:idx+60]))
        
        # Correct it
        old_str = "https://www.youtube.watch?v=gJWMBI64sZk"
        new_str = "https://www.youtube.com/watch?v=gJWMBI64sZk"
        if old_str in text:
            updated_text = text.replace(old_str, new_str)
            await conn.execute("""
                UPDATE knowledge.document_versions
                SET extracted_text = $1
                WHERE id = $2
            """, updated_text, r['id'])
            print("Successfully updated!")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
