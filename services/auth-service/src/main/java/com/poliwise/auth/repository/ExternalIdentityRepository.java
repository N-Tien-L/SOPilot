package com.poliwise.auth.repository;

import com.poliwise.auth.entity.ExternalIdentity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface ExternalIdentityRepository extends JpaRepository<ExternalIdentity, UUID> {
    Optional<ExternalIdentity> findByIssuerAndSubject(String issuer, String subject);

    @Query(value = """
            SELECT i.* FROM core.external_identities i
            JOIN core.users u ON u.id = i.user_id
            WHERE i.issuer = :issuer AND lower(u.email) = lower(:email)
            """, nativeQuery = true)
    Optional<ExternalIdentity> findByIssuerAndUserEmail(@Param("issuer") String issuer,
                                                      @Param("email") String email);

    // Both uniqueness constraints arbitrate concurrent enrollments without aborting the transaction.
    @Modifying
    @Query(value = """
            INSERT INTO core.external_identities (id, user_id, issuer, subject, email_at_link)
            VALUES (:id, :userId, :issuer, :subject, :email)
            ON CONFLICT DO NOTHING
            """, nativeQuery = true)
    int insertIfAbsent(@Param("id") UUID id, @Param("userId") UUID userId,
                       @Param("issuer") String issuer, @Param("subject") String subject,
                       @Param("email") String email);
}
