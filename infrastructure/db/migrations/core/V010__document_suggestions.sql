-- V2-25: metadata suggestions received from ai-service (TECH-V2-ai-service §5.7). Runs as sopilot_migrator.
-- Additive only. Kept apart from core.documents so a suggestion never overwrites a value by itself:
-- the callback applies it only to fields whose source is not USER (see SuggestionService).

CREATE TABLE core.document_suggestions (
    workspace_id          uuid NOT NULL,
    version_id            uuid PRIMARY KEY,
    document_id           uuid NOT NULL,
    method                text NOT NULL CHECK (method IN ('LLM', 'RULES_FALLBACK')),
    title                 text,
    description           text,
    category_id           uuid,
    proposed_category_name text,
    tags                  text[] NOT NULL DEFAULT '{}',
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_document_suggestions_doc ON core.document_suggestions (workspace_id, document_id);

ALTER TABLE core.document_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.document_suggestions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON core.document_suggestions
    USING (workspace_id = core.current_workspace())
    WITH CHECK (workspace_id = core.current_workspace());

GRANT SELECT, INSERT, UPDATE ON core.document_suggestions TO sopilot_core_app;
