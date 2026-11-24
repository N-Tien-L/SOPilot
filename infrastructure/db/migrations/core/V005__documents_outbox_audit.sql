-- V2-12: documents, versions, outbox and audit log (TECH-V2-core-api §3.3-§3.6, §4.2).
-- Runs as sopilot_migrator. Tags, document_tags and document_suggestions come with V2-24/V2-25;
-- categories exist now only as the target of documents.category_id (API in V2-24).

CREATE TABLE core.categories (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    name         text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);
CREATE UNIQUE INDEX uq_category_name ON core.categories(workspace_id, lower(name));

CREATE TABLE core.documents (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL REFERENCES core.workspaces(id) ON DELETE CASCADE,
    title              text NOT NULL CHECK (length(trim(title)) > 0),
    title_source       text NOT NULL DEFAULT 'SYSTEM' CHECK (title_source IN ('SYSTEM','SUGGESTED','USER')),
    description        text,
    description_source text NOT NULL DEFAULT 'SYSTEM' CHECK (description_source IN ('SYSTEM','SUGGESTED','USER')),
    category_id        uuid,
    category_source    text NOT NULL DEFAULT 'SYSTEM' CHECK (category_source IN ('SYSTEM','SUGGESTED','USER')),
    tags_source        text NOT NULL DEFAULT 'SYSTEM' CHECK (tags_source IN ('SYSTEM','SUGGESTED','USER')),
    language           text,
    language_source    text NOT NULL DEFAULT 'SYSTEM' CHECK (language_source IN ('SYSTEM','SUGGESTED','USER')),
    visibility         text NOT NULL DEFAULT 'WORKSPACE' CHECK (visibility IN ('WORKSPACE','DEPARTMENTS')),
    access_revision    bigint NOT NULL DEFAULT 1,
    current_version_id uuid,                        -- READY version used for Q&A
    latest_version_id  uuid,                        -- newest version, possibly still processing
    created_by         uuid NOT NULL REFERENCES core.users(id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    deleted_at         timestamptz,                 -- soft delete while ai-service removes chunks
    UNIQUE (workspace_id, id),
    FOREIGN KEY (workspace_id, category_id) REFERENCES core.categories(workspace_id, id)
        ON DELETE SET NULL (category_id)
);
CREATE INDEX ix_documents_workspace_created ON core.documents(workspace_id, created_at DESC, id DESC)
    WHERE deleted_at IS NULL;

CREATE TABLE core.document_versions (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL,
    document_id        uuid NOT NULL,
    version_no         int  NOT NULL,
    status             text NOT NULL CHECK (status IN ('UPLOADED','PROCESSING','READY','FAILED','SUPERSEDED')),
    failure_code       text,
    failure_message    text,                        -- fixed sentence per code, never an internal error
    original_name      text NOT NULL,
    mime_type          text NOT NULL,
    file_type          text NOT NULL CHECK (file_type IN ('PDF','MD')),
    size_bytes         bigint NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 20971520),
    sha256             bytea NOT NULL,
    object_key         text NOT NULL UNIQUE,
    page_count         int,
    detected_language  text,
    doc_code           text,
    revision_label     text,
    effective_date     date,
    embedding_model    text,
    embedding_revision text,
    chunk_count        int,
    warning_codes      text[] NOT NULL DEFAULT '{}',
    attempt            int NOT NULL DEFAULT 0,
    uploaded_by        uuid NOT NULL REFERENCES core.users(id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    processed_at       timestamptz,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_no),
    FOREIGN KEY (workspace_id, document_id) REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_document_versions_sha ON core.document_versions(workspace_id, sha256);

-- Departments a DEPARTMENTS-scoped document is limited to (written by V2-24); the RESTRICT FK is what
-- stops a department that a document still references from being deleted (V2-23).
CREATE TABLE core.document_departments (
    workspace_id  uuid NOT NULL,
    document_id   uuid NOT NULL,
    department_id uuid NOT NULL,
    PRIMARY KEY (document_id, department_id),
    FOREIGN KEY (workspace_id, document_id)   REFERENCES core.documents(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, department_id) REFERENCES core.departments(workspace_id, id) ON DELETE RESTRICT
);

CREATE TABLE core.outbox_events (
    id              uuid PRIMARY KEY,               -- also the Idempotency-Key sent to ai-service
    workspace_id    uuid NOT NULL,
    aggregate_id    uuid NOT NULL,                  -- document id
    event_type      text NOT NULL CHECK (event_type IN ('INGEST_REQUESTED','ACCESS_UPDATED','DOCUMENT_DELETED')),
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','DELIVERED','DEAD')),
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz
);
CREATE INDEX ix_outbox_due ON core.outbox_events(next_attempt_at) WHERE status = 'PENDING';

CREATE TABLE core.audit_logs (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    actor_id     uuid,
    action       text NOT NULL,
    target_type  text,
    target_id    uuid,
    details      jsonb NOT NULL DEFAULT '{}',
    trace_id     text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_workspace_time ON core.audit_logs(workspace_id, created_at DESC, id DESC);
-- Append-only for the application role.
REVOKE UPDATE, DELETE ON core.audit_logs FROM sopilot_core_app;

CREATE TRIGGER trg_categories_updated_at BEFORE UPDATE ON core.categories
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON core.documents
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER trg_document_versions_updated_at BEFORE UPDATE ON core.document_versions
    FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['categories','documents','document_versions','document_departments',
                             'outbox_events','audit_logs'] LOOP
        EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE core.%I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY tenant_isolation ON core.%I '
                       'USING (workspace_id = core.current_workspace()) '
                       'WITH CHECK (workspace_id = core.current_workspace())', t);
    END LOOP;
END $$;

-- SECURITY DEFINER helpers run as the table owner, which FORCE RLS also binds; give the migrator its
-- own policy on the two tables they read (see V003). sopilot_core_app is unaffected.
CREATE POLICY definer_access ON core.outbox_events TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.document_versions TO sopilot_migrator USING (true) WITH CHECK (true);

-- Dispatcher: claims due events of every workspace (TECH §4.2, §7). The claim is a lease: the event
-- stays PENDING but is not due again for 60 s, so a crashed sender is retried and two dispatchers
-- never send the same event at once.
CREATE FUNCTION core.claim_outbox_batch(p_limit int) RETURNS SETOF core.outbox_events
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$
    UPDATE core.outbox_events o
       SET next_attempt_at = now() + interval '60 seconds'
     WHERE o.id IN (SELECT e.id FROM core.outbox_events e
                     WHERE e.status = 'PENDING' AND e.next_attempt_at <= now()
                     ORDER BY e.next_attempt_at
                     LIMIT greatest(p_limit, 0)
                       FOR UPDATE SKIP LOCKED)
    RETURNING o.*
$$;

-- StorageJanitor: which of these object keys are still referenced by a version, in any workspace.
CREATE FUNCTION core.referenced_object_keys(p_keys text[]) RETURNS SETOF text
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$ SELECT v.object_key FROM core.document_versions v WHERE v.object_key = ANY (p_keys) $$;

REVOKE EXECUTE ON FUNCTION core.claim_outbox_batch(int), core.referenced_object_keys(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.claim_outbox_batch(int), core.referenced_object_keys(text[]) TO sopilot_core_app;
