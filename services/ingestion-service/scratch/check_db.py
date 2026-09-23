import asyncio
from sqlalchemy import text
from src.db.session import engine

async def check_latest_ingestion():
    async with engine.connect() as conn:
        # 1. Kiểm tra 5 chunks mới nhất
        query = text("""
            SELECT 
                document_id, 
                chunk_index, 
                chunk_type, 
                content_length, 
                left(content, 50) as content_preview,
                (embedding_vector IS NOT NULL) as has_embedding,
                metadata
            FROM knowledge.chunks
            ORDER BY created_at DESC
            LIMIT 5;
        """)
        
        result = await conn.execute(query)
        rows = result.all()
        
        if not rows:
            print("❌ Không tìm thấy dữ liệu nào trong bảng knowledge.chunks.")
            return

        print(f"✅ Tìm thấy {len(rows)} bản ghi mới nhất:")
        print("-" * 100)
        for row in rows:
            print(f"Doc ID: {row.document_id}")
            print(f"Index: {row.chunk_index} | Type: {row.chunk_type} | Length: {row.content_length}")
            print(f"Embedding: {'✅ Có' if row.has_embedding else '❌ Không'}")
            print(f"Preview: {row.content_preview}...")
            print("-" * 100)

if __name__ == "__main__":
    asyncio.run(check_latest_ingestion())
