import asyncio
import asyncpg
import sys

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    row = await conn.fetchrow("""
        SELECT extracted_text 
        FROM knowledge.documents 
        WHERE id = '7d8427e1-f202-4c2e-8458-7c51bcdafe14'
    """)
    if row and row['extracted_text']:
        text = row['extracted_text']
        print(f"Documents Table Text Length: {len(text)}")
        idx = text.lower().find("youtube")
        if idx != -1:
            print(repr(text[idx-20:idx+80]))
        else:
            print("No 'youtube' found!")
    else:
        print("Documents table extracted_text is empty!")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
