package com.poliwise.knowledge.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class InternalStatsTokenFilter extends OncePerRequestFilter {

    static final String HEADER_NAME = "X-Service-Token";
    private static final String STATS_PATH = "/api/v1/documents/stats";

    private final byte[] expectedToken;

    public InternalStatsTokenFilter(@Value("${poliwise.service-token:}") String serviceToken) {
        this.expectedToken = serviceToken.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !STATS_PATH.equals(request.getServletPath());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        String presented = request.getHeader(HEADER_NAME);
        byte[] presentedBytes = presented == null
                ? new byte[0]
                : presented.getBytes(StandardCharsets.UTF_8);

        if (expectedToken.length == 0 || !MessageDigest.isEqual(expectedToken, presentedBytes)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"Invalid service token\"}");
            return;
        }

        var authentication = new UsernamePasswordAuthenticationToken(
                "feedback-service",
                null,
                List.of(new SimpleGrantedAuthority("ROLE_INTERNAL")));
        SecurityContextHolder.getContext().setAuthentication(authentication);
        filterChain.doFilter(request, response);
    }
}
