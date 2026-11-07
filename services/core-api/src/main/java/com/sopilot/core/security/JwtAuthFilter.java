package com.sopilot.core.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.ApiErrorResponse;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Map;
import java.util.Optional;

/**
 * Requires a valid {@code Authorization: Bearer} access token on every {@code /api/v1/**} route
 * except {@code /api/v1/auth/**} (TECH §5.0). The verified principal is stored as a request
 * attribute; tenant and user for RLS come from it and nowhere else.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class JwtAuthFilter extends OncePerRequestFilter {

    public static final String ATTRIBUTE = JwtAuthFilter.class.getName() + ".principal";
    private static final String BEARER = "Bearer ";

    private final AccessTokenVerifier verifier;
    private final ObjectMapper mapper;

    public JwtAuthFilter(AccessTokenVerifier verifier, ObjectMapper mapper) {
        this.verifier = verifier;
        this.mapper = mapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !path.startsWith("/api/v1/") || path.startsWith("/api/v1/auth/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        Optional<AuthPrincipal> principal = header != null && header.startsWith(BEARER)
                ? verifier.verify(header.substring(BEARER.length()).trim())
                : Optional.empty();
        if (principal.isEmpty()) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            mapper.writeValue(response.getOutputStream(), ApiErrorResponse.of(
                    "UNAUTHENTICATED", "Sign in to continue.", Map.of()));
            return;
        }
        request.setAttribute(ATTRIBUTE, principal.get());
        chain.doFilter(request, response);
    }
}
