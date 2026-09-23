package com.poliwise.auth.security;

import com.poliwise.auth.dto.auth.JwtPayload;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.service.JwtTokenProvider;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthenticationFilter.class);
    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtTokenProvider jwtTokenProvider;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        String servletPath = request.getServletPath();
        Optional<String> rawToken = extractBearerToken(request);

        // DEBUG: Log the Authorization header received
        String rawAuthHeader = request.getHeader(AUTHORIZATION_HEADER);
        log.debug("[JwtAuthFilter] path={} | authHeader={} | hasToken={}",
            servletPath,
            rawAuthHeader != null ? "Bearer <" + rawAuthHeader.substring(7, Math.min(20, rawAuthHeader.length())) + "...]" : "null/missing",
            rawToken.isPresent());

        if (rawToken.isPresent()) {
            try {
                Optional<JwtPayload> payloadOpt = jwtTokenProvider.extractPayloadIfValid(rawToken.get());

                if (payloadOpt.isPresent()) {
                    JwtPayload payload = payloadOpt.get();

                    if (payload.status() != AccountStatus.ACTIVE) {
                        log.warn("[JwtAuthFilter] Token rejected: account not ACTIVE. status={}", payload.status());
                        sendError(response, HttpServletResponse.SC_FORBIDDEN, "Account is not active");
                        return;
                    }

                    String jti = payload.jti();
                    if (jti != null && jwtTokenProvider.isTokenBlacklisted(jti)) {
                        log.warn("[JwtAuthFilter] Token rejected: token is blacklisted. jti={}", jti);
                        sendError(response, HttpServletResponse.SC_UNAUTHORIZED, "Token has been revoked");
                        return;
                    }

                    JwtAuthenticationToken authentication = new JwtAuthenticationToken(
                            payload,
                            rawToken.get(),
                            JwtAuthenticationToken.buildAuthorities(payload.role())
                    );

                    SecurityContextHolder.getContext().setAuthentication(authentication);
                    log.debug("[JwtAuthFilter] Token validated OK. sub={} username={}", payload.sub(), payload.username());
                } else {
                    log.warn("[JwtAuthFilter] Token validation returned empty payload (token invalid or expired)");
                }
            } catch (JwtException ex) {
                log.warn("[JwtAuthFilter] JwtException: {} | token={}",
                    ex.getMessage(),
                    rawToken.get().substring(0, Math.min(20, rawToken.get().length())));
                sendError(response, HttpServletResponse.SC_UNAUTHORIZED, "Invalid or expired token");
                return;
            }
        } else {
            log.debug("[JwtAuthFilter] No Bearer token found in request");
        }

        filterChain.doFilter(request, response);
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
}
