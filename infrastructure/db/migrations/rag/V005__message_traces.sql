-- Real-time Query Pipeline Inspector: persisted sanitized pipeline trace per assistant message.
-- Additive only. Inherits SELECT/INSERT/UPDATE/DELETE grants for sopilot_ai_app from V001.

CREATE TABLE rag.message_traces (
    message_id    uuid PRIMARY KEY REFERENCES rag.messages (id) ON DELETE CASCADE,
    workspace_id  uuid NOT NULL,
    user_id       uuid NOT NULL,
    trace_version int  NOT NULL DEFAULT 1,
    trace         jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_message_traces_ws_user ON rag.message_traces (workspace_id, user_id);

ALTER TABLE rag.message_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.message_traces FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON rag.message_traces
    USING (workspace_id = rag.current_workspace())
    WITH CHECK (workspace_id = rag.current_workspace());
