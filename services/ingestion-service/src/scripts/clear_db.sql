-- Clear all ingestion-related data from knowledge and metadata schemas
-- This script resets data seeded by ingest_base_dataset.py

-- Clear knowledge schema tables (in correct order to respect foreign keys)
DELETE FROM knowledge.embedding_cache;
DELETE FROM knowledge.processing_jobs;
DELETE FROM knowledge.chunks;
DELETE FROM knowledge.document_versions;
DELETE FROM knowledge.documents;

-- Clear metadata schema tables
DELETE FROM metadata.document_tags;
DELETE FROM metadata.document_access_rules;
DELETE FROM metadata.document_metadata;

-- Clear categories and tags seeded by ingestion
DELETE FROM metadata.categories;
DELETE FROM metadata.tags;

-- Clear departments seeded by ingestion (keep if they exist from other sources)
-- DELETE FROM core.departments WHERE code IN ('ENGINEERING_AND_PROD', 'INFRASTRUCTURE_AND_', 'SALES_AND_MARKETING', 'PEOPLE_AND_LEGAL', 'EXECUTIVE_AND_CORP');

-- Clear admin user created by ingestion (optional - comment out if you want to keep it)
DELETE FROM core.user_profiles WHERE user_id = '00000000-0000-0000-0000-000000000001';
DELETE FROM core.users WHERE id = '00000000-0000-0000-0000-000000000001';

-- Reset sequences if any (PostgreSQL auto-increment sequences)
-- This ensures IDs start fresh
