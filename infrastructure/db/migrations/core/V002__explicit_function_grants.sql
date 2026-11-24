-- V2-08 review: schema-local REVOKE cannot undo PostgreSQL's global PUBLIC EXECUTE.
-- Apply a global default for this creator, then repair already-created helpers.
-- Both Flyway chains use the same creator; serialize the global default change.
SELECT pg_advisory_xact_lock(24082026);
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION core.current_workspace(), core.current_app_user(), core.touch_updated_at()
    FROM PUBLIC;
-- Existing grants to sopilot_core_app in V001 are retained.
