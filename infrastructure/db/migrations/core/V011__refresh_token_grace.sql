-- V2-39: refresh-token grace window (TECH-V2-core-api §5.1 step 2). Runs as sopilot_migrator. Additive only.
-- A token that was exchanged a few seconds ago may be presented once more (a reload aborted the response that
-- carried the successor). successor_id points at the token issued by the exchange so the service can tell
-- whether the successor was already used; it is cleared once the grace was spent. The column holds no secret.
ALTER TABLE core.refresh_tokens ADD COLUMN successor_id uuid REFERENCES core.refresh_tokens(id) ON DELETE SET NULL;
