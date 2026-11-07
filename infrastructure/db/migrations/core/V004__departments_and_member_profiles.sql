-- V2-23: flat departments, member profile fields and the invitation table (TECH-V2-core-api §3.2,
-- ADR-007 §4.1-4.3). Runs as sopilot_migrator. Invitation endpoints and acceptance are V2-30; the
-- table exists now because deleting a department must be refused while an invitation points at it.

CREATE TABLE core.departments (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)                     -- two-column FK target: a department belongs to one workspace
);
CREATE UNIQUE INDEX uq_department_name ON core.departments(workspace_id, lower(name));

ALTER TABLE core.memberships
    ADD COLUMN employee_code text CHECK (employee_code IS NULL OR length(trim(employee_code)) BETWEEN 1 AND 50),
    ADD COLUMN job_title     text CHECK (job_title IS NULL OR length(trim(job_title)) BETWEEN 1 AND 100);
ALTER TABLE core.memberships
    ADD CONSTRAINT fk_membership_department FOREIGN KEY (workspace_id, department_id)
        REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT;
CREATE UNIQUE INDEX uq_membership_employee_code ON core.memberships(workspace_id, employee_code)
    WHERE employee_code IS NOT NULL;
CREATE INDEX ix_memberships_department ON core.memberships(workspace_id, department_id)
    WHERE department_id IS NOT NULL;

CREATE TABLE core.invitations (
    id            uuid PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    email         text NOT NULL CHECK (email = lower(email)),
    role          text NOT NULL CHECK (role IN ('ADMIN','MEMBER')),   -- never invite straight to OWNER
    display_name  text,
    employee_code text,
    job_title     text,
    department_id uuid,
    token_hash    bytea NOT NULL UNIQUE,
    invited_by    uuid NOT NULL REFERENCES core.users(id),
    expires_at    timestamptz NOT NULL,
    accepted_at   timestamptz,
    accepted_by   uuid REFERENCES core.users(id),
    revoked_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- SET NULL (not RESTRICT): used or revoked invitations are history and must not pin a department.
    -- DepartmentService refuses deleting a department while a *pending* invitation still names it.
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id)
        ON DELETE SET NULL (department_id)
);
CREATE UNIQUE INDEX uq_pending_invitation ON core.invitations(workspace_id, email)
    WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TRIGGER trg_departments_updated_at BEFORE UPDATE ON core.departments
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

ALTER TABLE core.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.departments FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.departments
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

ALTER TABLE core.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.invitations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.invitations
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());
