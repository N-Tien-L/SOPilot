package com.poliwise.metadata.security;

import com.poliwise.metadata.enums.UserRole;
import com.poliwise.metadata.security.AccountStatus;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.SecretKey;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.UUID;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final SecretKey signingKey;

    public JwtAuthenticationFilter(
            @Value("${poliwise.jwt.secret}") String jwtSecret,
            @Value("${poliwise.jwt.issuer}") String jwtIssuer) {
        this.signingKey = Keys.hmacShaKeyFor(resolveSecretBytes(jwtSecret));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        Optional<String> rawToken = extractBearerToken(request);

        if (rawToken.isPresent()) {
            try {
                Optional<Claims> claimsOpt = extractClaims(rawToken.get());

                if (claimsOpt.isPresent()) {
                    Claims claims = claimsOpt.get();

                    AccountStatus status = AccountStatus.valueOf(claims.get("status", String.class));
                    if (status != AccountStatus.ACTIVE) {
                        sendError(response, HttpServletResponse.SC_FORBIDDEN, "Account is not active");
                        return;
                    }

                    UUID userId = UUID.fromString(claims.getSubject());
                    String username = claims.get("username", String.class);
                    String email = claims.get("email", String.class);
                    UserRole role = UserRole.valueOf(claims.get("role", String.class));
                    UUID department = parseDepartment(claims.get("department", String.class));

                    JwtAuthenticationToken authentication = new JwtAuthenticationToken(
                            userId, username, email, role, status, department, rawToken.get(),
                            JwtAuthenticationToken.buildAuthorities(role)
                    );

                    SecurityContextHolder.getContext().setAuthentication(authentication);
                }
            } catch (JwtException | IllegalArgumentException ex) {
                sendError(response, HttpServletResponse.SC_UNAUTHORIZED, "Invalid or expired token");
                return;
            }
        }

        filterChain.doFilter(request, response);
    }

    private Optional<Claims> extractClaims(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(signingKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            return Optional.of(claims);
        } catch (ExpiredJwtException ex) {
            return Optional.empty();
        } catch (JwtException ex) {
            return Optional.empty();
        }
    }

    private Optional<String> extractBearerToken(HttpServletRequest request) {
        String header = request.getHeader(AUTHORIZATION_HEADER);
        if (StringUtils.hasText(header) && header.startsWith(BEARER_PREFIX)) {
            String token = header.substring(BEARER_PREFIX.length()).trim();
            if (!token.isEmpty()) {
                return Optional.of(token);
            }
        }
        return Optional.empty();
    }

    private void sendError(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");
        response.getWriter().write("{\"error\": \"" + message + "\", \"status\": " + status + "}");
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getServletPath();
        return path.startsWith("/actuator/")
                || path.equals("/api/v1/auth/login")
                || path.equals("/api/v1/auth/register")
                || path.equals("/api/v1/auth/refresh");
    }

    private UUID parseDepartment(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return UUID.fromString(value);
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
                    "poliwise.jwt.secret must be at least 32 bytes (or a base64 string decoding to >= 32 bytes)");
        }
        return plain;
    }
}
