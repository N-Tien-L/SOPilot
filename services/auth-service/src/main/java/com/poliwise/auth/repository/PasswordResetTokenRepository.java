package com.poliwise.auth.repository;

import com.poliwise.auth.entity.PasswordResetToken;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface PasswordResetTokenRepository extends JpaRepository<PasswordResetToken, UUID> {

    Optional<PasswordResetToken> findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(
            String tokenHash,
            OffsetDateTime now
    );

    @Modifying
    @Query("""
            update PasswordResetToken token
            set token.usedAt = :usedAt
            where token.userId = :userId
              and token.usedAt is null
            """)
    int markActiveTokensUsedForUser(@Param("userId") UUID userId, @Param("usedAt") OffsetDateTime usedAt);
}
