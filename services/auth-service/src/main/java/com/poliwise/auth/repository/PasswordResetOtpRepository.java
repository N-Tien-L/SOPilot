package com.poliwise.auth.repository;

import com.poliwise.auth.entity.PasswordResetOtp;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface PasswordResetOtpRepository extends JpaRepository<PasswordResetOtp, UUID> {

    Optional<PasswordResetOtp> findTopByEmailAndUsedFalseOrderByCreatedAtDesc(String email);

    Optional<PasswordResetOtp> findByEmailAndOtpCodeAndUsedFalse(String email, String otpCode);

    @Modifying
    @Query("UPDATE PasswordResetOtp o SET o.used = true, o.usedAt = :usedAt WHERE o.email = :email AND o.used = false")
    void markAllUnusedForEmail(@Param("email") String email, @Param("usedAt") OffsetDateTime usedAt);

    @Modifying
    @Query("DELETE FROM PasswordResetOtp o WHERE o.expiresAt < :now")
    void deleteExpiredOtps(@Param("now") OffsetDateTime now);

    @Modifying
    @Query("DELETE FROM PasswordResetOtp o WHERE o.email = :email")
    void deleteByEmail(@Param("email") String email);
}
