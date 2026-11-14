-- V2-25: metadata suggestion jobs (TECH-V2-ai-service §3.5, §5.7). Additive only: the tables come
-- from V003; this adds the cross-workspace claim the worker needs, like rag.claim_ingestion_job.

-- FORCE RLS also binds the owner, so the SECURITY DEFINER claim needs this owner-only policy
-- (same pattern as definer_jobs in V003). Application roles never match it.
CREATE POLICY definer_suggestions ON rag.suggestion_jobs TO sopilot_migrator
    USING (true) WITH CHECK (true);

-- One due suggestion job of any workspace: QUEUED, or RUNNING with an expired lease. Marks it
-- RUNNING and counts the attempt. The caller then sets app.workspace_id from the returned row.
CREATE FUNCTION rag.claim_suggestion_job(p_lease_seconds int DEFAULT 300)
    RETURNS TABLE (id uuid, workspace_id uuid, document_id uuid, version_id uuid,
                   input jsonb, attempts int)
    LANGUAGE sql VOLATILE SECURITY DEFINER
    SET search_path = rag, pg_temp
AS $$
    UPDATE rag.suggestion_jobs j
       SET status = 'RUNNING',
           lease_until = now() + make_interval(secs => p_lease_seconds),
           attempts = j.attempts + 1
     WHERE j.id = (
            SELECT d.id FROM rag.suggestion_jobs d
             WHERE d.status = 'QUEUED'
                OR (d.status = 'RUNNING' AND d.lease_until < now())
             ORDER BY d.created_at
             FOR UPDATE SKIP LOCKED
             LIMIT 1)
    RETURNING j.id, j.workspace_id, j.document_id, j.version_id, j.input, j.attempts
$$;

REVOKE EXECUTE ON FUNCTION rag.claim_suggestion_job(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rag.claim_suggestion_job(int) TO sopilot_ai_app;
