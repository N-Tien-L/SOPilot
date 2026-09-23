-- ============================================================
-- METADATA SCHEMA RETRIEVAL SCRIPTS
-- Purpose: Querying categories, tags, and document permissions
-- ============================================================

-- 1. Find all active categories
SELECT id, name, slug, icon, display_order 
FROM metadata.categories 
WHERE is_active = TRUE AND deleted_at IS NULL
ORDER BY display_order ASC;

-- 2. Popular tags by usage count
SELECT name, slug, usage_count 
FROM metadata.tags 
WHERE deleted_at IS NULL
ORDER BY usage_count DESC 
LIMIT 20;

-- 3. Document metadata with owning department and category
SELECT 
    dm.title, 
    dm.status, 
    dm.access_level,
    c.name as category_name,
    d.name as department_name,
    dm.published_at
FROM metadata.document_metadata dm
LEFT JOIN metadata.categories c ON dm.category_id = c.id
LEFT JOIN core.departments d ON dm.department_id = d.id
WHERE dm.deleted_at IS NULL
ORDER BY dm.created_at DESC;

-- 4. Check specific access rules for a document
-- Replace :doc_meta_id with actual UUID
SELECT 
    target_type, 
    target_role, 
    permission,
    created_at
FROM metadata.document_access_rules
WHERE document_metadata_id = 'REPLACE_WITH_UUID'
ORDER BY created_at;

-- 5. List all published documents and their tags
SELECT 
    dm.title,
    string_agg(t.name, ', ') as tags_list
FROM metadata.document_metadata dm
LEFT JOIN metadata.document_tags dt ON dm.id = dt.document_metadata_id
LEFT JOIN metadata.tags t ON dt.tag_id = t.id
WHERE dm.status = 'PUBLISHED' AND dm.deleted_at IS NULL
GROUP BY dm.id, dm.title;
