-- V2-36: department and workspace publishers, document owner department (ADR-009, TECH-V2-core-api §15.2).
-- Runs as sopilot_migrator. Additive only. The write permission on documents moves from OWNER/ADMIN to the
-- publisher of the owning department (visibility DEPARTMENTS) or of the workspace (visibility WORKSPACE).
-- Read access, token claims and ai-service are unchanged.

-- At most one publisher per department. Both FKs are two-column so the department and the member must
-- belong to the same workspace as this row.
CREATE TABLE core.department_publishers (
    workspace_id  uuid NOT NULL,
    department_id uuid PRIMARY KEY,
    user_id       uuid NOT NULL,
    assigned_at   timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE CASCADE,
    -- Leaving or being removed from the workspace ends the role at once (ADR-009 §4.1).
    FOREIGN KEY (workspace_id, user_id) REFERENCES core.memberships(workspace_id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_department_publishers_user ON core.department_publishers(workspace_id, user_id);

-- At most one publisher per workspace, for documents with visibility WORKSPACE (ADR-009 §6 Q0).
CREATE TABLE core.workspace_publishers (
    workspace_id uuid PRIMARY KEY,
    user_id      uuid NOT NULL,
    assigned_at  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, user_id) REFERENCES core.memberships(workspace_id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_workspace_publishers_user ON core.workspace_publishers(workspace_id, user_id);

ALTER TABLE core.department_publishers ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.department_publishers FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.department_publishers
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

ALTER TABLE core.workspace_publishers ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.workspace_publishers FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.workspace_publishers
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

-- FORCE RLS also binds the table owner. This migration (backfill below) and core.create_personal_workspace
-- run as the owner, so they need their own policy on the tables they touch (see V003). The migrator already
-- owns these tables and could disable RLS, so this grants it nothing new; sopilot_core_app is unaffected.
CREATE POLICY definer_access ON core.department_publishers TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.workspace_publishers TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.documents TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.document_departments TO sopilot_migrator USING (true) WITH CHECK (true);

-- Owning department of a document.
ALTER TABLE core.documents ADD COLUMN owner_department_id uuid;

-- Backfill (ADR-009 §4.4, §6 Q6). Documents limited to departments get the owner by the rule
--   one department          -> that department
--   several departments     -> the department of the first version's uploader if it is in scope,
--                              otherwise the smallest lower(name)
-- Documents in several departments are listed in the Flyway log so the OWNER can review them.
DO $$
DECLARE
    v_multi record;
    v_empty bigint;
BEGIN
    -- The application never creates a DEPARTMENTS document without a department, but manual SQL or a seed could.
    -- Such a row has no owner to backfill and would fail the CHECK below; stop here with a readable message.
    SELECT count(*) INTO v_empty
      FROM core.documents d
     WHERE d.visibility = 'DEPARTMENTS'
       AND NOT EXISTS (SELECT 1 FROM core.document_departments dd
                        WHERE dd.workspace_id = d.workspace_id AND dd.document_id = d.id);
    IF v_empty > 0 THEN
        RAISE EXCEPTION 'V009: % document(s) have visibility DEPARTMENTS but no department; fix or delete them, then rerun',
            v_empty;
    END IF;

    FOR v_multi IN
        SELECT d.workspace_id, d.id
          FROM core.documents d
         WHERE d.visibility = 'DEPARTMENTS'
           AND (SELECT count(*) FROM core.document_departments dd
                 WHERE dd.workspace_id = d.workspace_id AND dd.document_id = d.id) > 1
    LOOP
        RAISE NOTICE 'V009: document % (workspace %) is limited to several departments; owner chosen by rule Q6',
            v_multi.id, v_multi.workspace_id;
    END LOOP;
END $$;

-- The backfill is not an edit by a person: keep updated_at as it was.
ALTER TABLE core.documents DISABLE TRIGGER trg_documents_updated_at;
UPDATE core.documents d
   SET owner_department_id = COALESCE(
        (SELECT m.department_id
           FROM core.document_versions v
           JOIN core.memberships m ON m.workspace_id = v.workspace_id AND m.user_id = v.uploaded_by
           JOIN core.document_departments dd ON dd.workspace_id = d.workspace_id AND dd.document_id = d.id
                                            AND dd.department_id = m.department_id
          WHERE v.workspace_id = d.workspace_id AND v.document_id = d.id AND v.version_no = 1),
        (SELECT dd.department_id
           FROM core.document_departments dd
           JOIN core.departments dep ON dep.workspace_id = dd.workspace_id AND dep.id = dd.department_id
          WHERE dd.workspace_id = d.workspace_id AND dd.document_id = d.id
          ORDER BY lower(dep.name), dep.id
          LIMIT 1))
 WHERE d.visibility = 'DEPARTMENTS';
ALTER TABLE core.documents ENABLE TRIGGER trg_documents_updated_at;

-- Workspace publisher backfill (ADR-009 §4.4): the creator while still an ACTIVE member, otherwise the
-- ACTIVE OWNER who joined first. Soft-deleted workspaces are skipped. No department publishers: every
-- department starts without one until an OWNER assigns it.
INSERT INTO core.workspace_publishers (workspace_id, user_id)
SELECT t.workspace_id, t.user_id
  FROM (SELECT w.id AS workspace_id,
               COALESCE(
                   (SELECT m.user_id FROM core.memberships m
                     WHERE m.workspace_id = w.id AND m.user_id = w.created_by AND m.status = 'ACTIVE'),
                   (SELECT m.user_id FROM core.memberships m
                     WHERE m.workspace_id = w.id AND m.role = 'OWNER' AND m.status = 'ACTIVE'
                     ORDER BY m.joined_at, m.user_id LIMIT 1)) AS user_id
          FROM core.workspaces w
         WHERE w.deleted_at IS NULL) t
 WHERE t.user_id IS NOT NULL
ON CONFLICT (workspace_id) DO NOTHING;

ALTER TABLE core.documents
    ADD CONSTRAINT fk_documents_owner_department
        FOREIGN KEY (workspace_id, owner_department_id) REFERENCES core.departments(workspace_id, id)
        ON DELETE RESTRICT,
    -- The owning department must be one of the departments allowed to read the document. Checked at commit
    -- because documents and document_departments are written in the same transaction.
    ADD CONSTRAINT fk_documents_owner_in_scope
        FOREIGN KEY (id, owner_department_id) REFERENCES core.document_departments(document_id, department_id)
        DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT ck_documents_owner_matches_visibility
        CHECK ((visibility = 'WORKSPACE') = (owner_department_id IS NULL));
CREATE INDEX ix_documents_owner_department ON core.documents(workspace_id, owner_department_id)
    WHERE owner_department_id IS NOT NULL;

-- A new PERSONAL workspace gets its creator as workspace publisher, so personal workspaces, eval and demos
-- can still upload. Only when the workspace is created by this call: the function also runs at every login,
-- and must not give the role back to someone an OWNER removed it from.
CREATE OR REPLACE FUNCTION core.create_personal_workspace(p_user_id uuid, p_workspace_id uuid,
                                                          p_name text, p_email text)
    RETURNS uuid
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$
DECLARE
    v_id      uuid;
    v_created integer;
BEGIN
    INSERT INTO core.workspaces (id, name, kind, created_by)
    VALUES (p_workspace_id, p_name, 'PERSONAL', p_user_id)
    ON CONFLICT (created_by) WHERE kind = 'PERSONAL' DO NOTHING;
    GET DIAGNOSTICS v_created = ROW_COUNT;

    SELECT id INTO STRICT v_id FROM core.workspaces
    WHERE created_by = p_user_id AND kind = 'PERSONAL';

    INSERT INTO core.memberships (workspace_id, user_id, role, status, display_name, email)
    SELECT v_id, u.id, 'OWNER', 'ACTIVE', u.display_name, lower(p_email)
    FROM core.users u WHERE u.id = p_user_id
    ON CONFLICT (workspace_id, user_id) DO NOTHING;

    IF v_created > 0 THEN
        INSERT INTO core.workspace_publishers (workspace_id, user_id)
        VALUES (v_id, p_user_id)
        ON CONFLICT (workspace_id) DO NOTHING;
    END IF;

    RETURN v_id;
END $$;
