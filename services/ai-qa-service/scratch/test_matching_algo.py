import asyncio
import asyncpg
import sys

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    database_url = "postgresql://poliwise:poliwise_secure_password@localhost:5432/poliwise"
    conn = await asyncpg.connect(database_url)
    
    # Fetch full text of CEO Shadow Program document
    doc = await conn.fetchrow("""
        SELECT extracted_text 
        FROM knowledge.document_versions 
        WHERE document_id = '7d8427e1-f202-4c2e-8458-7c51bcdafe14'
        ORDER BY version_number DESC
        LIMIT 1
    """)
    content = doc['extracted_text'] or ""
    
    # Fetch the chunk containing "Hear what"
    chunk = await conn.fetchrow("""
        SELECT content 
        FROM knowledge.chunks 
        WHERE document_id = '7d8427e1-f202-4c2e-8458-7c51bcdafe14' AND content ILIKE '%Hear what%'
        LIMIT 1
    """)
    excerpt = chunk['content']
    
    print("Original Content length:", len(content))
    print("Original Excerpt length:", len(excerpt))
    
    # --- IMPLEMENT THE STRIPPED MATCHING ALGORITHM IN PYTHON ---
    # 1. Clean query
    clean_query = excerpt.strip()
    stripped_query = "".join(clean_query.split()).lower()
    
    # 2. Build charMap for content
    char_map = []
    for i, c in enumerate(content):
        if not c.isspace():
            char_map.append({"char": c.lower(), "orig_idx": i})
            
    stripped_content = "".join([cm["char"] for cm in char_map])
    
    print("\nStripped Query length:", len(stripped_query))
    print("Stripped Content length:", len(stripped_content))
    
    # Try match
    match_idx = stripped_content.find(stripped_query)
    matched_length = len(stripped_query)
    
    if match_idx == -1:
        print("Full match failed! Trying 80-char prefix...")
        prefix = stripped_query[:80]
        match_idx = stripped_content.find(prefix)
        matched_length = len(prefix)
        
    if match_idx != -1:
        start_orig = char_map[match_idx]["orig_idx"]
        end_orig = char_map[match_idx + matched_length - 1]["orig_idx"] + 1
        print(f"\nMatch found!")
        print(f"Original Indices: [{start_orig}, {end_orig}]")
        print("Matched Text in original content:")
        print(repr(content[start_orig:end_orig]))
    else:
        print("\nNo match found at all!")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
