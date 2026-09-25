package com.poliwise.user.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * Accepts internal service-to-service calls by verifying the X-Internal-Service header.
 * This allows metadata-service, feedback-service, and other internal services to call
 * user-service endpoints without requiring a user JWT token.
 *
 * IMPORTANT: This filter trusts requests from internal services behind the API gateway,
 * which has already validated the original user request. The gateway ensures only
 * authenticated users can reach these endpoints.
 */
@Component
public class InternalServiceAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(InternalServiceAuthFilter.class);
    private static final String INTERNAL_SERVICE_HEADER = "X-Internal-Service";
    private static final String INTERNAL_TOKEN_HEADER = "X-Internal-Token";
    private static final String SERVICE_NAME = "internal-service";

    private final String serviceToken;

    public InternalServiceAuthFilter(
            @Value("${poliwise.service-token:#{null}}") String serviceToken) {
        if (serviceToken == null || serviceToken.isBlank()) {
            throw new IllegalStateException(
                "poliwise.service-token (INTERNAL_SERVICE_TOKEN) must be configured; "
                    + "refusing to start with an empty internal-service token");
        }
        this.serviceToken = serviceToken;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        String path = resolvePath(request);
        String token = request.getHeader(INTERNAL_SERVICE_HEADER);
        if (token == null || token.isBlank()) {
            token = request.getHeader(INTERNAL_TOKEN_HEADER);
        }

        if (token != null && !token.isBlank()) {
            if (!token.equals(serviceToken)) {
                log.warn("Internal service call with invalid token");
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                response.setContentType("application/json");
                response.getWriter().write("{\"error\":\"Invalid internal service token\"}");
                return;
            }

            log.debug("Internal service call authenticated");
            var authentication = new UsernamePasswordAuthenticationToken(
                    SERVICE_NAME,
                    null,
                    List.of(new SimpleGrantedAuthority("ROLE_INTERNAL"))
            );
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
            return;
        }

        if (path.startsWith("/internal/")) {
            log.warn("Internal service call missing token for path: {}", path);
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"Missing internal service token\"}");
            return;
        }

        filterChain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = resolvePath(request);
        return !path.startsWith("/api/") && !path.startsWith("/internal/");
    }

    private String resolvePath(HttpServletRequest request) {
        String path = request.getServletPath();
        if (path == null || path.isBlank()) {
            path = request.getRequestURI();
        }
        return path != null ? path : "";
    }
}
