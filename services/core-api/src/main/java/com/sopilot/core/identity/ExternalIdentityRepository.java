package com.sopilot.core.identity;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/** {@code core.external_identities}: links {@code (issuer, subject)} to a user (ADR-005 §4.1). */
@Repository
public class ExternalIdentityRepository {

    private final JdbcTemplate jdbc;

    public ExternalIdentityRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<UUID> findUserId(String issuer, String subject) {
        return jdbc.queryForList("SELECT user_id FROM core.external_identities WHERE issuer = ? AND subject = ?",
                UUID.class, issuer, subject).stream().findFirst();
    }

    /** @return true if inserted, false if {@code (issuer, subject)} was already linked */
    public boolean insertIfAbsent(UUID id, UUID userId, String issuer, String subject, String email, String hostedDomain) {
        return jdbc.update("INSERT INTO core.external_identities (id, user_id, issuer, subject, email_at_link, hosted_domain) "
                        + "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (issuer, subject) DO NOTHING",
                id, userId, issuer, subject, email, hostedDomain) == 1;
    }

    /** Latest {@code hd} claim seen for this identity (TECH §3.1). */
    public void updateHostedDomain(String issuer, String subject, String hostedDomain) {
        jdbc.update("UPDATE core.external_identities SET hosted_domain = ? WHERE issuer = ? AND subject = ? "
                + "AND hosted_domain IS DISTINCT FROM ?", hostedDomain, issuer, subject, hostedDomain);
    }
}
