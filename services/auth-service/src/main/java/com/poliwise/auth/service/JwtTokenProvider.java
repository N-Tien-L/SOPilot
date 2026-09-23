package com.poliwise.auth.service;

import com.poliwise.auth.config.AuthProperties;
import com.poliwise.auth.dto.auth.JwtPayload;
import com.poliwise.auth.entity.AccessTokenBlacklist;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.repository.AccessTokenBlacklistRepository;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.SignatureException;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class JwtTokenProvider {

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final AuthProperties authProperties;
    private final SecretKey signingKey;
    private final AccessTokenBlacklistRepository blacklistRepository;

    public JwtTokenProvider(AuthProperties authProperties, AccessTokenBlacklistRepository blacklistRepository) {
        this.authProperties = authProperties;
        this.blacklistRepository = blacklistRepository;
        this.signingKey = Keys.hmacShaKeyFor(resolveSecretBytes(authProperties.jwt().secret()));
    }

    public String createAccessToken(User user) {
        Instant now = Instant.now();
        Instant expiresAt = now.plus(authProperties.jwt().accessTokenTtl());
        String jti = generateJti();
        String issuer = authProperties.jwt().issuer();

        return Jwts.builder()
                .subject(user.getId().toString())
                .id(jti)
                .issuer(issuer)
                .issuedAt(java.util.Date.from(now))
                .expiration(java.util.Date.from(expiresAt))
                .claim("username", user.getUsername())
                .claim("email", user.getEmail())
                .claim("role", user.getRole().name())
                .claim("status", user.getStatus().name())
                .claim("department", user.getDepartmentId() != null ? user.getDepartmentId().toString() : null)
                .signWith(signingKey)
                .compact();
    }

    public JwtPayload verifyAccessToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(signingKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            return buildJwtPayload(claims);
        } catch (ExpiredJwtException ex) {
            throw new JwtException("Access token has expired", ex);
        } catch (JwtException ex) {
            throw new JwtException("Invalid JWT token: " + ex.getMessage());
        }
    }

    public Optional<JwtPayload> extractPayloadIfValid(String token) {
        try {
            return Optional.of(verifyAccessToken(token));
        } catch (JwtException ex) {
            return Optional.empty();
        }
    }

    public Optional<UUID> extractUserIdIfValid(String token) {
        return extractPayloadIfValid(token).map(JwtPayload::sub);
    }

    public boolean isTokenExpired(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(signingKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return claims.getExpiration().toInstant().isBefore(Instant.now());
        } catch (ExpiredJwtException ex) {
            return true;
        } catch (JwtException ex) {
            return false;
        }
    }

    public String extractJti(String token) {
        return Jwts.parser()
                .verifyWith(signingKey)
                .build()
                .parseSignedClaims(token)
                .getPayload()
                .getId();
    }

    public Instant extractExpiry(String token) {
        return Jwts.parser()
                .verifyWith(signingKey)
                .build()
                .parseSignedClaims(token)
                .getPayload()
                .getExpiration()
                .toInstant();
    }

    @Transactional
    public void blacklistToken(String token, UUID userId, String reason) {
        String jti = extractJti(token);
        Instant expiry = extractExpiry(token);

        if (!blacklistRepository.existsByJti(jti)) {
            AccessTokenBlacklist entry = AccessTokenBlacklist.builder()
                    .jti(jti)
                    .userId(userId)
                    .expiredAt(expiry)
                    .blacklistedAt(Instant.now())
                    .reason(reason)
                    .build();
            blacklistRepository.save(entry);
        }
    }

    public boolean isTokenBlacklisted(String jti) {
        return blacklistRepository.existsByJti(jti);
    }

    public Key getSigningKey() {
        return signingKey;
    }

    public Duration getAccessTokenTtl() {
        return authProperties.jwt().accessTokenTtl();
    }

    private JwtPayload buildJwtPayload(Claims claims) {
        return new JwtPayload(
                UUID.fromString(claims.getSubject()),
                claims.get("username", String.class),
                claims.get("email", String.class),
                UserRole.valueOf(claims.get("role", String.class)),
                AccountStatus.valueOf(claims.get("status", String.class)),
                parseDepartment(claims.get("department", String.class)),
                claims.getIssuedAt().toInstant(),
                claims.getExpiration().toInstant(),
                claims.getIssuer(),
                claims.getId()
        );
    }

    private UUID parseDepartment(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return UUID.fromString(value);
    }

    private String generateJti() {
        byte[] bytes = new byte[16];
        SECURE_RANDOM.nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }

    private static byte[] resolveSecretBytes(String secret) {
        try {
            byte[] decoded = Decoders.BASE64.decode(secret);
            if (decoded.length >= 32) {
                return decoded;
            }
        } catch (Exception ignored) {
        }
        byte[] plain = secret.getBytes(StandardCharsets.UTF_8);
        if (plain.length < 32) {
            throw new IllegalArgumentException(
                    "auth.jwt.secret must be at least 32 bytes (or a base64 string decoding to >= 32 bytes)");
        }
        return plain;
    }
}
