package com.sopilot.core.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.ApiErrorResponse;
import com.sopilot.core.config.InternalProperties;
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
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

/**
 * Guards {@code /internal/**} with {@code X-Internal-Token} (TECH §8), compared in constant time.
 * With no token configured every call is rejected. These routes are never exposed to browsers.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 11)
public class InternalTokenFilter extends OncePerRequestFilter {

    private final byte[] expected;
    private final ObjectMapper mapper;

    public InternalTokenFilter(InternalProperties properties, ObjectMapper mapper) {
        this.expected = properties.token().getBytes(StandardCharsets.UTF_8);
        this.mapper = mapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/internal/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String given = request.getHeader("X-Internal-Token");
        boolean ok = expected.length > 0 && given != null
                && MessageDigest.isEqual(given.getBytes(StandardCharsets.UTF_8), expected);
        if (!ok) {
            response.setStatus(HttpStatus.UNAUTHORIZED.value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            mapper.writeValue(response.getOutputStream(), ApiErrorResponse.of(
                    "UNAUTHENTICATED", "Invalid internal token.", Map.of()));
            return;
        }
        chain.doFilter(request, response);
    }
}
