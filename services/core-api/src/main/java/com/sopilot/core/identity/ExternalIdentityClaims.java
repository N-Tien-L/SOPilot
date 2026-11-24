package com.sopilot.core.identity;

/**
 * Verified identity from an external issuer (Google or the local/test dev issuer).
 * {@code email} is lower-case. Identity is {@code (issuer, subject)}, never the email.
 */
public record ExternalIdentityClaims(String issuer,
                                     String subject,
                                     String email,
                                     String displayName,
                                     String avatarUrl,
                                     String hostedDomain) {
}
