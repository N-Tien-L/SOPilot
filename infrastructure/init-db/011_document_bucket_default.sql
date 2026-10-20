-- Forward-only, idempotent default change for SOPilot document uploads.
-- Does not move objects or rewrite bucket references on existing documents.
ALTER TABLE knowledge.documents
    ALTER COLUMN bucket_name SET DEFAULT 'sopilot-documents';
