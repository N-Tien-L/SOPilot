-- Auth-owned provider identity. Email is enrollment metadata, never the login key.
CREATE TABLE IF NOT EXISTS core.external_identities (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    issuer VARCHAR(255) NOT NULL CHECK (length(trim(issuer)) > 0),
    subject VARCHAR(255) NOT NULL CHECK (length(trim(subject)) > 0),
    email_at_link VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_identity_subject UNIQUE (issuer, subject),
    CONSTRAINT uq_external_identity_user UNIQUE (user_id, issuer)
);
-- Deliberately no backfill by email: a verified Google login must enroll the link.
