package com.sopilot.core.identity;

/**
 * A Google ID token failed verification. The {@link Reason} is for logs only; clients always
 * receive the generic {@code 401 INVALID_GOOGLE_TOKEN} (TECH §5.1).
 */
public class GoogleTokenRejectedException extends RuntimeException {

    public enum Reason {
        NOT_CONFIGURED, MALFORMED, BAD_SIGNATURE, BAD_ISSUER, BAD_AUDIENCE, EXPIRED, NOT_YET_VALID,
        EMAIL_NOT_VERIFIED, MISSING_EMAIL, MISSING_SUBJECT, NONCE_MISSING, NONCE_MISMATCH
    }

    private final Reason reason;

    public GoogleTokenRejectedException(Reason reason) {
        super(reason.name(), null, false, false);
        this.reason = reason;
    }

    public Reason reason() {
        return reason;
    }
}
