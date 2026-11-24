#!/bin/sh
# Runs once, on a fresh V2 Postgres volume (docker-entrypoint-initdb.d).
# Creates the migration owner and the two application roles (TECH-V2-core-api §4.1).
# Application roles own nothing and cannot bypass RLS, so row-level security applies to them.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator_pw="$V2_DB_MIGRATOR_PASSWORD" \
  -v core_pw="$V2_DB_CORE_APP_PASSWORD" \
  -v ai_pw="$V2_DB_AI_APP_PASSWORD" <<'SQL'
CREATE ROLE sopilot_migrator LOGIN PASSWORD :'migrator_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sopilot_core_app LOGIN PASSWORD :'core_pw'     NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE sopilot_ai_app   LOGIN PASSWORD :'ai_pw'       NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

REVOKE ALL ON DATABASE sopilot FROM PUBLIC;
GRANT CONNECT ON DATABASE sopilot TO sopilot_migrator, sopilot_core_app, sopilot_ai_app;
-- Flyway creates the core and rag schemas, so they are owned by the migrator.
GRANT CREATE ON DATABASE sopilot TO sopilot_migrator;

-- Extensions need superuser; created once here, in public, usable by every role.
CREATE EXTENSION IF NOT EXISTS vector;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
