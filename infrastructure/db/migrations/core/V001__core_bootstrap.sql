-- V2 core schema bootstrap (TECH-V2-core-api §3, §4). Runs as sopilot_migrator, which owns the schema.
-- Tables come in later migrations (V2-11 onwards); this file sets privileges and shared helpers.

REVOKE ALL ON SCHEMA core FROM PUBLIC;
GRANT USAGE ON SCHEMA core TO sopilot_core_app;

-- Every table the migrator creates here is usable (not owned) by core-api.
-- audit_logs revokes UPDATE/DELETE in its own migration.
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA core
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sopilot_core_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA core
    GRANT USAGE, SELECT ON SEQUENCES TO sopilot_core_app;
-- Functions are not executable by PUBLIC by default; each one is granted explicitly
-- (SECURITY DEFINER helpers must stay out of reach of other roles).
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA core
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Tenant context set per transaction with set_config(..., true). Unset or empty means NULL,
-- so RLS predicates match no rows (fail closed).
CREATE FUNCTION core.current_workspace() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$;

CREATE FUNCTION core.current_app_user() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION core.touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

GRANT EXECUTE ON FUNCTION core.current_workspace(), core.current_app_user(), core.touch_updated_at()
    TO sopilot_core_app;
