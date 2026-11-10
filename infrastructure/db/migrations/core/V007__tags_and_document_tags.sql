-- V2-24: tags and document_tags (TECH-V2-core-api §3.4).
-- Runs as sopilot_migrator. Additive only.

CREATE TABLE core.tags (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 50),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);
CREATE UNIQUE INDEX uq_tag_name ON core.tags(workspace_id, lower(name));

CREATE TABLE core.document_tags (
    workspace_id uuid NOT NULL,
    document_id  uuid NOT NULL,
    tag_id       uuid NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, tag_id)      REFERENCES core.tags(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_document_tags_tag ON core.document_tags(workspace_id, tag_id);

ALTER TABLE core.tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.tags FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.tags
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

ALTER TABLE core.document_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.document_tags FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.document_tags
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

GRANT SELECT, INSERT, UPDATE, DELETE ON core.tags, core.document_tags TO sopilot_core_app;
