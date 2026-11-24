-- V2 rag schema bootstrap (TECH-V2-ai-service §3). Runs as sopilot_migrator, which owns the schema.
-- Tables come in later migrations (V2-09 onwards); this file sets privileges and shared helpers.

REVOKE ALL ON SCHEMA rag FROM PUBLIC;
GRANT USAGE ON SCHEMA rag TO sopilot_ai_app;

ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sopilot_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA rag
    GRANT USAGE, SELECT ON SEQUENCES TO sopilot_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator IN SCHEMA rag
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

CREATE FUNCTION rag.current_workspace() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$;

CREATE FUNCTION rag.current_app_user() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION rag.touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

GRANT EXECUTE ON FUNCTION rag.current_workspace(), rag.current_app_user(), rag.touch_updated_at()
    TO sopilot_ai_app;
