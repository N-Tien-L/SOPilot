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

        String internalService = request.getHeader(INTERNAL_SERVICE_HEADER);

        if (internalService != null && !internalService.isBlank()) {
            if (!internalService.equals(serviceToken)) {
                log.warn("Internal service call with invalid token: service={}", internalService);
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Invalid internal service token");
                return;
            }

            log.debug("Internal service call authenticated: service={}", internalService);
            var authentication = new UsernamePasswordAuthenticationToken(
                    SERVICE_NAME + ":" + internalService,
                    null,
                    List.of(
                            new SimpleGrantedAuthority("ROLE_INTERNAL"),
                            new SimpleGrantedAuthority("ROLE_" + internalService.toUpperCase().replace("-", "_"))
                    )
            );
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
            return;
        }

        filterChain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // Only filter API paths
        return !request.getServletPath().startsWith("/api/");
    }
}
