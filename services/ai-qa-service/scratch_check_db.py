import asyncio
import asyncpg
import os
from uuid import UUID

async def check_db():
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    # Use localhost if running from outside docker, but this script will run on host
    # Wait, the user is on Windows. I can't easily connect to the docker postgres from here 
    # unless port 5432 is mapped.
    # It is: ports: ["5432:5432"] in docker-compose? Let's check.
    
    conn = await asyncpg.connect(database_url)
    try:
        print("Connected to DB")
        rows = await conn.fetch("SELECT * FROM conversation.conversations LIMIT 5")
        for row in rows:
            print(dict(row))
            
        count = await conn.fetchval("SELECT COUNT(*) FROM conversation.conversations")
        print(f"Total conversations: {count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_db())
