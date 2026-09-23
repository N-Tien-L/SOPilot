-- ============================================================
-- Combined init script for Poliwise database
-- ============================================================

\i /docker-entrypoint-initdb.d/init-db/000_bootstrap.sql
\i /docker-entrypoint-initdb.d/init-db/001_core.sql
\i /docker-entrypoint-initdb.d/init-db/002_metadata.sql
\i /docker-entrypoint-initdb.d/init-db/003_knowledge.sql
\i /docker-entrypoint-initdb.d/init-db/004_conversation.sql
\i /docker-entrypoint-initdb.d/init-db/005_analytics.sql
\i /docker-entrypoint-initdb.d/init-db/006_functions_triggers.sql
\i /docker-entrypoint-initdb.d/init-db/007_seed_data.sql
\i /docker-entrypoint-initdb.d/init-db/008_ai_indexes.sql
\i /docker-entrypoint-initdb.d/init-db/009_document_locks.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/001_bm25_simple_dictionary.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/001_add_document_type_column.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/002_fk_constraints_and_improvements.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/003_onlyoffice_document_locks.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/004_add_password_reset_otp.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/005_add_password_reset_tokens.sql
\i /docker-entrypoint-initdb.d/init-db/migrations/010_user_violations_and_warnings.sql

-- Seed data
\i /docker-entrypoint-initdb.d/seed/seed_data.sql

SELECT 'Database initialization complete!' AS status;
