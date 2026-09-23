import asyncio
import asyncpg
import json
import sys

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    # Query latest assistant message with sources
    row = await conn.fetchrow("""
        SELECT id, content, sources 
        FROM conversation.messages 
        WHERE role = 'ASSISTANT' AND sources IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
    """)
    
    if not row:
        print("No assistant messages with sources found!")
        await conn.close()
        return
        
    print(f"Message ID: {row['id']}")
    print(f"Message Content: {repr(row['content'][:150])}...")
    
    sources = row['sources']
    if isinstance(sources, str):
        sources = json.loads(sources)
        
    print("\n--- Sources JSON ---")
    print(json.dumps(sources, indent=2, ensure_ascii=False))
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
