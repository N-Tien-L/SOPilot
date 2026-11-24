-- V2-XX: <what and why> (TECH-V2-<core-api|ai-service> §<n>). Runs as sopilot_migrator.
-- Replace <schema> with core or rag, and <app_role> with sopilot_core_app or sopilot_ai_app.
-- Patterns copied from core/V005__documents_outbox_audit.sql.

CREATE TABLE <schema>.example_items (
    id            uuid        PRIMARY KEY,
    workspace_id  uuid        NOT NULL,
    parent_id     uuid        NOT NULL,
    name          text        NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    created_at    timestamptz NOT NULL DEFAULT now(),
    -- Child rows carry workspace_id and reference the parent with it, so a join cannot cross tenants.
    FOREIGN KEY (workspace_id, parent_id) REFERENCES <schema>.example_parents (workspace_id, id)
);

CREATE INDEX example_items_workspace_parent_idx ON <schema>.example_items (workspace_id, parent_id);

-- Tenant isolation: FORCE also binds the owner (sopilot_migrator).
ALTER TABLE <schema>.example_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE <schema>.example_items FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <schema>.example_items
    USING (workspace_id = <schema>.current_workspace())
    WITH CHECK (workspace_id = <schema>.current_workspace());

-- Optional: append-only for the app role.
-- REVOKE UPDATE, DELETE ON <schema>.example_items FROM <app_role>;

-- Optional: a SECURITY DEFINER helper that must read across workspaces.
-- CREATE POLICY definer_access ON <schema>.example_items TO sopilot_migrator USING (true) WITH CHECK (true);
-- CREATE FUNCTION <schema>.example_lookup(p_ids uuid[]) RETURNS SETOF uuid
--     LANGUAGE sql STABLE SECURITY DEFINER
--     SET search_path = <schema>, pg_temp
--     AS $$ SELECT i.id FROM <schema>.example_items i WHERE i.id = ANY (p_ids) $$;
-- REVOKE EXECUTE ON FUNCTION <schema>.example_lookup(uuid[]) FROM PUBLIC;
-- GRANT EXECUTE ON FUNCTION <schema>.example_lookup(uuid[]) TO <app_role>;
