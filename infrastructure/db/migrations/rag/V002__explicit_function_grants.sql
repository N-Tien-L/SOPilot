-- Each Flyway chain must be safe independently of the other chain's ordering.
SELECT pg_advisory_xact_lock(24082026);
ALTER DEFAULT PRIVILEGES FOR ROLE sopilot_migrator
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION rag.current_workspace(), rag.current_app_user(), rag.touch_updated_at()
    FROM PUBLIC;
-- Existing grants to sopilot_ai_app in V001 are retained.
