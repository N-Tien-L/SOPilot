-- V2-29: refresh-token rotation and workspace soft delete (TECH-V2-core-api §3.1, §5.1, §5.2).
-- Runs as sopilot_migrator. Additive only.

-- Rotating refresh tokens. Only the SHA-256 of the 256-bit random token is stored. The table is
-- global (no RLS, TECH §3.1): it is read by token_hash during refresh, before the workspace is known.
-- Reusing a token that was already exchanged revokes the whole family.
CREATE TABLE core.refresh_tokens (
    id             uuid PRIMARY KEY,
    user_id        uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    -- Deliberately not named workspace_id: the table is global (looked up by token_hash before any workspace is
    -- known), so it must not look like a tenant table to the isolation suite (reviewed in GLOBAL_TABLES).
    target_workspace_id uuid NOT NULL,            -- workspace of the access token this chain issues
    family_id      uuid NOT NULL,
    token_hash     bytea NOT NULL UNIQUE,
    expires_at     timestamptz NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    used_at        timestamptz,
    revoked_at     timestamptz,
    revoked_reason text CHECK (revoked_reason IN
        ('LOGOUT','REUSE_DETECTED','MEMBERSHIP_LOST','SUSPENDED','EXPIRED_FAMILY'))
);
CREATE INDEX ix_refresh_tokens_family ON core.refresh_tokens(family_id);
-- Revoking every chain of one membership (suspend, remove, leave, workspace delete).
CREATE INDEX ix_refresh_tokens_membership ON core.refresh_tokens(user_id, target_workspace_id);

-- Workspace delete is soft: the row stays until ai-service confirmed that every document is gone.
ALTER TABLE core.workspaces ADD COLUMN deleted_at timestamptz;
