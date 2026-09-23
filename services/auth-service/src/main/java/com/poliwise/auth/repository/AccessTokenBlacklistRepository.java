package com.poliwise.auth.repository;

import com.poliwise.auth.entity.AccessTokenBlacklist;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import java.time.Instant;
import java.util.UUID;

@Repository
public interface AccessTokenBlacklistRepository extends JpaRepository<AccessTokenBlacklist, String> {

    boolean existsByJti(String jti);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            delete from AccessTokenBlacklist atb
            where atb.expiredAt < :now
            """)
    int deleteExpiredTokens(@Param("now") Instant now);
}
