package com.poliwise.auth.service;

import com.poliwise.auth.config.AuthProperties;
import com.poliwise.auth.dto.auth.ClientMetadata;
import com.poliwise.auth.dto.auth.JwtPayload;
import com.poliwise.auth.entity.RefreshToken;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.repository.RefreshTokenRepository;
import com.poliwise.auth.repository.UserRepository;
import io.jsonwebtoken.JwtException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RefreshTokenService {

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final RefreshTokenRepository refreshTokenRepository;
    private final UserRepository userRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final AuthProperties authProperties;

    public RefreshTokenService(RefreshTokenRepository refreshTokenRepository,
                               UserRepository userRepository,
                               JwtTokenProvider jwtTokenProvider,
                               AuthProperties authProperties) {
        this.refreshTokenRepository = refreshTokenRepository;
        this.userRepository = userRepository;
        this.jwtTokenProvider = jwtTokenProvider;
        this.authProperties = authProperties;
    }

    public String createRefreshToken(User user, ClientMetadata metadata) {
        String rawToken = generateOpaqueRefreshToken();
        String hashed = hashRefreshToken(rawToken);

        RefreshToken entity = RefreshToken.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .tokenHash(hashed)
                .deviceInfo(metadata.deviceInfo())
                .ipAddress(metadata.ipAddress())
                .userAgent(metadata.userAgent())
                .expiresAt(OffsetDateTime.now(ZoneOffset.UTC).plus(authProperties.refreshToken().ttl()))
                .revoked(false)
                .createdAt(OffsetDateTime.now(ZoneOffset.UTC))
                .build();

        refreshTokenRepository.save(entity);
        return rawToken;
    }

    @Transactional
    public RefreshTokenResult rotate(String rawRefreshToken, ClientMetadata metadata) {
        String hashed = hashRefreshToken(rawRefreshToken);

        RefreshToken existing = refreshTokenRepository.findByTokenHashForUpdate(hashed)
                .orElseThrow(() -> new JwtException("Invalid refresh token"));

        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        if (isExpired(existing, now)) {
            refreshTokenRepository.revokeToken(existing.getId(), now, "EXPIRED", null);
            throw new JwtException("Refresh token expired");
        }

        if (Boolean.TRUE.equals(existing.getRevoked())) {
            refreshTokenRepository.revokeAllActiveTokensByUserId(existing.getUserId(), now, "REUSE_DETECTED");
            throw new JwtException("Refresh token reuse detected — all sessions revoked");
        }

        User user = userRepository.findById(existing.getUserId())
                .orElseThrow(() -> new JwtException("User not found"));

        if (user.getStatus() != AccountStatus.ACTIVE) {
            throw new JwtException("Account is not active");
        }

        String newRawToken = generateOpaqueRefreshToken();
        String newHash = hashRefreshToken(newRawToken);

        RefreshToken newToken = RefreshToken.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .tokenHash(newHash)
                .deviceInfo(metadata.deviceInfo())
                .ipAddress(metadata.ipAddress())
                .userAgent(metadata.userAgent())
                .expiresAt(now.plus(authProperties.refreshToken().ttl()))
                .revoked(false)
                .createdAt(now)
                .build();
        refreshTokenRepository.save(newToken);

        refreshTokenRepository.revokeToken(existing.getId(), now, "ROTATION", newToken.getId());

        return new RefreshTokenResult(newRawToken, user);
    }

    @Transactional
    public void revoke(String rawRefreshToken, UUID userId, String reason) {
        String hashed = hashRefreshToken(rawRefreshToken);

        RefreshToken token = refreshTokenRepository.findByTokenHashForUpdate(hashed)
                .orElseThrow(() -> new JwtException("Invalid refresh token"));

        if (!token.getUserId().equals(userId)) {
            throw new JwtException("Token does not belong to user");
        }

        refreshTokenRepository.revokeToken(token.getId(), OffsetDateTime.now(ZoneOffset.UTC), reason, null);
    }

    @Transactional
    public int revokeAll(UUID userId, String reason) {
        return refreshTokenRepository.revokeAllActiveTokensByUserId(
                userId, OffsetDateTime.now(ZoneOffset.UTC), reason);
    }

    public List<RefreshTokenInfo> getActiveSessions(UUID userId) {
        return refreshTokenRepository.findActiveTokensByUserId(userId, OffsetDateTime.now(ZoneOffset.UTC))
                .stream()
                .map(t -> new RefreshTokenInfo(
                        t.getId(),
                        t.getDeviceInfo(),
                        t.getIpAddress(),
                        t.getCreatedAt(),
                        t.getExpiresAt()
                ))
                .toList();
    }

    @Transactional
    public void revokeSession(UUID userId, UUID sessionId) {
        refreshTokenRepository.findById(sessionId).ifPresent(token -> {
            if (!token.getUserId().equals(userId)) {
                throw new JwtException("Session does not belong to user");
            }
            refreshTokenRepository.revokeToken(
                    sessionId,
                    OffsetDateTime.now(ZoneOffset.UTC),
                    "SESSION_REVOKED",
                    null
            );
        });
    }

    private boolean isExpired(RefreshToken token, OffsetDateTime now) {
        return token.getExpiresAt() == null || !token.getExpiresAt().isAfter(now);
    }

    private String generateOpaqueRefreshToken() {
        byte[] bytes = new byte[64];
        SECURE_RANDOM.nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }

    private String hashRefreshToken(String rawRefreshToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(rawRefreshToken.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception ex) {
            throw new IllegalStateException("Cannot hash refresh token", ex);
        }
    }

    public record RefreshTokenResult(String newRawToken, User user) {}

    public record RefreshTokenInfo(
            UUID id,
            String deviceInfo,
            String ipAddress,
            OffsetDateTime createdAt,
            OffsetDateTime expiresAt
    ) {}
}
