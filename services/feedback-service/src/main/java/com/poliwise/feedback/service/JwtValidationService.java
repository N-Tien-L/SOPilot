package com.poliwise.feedback.service;

import com.poliwise.feedback.security.UserPrincipal;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.SignatureException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.UUID;

@Service
public class JwtValidationService {

    private static final Logger log = LoggerFactory.getLogger(JwtValidationService.class);
    private final SecretKey signingKey;

    public JwtValidationService(
            @Value("${poliwise.jwt.secret}") String jwtSecret) {
        this.signingKey = Keys.hmacShaKeyFor(resolveSecretBytes(jwtSecret));
    }

    public Optional<UserPrincipal> validateToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(signingKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            UserPrincipal principal = UserPrincipal.builder()
                    .userId(parseUUID(claims.getSubject()))
                    .username(claims.get("username", String.class))
                    .email(claims.get("email", String.class))
                    .role(claims.get("role", String.class))
                    .status(claims.get("status", String.class))
                    .departmentId(parseUUID(claims.get("department", String.class)))
                    .build();

            return Optional.of(principal);
        } catch (ExpiredJwtException ex) {
            log.debug("Token expired: {}", ex.getMessage());
            return Optional.empty();
        } catch (JwtException ex) {
            log.warn("Invalid JWT token: {}", ex.getMessage());
            return Optional.empty();
        }
    }

    private UUID parseUUID(String value) {
        if (value == null || value.isBlank()) return null;
        try { return UUID.fromString(value); }
        catch (IllegalArgumentException e) { return null; }
    }

    private byte[] resolveSecretBytes(String secret) {
        try {
            byte[] decoded = Decoders.BASE64.decode(secret);
            if (decoded.length >= 32) return decoded;
        } catch (Exception ignored) {}
        byte[] plain = secret.getBytes(StandardCharsets.UTF_8);
        if (plain.length < 32) {
            throw new IllegalArgumentException("poliwise.jwt.secret must be at least 32 bytes");
        }
        return plain;
    }
}
