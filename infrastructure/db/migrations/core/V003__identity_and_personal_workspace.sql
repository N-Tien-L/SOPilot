-- V2-11: global identity, workspaces and memberships (TECH-V2-core-api §3.1, §3.2, §4.2).
-- Runs as sopilot_migrator. Refresh tokens (V2-29), departments and member profile fields
-- (V2-23), invitations and domains (V2-30) come in later migrations.

-- Global identity: no workspace_id, no RLS. core-api is the only writer (A7).
CREATE TABLE core.users (
    id                       uuid PRIMARY KEY,
    email                    text NOT NULL CHECK (email = lower(email)),
    display_name             text,
    avatar_url               text,
    last_active_workspace_id uuid,            -- no FK: avoids a cycle when a workspace is deleted
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
-- email is not unique: identity is (issuer, subject); email is an attribute (ADR-005 §4.1).

CREATE TABLE core.external_identities (
    id            uuid PRIMARY KEY,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    issuer        text NOT NULL CHECK (length(trim(issuer)) > 0),
    subject       text NOT NULL CHECK (length(trim(subject)) > 0),
    email_at_link text NOT NULL,
    hosted_domain text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_external_identity_user UNIQUE (user_id, issuer)
);

CREATE TABLE core.workspaces (
    id         uuid PRIMARY KEY,
    name       text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    kind       text NOT NULL CHECK (kind IN ('PERSONAL','TEAM')),
    created_by uuid NOT NULL REFERENCES core.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- Exactly one PERSONAL workspace per user (FR-02, idempotent JIT).
CREATE UNIQUE INDEX uq_personal_workspace ON core.workspaces(created_by) WHERE kind = 'PERSONAL';

-- department_id gets its composite FK to core.departments in V2-23; profile fields
-- (employee_code, job_title) are added there too.
CREATE TABLE core.memberships (
    workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    role          text NOT NULL CHECK (role IN ('OWNER','ADMIN','MEMBER')),
    status        text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED')),
    display_name  text,
    email         text NOT NULL CHECK (email = lower(email)),
    department_id uuid,
    suspended_at  timestamptz,
    joined_at     timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id),
    CHECK ((status = 'SUSPENDED') = (suspended_at IS NOT NULL))
);
CREATE INDEX ix_memberships_user ON core.memberships(user_id);

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER trg_workspaces_updated_at BEFORE UPDATE ON core.workspaces
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER trg_memberships_updated_at BEFORE UPDATE ON core.memberships
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

-- Tenant isolation (TECH §4.2). Unset app.workspace_id / app.user_id match no rows.
ALTER TABLE core.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.workspaces FORCE ROW LEVEL SECURITY;
ALTER TABLE core.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.memberships FORCE ROW LEVEL SECURITY;

-- Own memberships in every workspace (to list "my workspaces"), or all in the current one.
CREATE POLICY membership_visibility ON core.memberships
    USING (workspace_id = core.current_workspace() OR user_id = core.current_app_user())
    WITH CHECK (workspace_id = core.current_workspace());

CREATE POLICY workspace_visibility ON core.workspaces
    USING (id = core.current_workspace()
           OR EXISTS (SELECT 1 FROM core.memberships m
                      WHERE m.workspace_id = id AND m.user_id = core.current_app_user()))
    WITH CHECK (id = core.current_workspace());

-- FORCE RLS also binds the table owner, so SECURITY DEFINER helpers (owned by the migrator)
-- need their own policy. The migrator already owns these tables and could disable RLS, so this
-- grants it nothing new; sopilot_core_app is unaffected.
CREATE POLICY definer_access ON core.workspaces TO sopilot_migrator
    USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.memberships TO sopilot_migrator
    USING (true) WITH CHECK (true);

-- JIT (FR-02): create the user's PERSONAL workspace and OWNER membership, or return the
-- existing one. Called before the token carries a wid, so it runs as the owner (TECH §4.2).
-- p_workspace_id is the application-generated UUIDv7 used only when nothing exists yet.
CREATE FUNCTION core.create_personal_workspace(p_user_id uuid, p_workspace_id uuid,
                                               p_name text, p_email text)
    RETURNS uuid
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$
DECLARE
    v_id uuid;
BEGIN
    INSERT INTO core.workspaces (id, name, kind, created_by)
    VALUES (p_workspace_id, p_name, 'PERSONAL', p_user_id)
    ON CONFLICT (created_by) WHERE kind = 'PERSONAL' DO NOTHING;

    SELECT id INTO STRICT v_id FROM core.workspaces
    WHERE created_by = p_user_id AND kind = 'PERSONAL';

    INSERT INTO core.memberships (workspace_id, user_id, role, status, display_name, email)
    SELECT v_id, u.id, 'OWNER', 'ACTIVE', u.display_name, lower(p_email)
    FROM core.users u WHERE u.id = p_user_id
    ON CONFLICT (workspace_id, user_id) DO NOTHING;

    RETURN v_id;
END $$;

REVOKE EXECUTE ON FUNCTION core.create_personal_workspace(uuid, uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.create_personal_workspace(uuid, uuid, text, text) TO sopilot_core_app;
