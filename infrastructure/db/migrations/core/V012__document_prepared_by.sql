-- V2-46: who drafted a document ("Prepared by"), apart from who published it (TECH-V2-core-api §3.3, ADR-009).
-- Runs as sopilot_migrator. Additive only.
-- Free text, optional: the drafter can be a department, a person or an outside source, and it is a fact about
-- the content, so it is a copy and not a reference (renaming a department or transferring the document does not
-- change who wrote it). core-api fills it with the owning department's name when a department document is created.
-- core.documents already has FORCE row level security and the app role's DML grants (V005); a new column needs neither.

ALTER TABLE core.documents
    ADD COLUMN prepared_by text
        CONSTRAINT ck_documents_prepared_by_length CHECK (prepared_by IS NULL OR length(trim(prepared_by)) BETWEEN 1 AND 100);
