package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.ForgotPasswordResponse;
import com.poliwise.auth.dto.auth.ResetPasswordResponse;
import com.poliwise.auth.entity.PasswordResetToken;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.repository.PasswordResetTokenRepository;
import com.poliwise.auth.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.util.UriComponentsBuilder;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;

@Service
public class ForgotPasswordService {

    private static final Logger log = LoggerFactory.getLogger(ForgotPasswordService.class);
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final UserRepository userRepository;
    private final PasswordResetTokenRepository tokenRepository;
    private final PasswordService passwordService;
    private final EmailService emailService;
    private final Duration tokenTtl;
    private final String resetFrontendUrl;

    public ForgotPasswordService(
            UserRepository userRepository,
            PasswordResetTokenRepository tokenRepository,
            PasswordService passwordService,
            EmailService emailService,
            @Value("${auth.password-reset.ttl:PT30M}") Duration tokenTtl,
            @Value("${auth.password-reset.frontend-url:http://localhost:3000/reset-password}") String resetFrontendUrl
    ) {
        this.userRepository = userRepository;
        this.tokenRepository = tokenRepository;
        this.passwordService = passwordService;
        this.emailService = emailService;
        this.tokenTtl = tokenTtl;
        this.resetFrontendUrl = resetFrontendUrl;
    }

    @Transactional
    public ForgotPasswordResponse processForgotPassword(String email) {
        String normalizedEmail = email.trim().toLowerCase();
        Optional<User> userOpt = userRepository.findByEmailIgnoreCase(normalizedEmail);

        if (userOpt.isEmpty()) {
            log.info("Forgot password request for non-existent email: {}", maskEmail(normalizedEmail));
            return ForgotPasswordResponse.notFound();
        }

        User user = userOpt.get();
        if (user.getStatus() != AccountStatus.ACTIVE) {
            log.info("Forgot password request for non-active user: {}", user.getUsername());
            return ForgotPasswordResponse.notFound();
        }

        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        String rawToken = generateToken();
        tokenRepository.markActiveTokensUsedForUser(user.getId(), now);
        tokenRepository.save(PasswordResetToken.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .tokenHash(hashToken(rawToken))
                .expiresAt(now.plus(tokenTtl))
                .createdAt(now)
                .build());

        emailService.sendPasswordResetLink(user.getEmail(), user.getUsername(), buildResetLink(rawToken), tokenTtl);
        log.info("Password reset link issued for user: {}", user.getUsername());
        return ForgotPasswordResponse.success();
    }

    @Transactional
    public ResetPasswordResponse resetPassword(String rawToken, String newPassword) {
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        PasswordResetToken token = tokenRepository
                .findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(hashToken(rawToken), now)
                .orElse(null);

        if (token == null) {
            return ResetPasswordResponse.invalidToken();
        }

        User user = userRepository.findById(token.getUserId()).orElse(null);
        if (user == null || user.getStatus() != AccountStatus.ACTIVE) {
            return ResetPasswordResponse.invalidToken();
        }

        user.setPasswordHash(passwordService.hashPassword(newPassword));
        user.setPasswordChangedAt(now);
        user.setMustChangePassword(false);
        user.setUpdatedAt(now);
        user.setFailedLoginAttempts(0);
        user.setLockedUntil(null);
        userRepository.save(user);

        tokenRepository.markActiveTokensUsedForUser(user.getId(), now);
        log.info("Password reset completed for user: {}", user.getUsername());
        return ResetPasswordResponse.ok();
    }

    private String buildResetLink(String token) {
        return UriComponentsBuilder.fromUriString(resetFrontendUrl)
                .queryParam("token", token)
                .build()
                .toUriString();
    }

    private String generateToken() {
        byte[] bytes = new byte[32];
        SECURE_RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String hashToken(String rawToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(rawToken.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("Unable to hash password reset token", e);
        }
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 4) return "***";
        int atIndex = email.indexOf('@');
        if (atIndex <= 1) return "***" + email.substring(atIndex);
        return email.substring(0, 2) + "***" + email.substring(atIndex);
    }
}
