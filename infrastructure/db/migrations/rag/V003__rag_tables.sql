-- V2-09: rag tables (TECH-V2-ai-service §3.1–§3.5, §7.6) and the cross-workspace helpers the
-- worker needs. One migration for the whole ticket, including the rag.messages decision-log
-- columns (refusal_reason, route, rewrite_status, checks, context_sources).
--
-- Tenant rule: every table with workspace_id ENABLEs and FORCEs RLS with the policy
-- workspace_id = rag.current_workspace(). Exceptions (no workspace_id, no RLS) are commented.
--
-- FORCE RLS also binds the table owner (sopilot_migrator), so the SECURITY DEFINER helpers at the
-- end would see nothing. Each table they read gets one extra policy granted TO sopilot_migrator
-- only; application roles never match it, and the migrator role is not used by any service.

-- §3.1 Document read access (ADR-007 §4.5) -------------------------------------------------------
CREATE TABLE rag.document_access (
    workspace_id      uuid NOT NULL,
    document_id       uuid PRIMARY KEY,
    visibility        text NOT NULL CHECK (visibility IN ('WORKSPACE', 'DEPARTMENTS')),
    department_ids    uuid[] NOT NULL DEFAULT '{}',
    access_revision   bigint NOT NULL,
    active_version_id uuid,
    title             text NOT NULL,
    deleted_at        timestamptz,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (visibility = 'WORKSPACE' OR cardinality(department_ids) >= 1)
);
CREATE INDEX ix_document_access_ws ON rag.document_access (workspace_id);
CREATE INDEX ix_document_access_depts ON rag.document_access USING gin (department_ids);
CREATE TRIGGER trg_document_access_updated BEFORE UPDATE ON rag.document_access
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

-- §3.2 Ingestion jobs and extraction result ------------------------------------------------------
CREATE TABLE rag.ingestion_jobs (
    id              uuid PRIMARY KEY,
    workspace_id    uuid NOT NULL,
    document_id     uuid NOT NULL,
    version_id      uuid NOT NULL UNIQUE,
    request_attempt int  NOT NULL DEFAULT 0,
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'QUEUED'
                    CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')),
    attempts        int  NOT NULL DEFAULT 0,
    lease_until     timestamptz,
    run_after       timestamptz NOT NULL DEFAULT now(),
    failure_code    text,
    stage_timings   jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ingestion_jobs_due ON rag.ingestion_jobs (run_after, created_at)
    WHERE status IN ('QUEUED', 'RUNNING');
CREATE INDEX ix_ingestion_jobs_doc ON rag.ingestion_jobs (document_id);
CREATE TRIGGER trg_ingestion_jobs_updated BEFORE UPDATE ON rag.ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

CREATE TABLE rag.extracted_documents (
    workspace_id       uuid NOT NULL,
    version_id         uuid PRIMARY KEY,
    document_id        uuid NOT NULL,
    structure          jsonb NOT NULL,
    markdown           text  NOT NULL,
    page_index         jsonb,
    warnings           jsonb NOT NULL DEFAULT '[]',
    normalizer_version text  NOT NULL,
    page_count         int,
    language           text,
    doc_family         text  NOT NULL
                       CHECK (doc_family IN ('ISO_PROCEDURE', 'LEGAL_ARTICLES', 'MARKDOWN', 'PROSE')),
    boilerplate        jsonb NOT NULL,
    extracted_meta     jsonb NOT NULL,
    extractor          text  NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_extracted_documents_doc ON rag.extracted_documents (document_id);

-- §3.3 Chunks and indexes ------------------------------------------------------------------------
CREATE TABLE rag.chunks (
    id                 uuid PRIMARY KEY,
    workspace_id       uuid NOT NULL,
    document_id        uuid NOT NULL,
    version_id         uuid NOT NULL,
    ordinal            int  NOT NULL,
    chunk_type         text NOT NULL CHECK (chunk_type IN ('SECTION', 'PROCEDURE_STEP', 'TABLE', 'PROSE')),
    section_path       text[] NOT NULL,
    page_start         int,
    page_end           int,
    char_start         int  NOT NULL,
    char_end           int  NOT NULL,
    content            text NOT NULL,
    index_text         text NOT NULL,
    lang               text,
    token_count        int  NOT NULL,
    content_sha256     bytea NOT NULL,
    embedding          public.vector(1024) NOT NULL,
    embedding_provider text NOT NULL,
    embedding_model    text NOT NULL,
    embedding_dim      int  NOT NULL CHECK (embedding_dim = 1024),
    embedding_revision text NOT NULL,
    lexical_len        int  NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_id, ordinal),
    CHECK (char_end > char_start)
);
CREATE INDEX ix_chunks_doc ON rag.chunks (document_id, version_id);
CREATE INDEX ix_chunks_ws ON rag.chunks (workspace_id);
CREATE INDEX ix_chunks_embedding ON rag.chunks USING hnsw (embedding public.vector_cosine_ops);

CREATE TABLE rag.chunk_terms (
    workspace_id uuid NOT NULL,
    chunk_id     uuid NOT NULL REFERENCES rag.chunks (id) ON DELETE CASCADE,
    term         text NOT NULL,
    tf           int  NOT NULL CHECK (tf > 0),
    PRIMARY KEY (chunk_id, term)
);
CREATE INDEX ix_chunk_terms_lookup ON rag.chunk_terms (workspace_id, term);

-- Exception: no workspace_id, no RLS. Vectors keyed by content hash only (ADR-007 §4.5); never
-- returns text, and there is no path from a hash back to a workspace.
CREATE TABLE rag.embedding_cache (
    model          text  NOT NULL,
    revision       text  NOT NULL,
    content_sha256 bytea NOT NULL,
    embedding      public.vector(1024) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, revision, content_sha256)
);

-- §3.4 Conversations, retrieval and guard --------------------------------------------------------
CREATE TABLE rag.conversations (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL,
    title        text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    deleted_at   timestamptz
);
CREATE INDEX ix_conversations_owner ON rag.conversations (workspace_id, user_id, updated_at DESC);
CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON rag.conversations
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

CREATE TABLE rag.messages (
    id               uuid PRIMARY KEY,
    workspace_id     uuid NOT NULL,
    conversation_id  uuid NOT NULL REFERENCES rag.conversations (id) ON DELETE CASCADE,
    user_id          uuid NOT NULL,
    role             text NOT NULL CHECK (role IN ('USER', 'ASSISTANT')),
    content          text NOT NULL,
    standalone_query text,
    outcome          text CHECK (outcome IN ('ANSWERED', 'REFUSED_NO_EVIDENCE', 'REFUSED_GUARD',
                                             'TEMPLATE', 'QUOTA_EXCEEDED', 'ERROR')),
    refusal_reason   text CHECK (refusal_reason IN ('NO_EVIDENCE', 'GENERATOR_NOT_FOUND',
                                                    'OUT_OF_SCOPE', 'INPUT_INVALID')),
    route            jsonb,
    rewrite_status   text CHECK (rewrite_status IN ('NONE', 'OK', 'FAILED')),
    checks           jsonb,
    lang             text,
    retrieval_mode   text,
    gate_score       real,
    threshold        real,
    model            text,
    prompt_version   text,
    tokens_in        int,
    tokens_out       int,
    latency_ms       jsonb,
    context_sources  jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (refusal_reason IS NULL OR outcome IN ('REFUSED_NO_EVIDENCE', 'TEMPLATE'))
);
CREATE INDEX ix_messages_conv ON rag.messages (conversation_id, created_at);

CREATE TABLE rag.message_citations (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages (id) ON DELETE CASCADE,
    n            int  NOT NULL,
    chunk_id     uuid,
    document_id  uuid NOT NULL,
    version_id   uuid NOT NULL,
    page_start   int,
    char_start   int  NOT NULL,
    char_end     int  NOT NULL,
    snippet      text NOT NULL,
    PRIMARY KEY (message_id, n)
);
CREATE INDEX ix_citations_document ON rag.message_citations (document_id);

CREATE TABLE rag.retrieval_results (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages (id) ON DELETE CASCADE,
    chunk_id     uuid NOT NULL,
    rank         int  NOT NULL,
    dense_score  real,
    bm25_score   real,
    fusion_score real,
    rerank_score real,
    in_context   boolean NOT NULL,
    PRIMARY KEY (message_id, chunk_id)
);

CREATE TABLE rag.guard_events (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    message_id   uuid REFERENCES rag.messages (id) ON DELETE CASCADE,
    user_id      uuid NOT NULL,
    layer        text NOT NULL CHECK (layer IN ('INPUT_BLOCK', 'INPUT_FLAG', 'OUTPUT_CANARY',
                                                'OUTPUT_PROMPT_ECHO')),
    rule_id      text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag.usage_counters (
    workspace_id uuid NOT NULL,
    user_id      uuid NOT NULL,
    day          date NOT NULL,
    questions    int  NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id, user_id, day)
);

-- Exception: no workspace_id, no RLS. System-wide question ceiling, counts only (§3.4).
CREATE TABLE rag.system_usage (
    day       date PRIMARY KEY,
    questions int  NOT NULL DEFAULT 0
);

-- §7.6 Feedback and knowledge gaps (used by V2-13) -----------------------------------------------
CREATE TABLE rag.message_feedback (
    workspace_id uuid NOT NULL,
    message_id   uuid NOT NULL REFERENCES rag.messages (id) ON DELETE CASCADE,
    user_id      uuid NOT NULL,
    vote         smallint NOT NULL CHECK (vote IN (-1, 1)),
    comment      text CHECK (length(comment) <= 1000),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, user_id)
);
CREATE TRIGGER trg_message_feedback_updated BEFORE UPDATE ON rag.message_feedback
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

CREATE TABLE rag.knowledge_gap_status (
    workspace_id uuid NOT NULL,
    message_id   uuid PRIMARY KEY REFERENCES rag.messages (id) ON DELETE CASCADE,
    resolved_by  uuid NOT NULL,
    resolved_at  timestamptz NOT NULL DEFAULT now(),
    note         text
);

-- §3.5 Metadata suggestions (used by V2-25), outbox and idempotency ------------------------------
CREATE TABLE rag.suggestion_jobs (
    id           uuid PRIMARY KEY,
    workspace_id uuid NOT NULL,
    document_id  uuid NOT NULL,
    version_id   uuid NOT NULL UNIQUE,
    input        jsonb NOT NULL,
    status       text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED')),
    result       jsonb,
    method       text CHECK (method IN ('RULES', 'LLM', 'RULES_FALLBACK')),
    timings      jsonb,
    attempts     int  NOT NULL DEFAULT 0,
    lease_until  timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_suggestion_jobs_doc ON rag.suggestion_jobs (document_id);
CREATE TRIGGER trg_suggestion_jobs_updated BEFORE UPDATE ON rag.suggestion_jobs
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

CREATE TABLE rag.suggestion_cache (
    workspace_id uuid  NOT NULL,
    cache_key    bytea NOT NULL,
    result       jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, cache_key)
);

CREATE TABLE rag.outbox_events (
    id              uuid PRIMARY KEY,
    workspace_id    uuid NOT NULL,
    aggregate_id    uuid NOT NULL,
    event_type      text NOT NULL CHECK (event_type IN ('VERSION_STATUS', 'SUGGESTIONS_READY')),
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'DELIVERED', 'DEAD')),
    attempts        int  NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    delivered_at    timestamptz
);
CREATE INDEX ix_outbox_due ON rag.outbox_events (next_attempt_at) WHERE status = 'PENDING';

-- Exception: no workspace_id, no RLS. Idempotency keys of /internal/** only; rows older than
-- 7 days are purged.
CREATE TABLE rag.processed_requests (
    idempotency_key uuid PRIMARY KEY,
    processed_at    timestamptz NOT NULL DEFAULT now()
);

-- Row-level security -----------------------------------------------------------------------------
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'document_access', 'ingestion_jobs', 'extracted_documents', 'chunks', 'chunk_terms',
        'conversations', 'messages', 'message_citations', 'retrieval_results', 'guard_events',
        'usage_counters', 'message_feedback', 'knowledge_gap_status', 'suggestion_jobs',
        'suggestion_cache', 'outbox_events'
    ] LOOP
        EXECUTE format('ALTER TABLE rag.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE rag.%I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON rag.%I '
            'USING (workspace_id = rag.current_workspace()) '
            'WITH CHECK (workspace_id = rag.current_workspace())', t);
    END LOOP;
END $$;

-- Owner-only policies for the SECURITY DEFINER helpers below (see header).
CREATE POLICY definer_jobs ON rag.ingestion_jobs TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_outbox ON rag.outbox_events TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_read ON rag.document_access FOR SELECT TO sopilot_migrator USING (true);
CREATE POLICY definer_read ON rag.chunks FOR SELECT TO sopilot_migrator USING (true);
CREATE POLICY definer_read ON rag.extracted_documents FOR SELECT TO sopilot_migrator USING (true);

-- Cross-workspace helpers ------------------------------------------------------------------------

-- §3.2: one due job of any workspace: QUEUED with run_after <= now(), or RUNNING with an expired
-- lease. Marks it RUNNING, sets the lease and counts the attempt. The caller then sets
-- app.workspace_id from the returned row; everything after that runs under RLS.
CREATE FUNCTION rag.claim_ingestion_job(p_lease_seconds int DEFAULT 600)
    RETURNS TABLE (id uuid, workspace_id uuid, document_id uuid, version_id uuid,
                   request_attempt int, payload jsonb, attempts int, failure_code text)
    LANGUAGE sql VOLATILE SECURITY DEFINER
    SET search_path = rag, pg_temp
AS $$
    UPDATE rag.ingestion_jobs j
       SET status = 'RUNNING',
           lease_until = now() + make_interval(secs => p_lease_seconds),
           attempts = j.attempts + 1
     WHERE j.id = (
            SELECT d.id FROM rag.ingestion_jobs d
             WHERE (d.status = 'QUEUED' AND d.run_after <= now())
                OR (d.status = 'RUNNING' AND d.lease_until < now())
             ORDER BY d.run_after, d.created_at
             FOR UPDATE SKIP LOCKED
             LIMIT 1)
    RETURNING j.id, j.workspace_id, j.document_id, j.version_id, j.request_attempt, j.payload,
              j.attempts, j.failure_code
$$;

-- §8: outbox events of any workspace that are due. Rows stay PENDING; the dispatcher updates them
-- under RLS after setting app.workspace_id. The lease (next_attempt_at pushed forward) keeps two
-- dispatchers from sending the same event at once.
CREATE FUNCTION rag.claim_outbox_batch(p_limit int, p_lease_seconds int DEFAULT 60)
    RETURNS TABLE (id uuid, workspace_id uuid, aggregate_id uuid, event_type text, payload jsonb,
                   attempts int)
    LANGUAGE sql VOLATILE SECURITY DEFINER
    SET search_path = rag, pg_temp
AS $$
    UPDATE rag.outbox_events o
       SET next_attempt_at = now() + make_interval(secs => p_lease_seconds)
     WHERE o.id IN (
            SELECT e.id FROM rag.outbox_events e
             WHERE e.status = 'PENDING' AND e.next_attempt_at <= now()
             ORDER BY e.next_attempt_at, e.created_at
             FOR UPDATE SKIP LOCKED
             LIMIT p_limit)
    RETURNING o.id, o.workspace_id, o.aggregate_id, o.event_type, o.payload, o.attempts
$$;

-- §3.3, §5.2: active versions to ingest again (startup check and `admin reindex`): chunks embedded
-- by another model or revision than the active one, or extracted with another normalizer
-- version; p_all = true lists every active version (BM25 tokenizer change). Identifiers only.
CREATE FUNCTION rag.stale_active_versions(p_model text, p_revision text,
                                          p_normalizer_version text, p_all boolean DEFAULT false)
    RETURNS TABLE (workspace_id uuid, document_id uuid, version_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = rag, pg_temp
AS $$
    SELECT da.workspace_id, da.document_id, da.active_version_id
      FROM rag.document_access da
     WHERE da.deleted_at IS NULL
       AND da.active_version_id IS NOT NULL
       AND (p_all
            OR EXISTS (SELECT 1 FROM rag.chunks c
                        WHERE c.document_id = da.document_id
                          AND c.version_id = da.active_version_id
                          AND (c.embedding_model <> p_model OR c.embedding_revision <> p_revision))
            OR EXISTS (SELECT 1 FROM rag.extracted_documents e
                        WHERE e.version_id = da.active_version_id
                          AND e.normalizer_version <> p_normalizer_version))
$$;

REVOKE EXECUTE ON FUNCTION rag.claim_ingestion_job(int), rag.claim_outbox_batch(int, int),
    rag.stale_active_versions(text, text, text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rag.claim_ingestion_job(int), rag.claim_outbox_batch(int, int),
    rag.stale_active_versions(text, text, text, boolean) TO sopilot_ai_app;
