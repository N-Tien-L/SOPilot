-- ============================================================
-- FILE: 000_bootstrap.sql
-- PURPOSE: Create all application schemas
-- ============================================================

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS conversation;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Extensions are often needed by multiple schemas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
