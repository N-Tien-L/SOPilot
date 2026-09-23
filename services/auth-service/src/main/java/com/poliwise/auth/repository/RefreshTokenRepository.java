package com.poliwise.auth.repository;

import com.poliwise.auth.entity.RefreshToken;
import jakarta.persistence.LockModeType;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public interface RefreshTokenRepository extends JpaRepository<RefreshToken, UUID> {

        Optional<RefreshToken> findByTokenHash(String tokenHash);

        boolean existsByTokenHash(String tokenHash);

        @Lock(LockModeType.PESSIMISTIC_WRITE)
        @Query("select rt from RefreshToken rt where rt.tokenHash = :tokenHash")
        Optional<RefreshToken> findByTokenHashForUpdate(@Param("tokenHash") String tokenHash);

        @Query("""
                        select rt
                        from RefreshToken rt
                        where rt.userId = :userId
                          and coalesce(rt.revoked, false) = false
                          and rt.expiresAt > :now
                        order by rt.createdAt desc
                        """)
        List<RefreshToken> findActiveTokensByUserId(@Param("userId") UUID userId,
                        @Param("now") OffsetDateTime now);

        @Transactional
        @Modifying(clearAutomatically = true, flushAutomatically = true)
        @Query("""
                        update RefreshToken rt
                        set rt.revoked = true,
                            rt.revokedAt = :revokedAt,
                            rt.revokedReason = :reason,
                            rt.replacedBy = :replacedBy
                        where rt.id = :tokenId
                          and coalesce(rt.revoked, false) = false
                        """)
        int revokeToken(@Param("tokenId") UUID tokenId,
                        @Param("revokedAt") OffsetDateTime revokedAt,
                        @Param("reason") String reason, @Param("replacedBy") UUID replacedBy);

        @Transactional
        @Modifying(clearAutomatically = true, flushAutomatically = true)
        @Query("""
                        update RefreshToken rt
                        set rt.revoked = true,
                            rt.revokedAt = :revokedAt,
                            rt.revokedReason = :reason
                        where rt.userId = :userId
                          and coalesce(rt.revoked, false) = false
                        """)
        int revokeAllActiveTokensByUserId(@Param("userId") UUID userId,
                        @Param("revokedAt") OffsetDateTime revokedAt,
                        @Param("reason") String reason);
}
