package com.poliwise.auth.config;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Order(1)
public class RateLimitingFilter implements Filter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitingFilter.class);

    private static final int LOGIN_WINDOW_SECONDS = 60;
    private static final int LOGIN_MAX_ATTEMPTS = 5;
    private static final int FORGOT_PASSWORD_WINDOW_SECONDS = 300;
    private static final int FORGOT_PASSWORD_MAX_ATTEMPTS = 3;

    private final Map<String, RateLimitEntry> loginAttempts = new ConcurrentHashMap<>();
    private final Map<String, RateLimitEntry> forgotPasswordAttempts = new ConcurrentHashMap<>();
    private volatile long cleanupCounter = 0;

    @Override
    public void doFilter(ServletRequest servletRequest, ServletResponse servletResponse, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest request = (HttpServletRequest) servletRequest;
        HttpServletResponse response = (HttpServletResponse) servletResponse;

        String path = request.getRequestURI();
        String ip = resolveIpAddress(request);

        if (path.equals("/api/v1/auth/login") && request.getMethod().equalsIgnoreCase("POST")) {
            if (!checkRateLimit(ip, loginAttempts, LOGIN_WINDOW_SECONDS, LOGIN_MAX_ATTEMPTS, response, "login")) {
                return;
            }
        }

        if (path.equals("/api/v1/auth/forgot-password") && request.getMethod().equalsIgnoreCase("POST")) {
            if (!checkRateLimit(ip, forgotPasswordAttempts, FORGOT_PASSWORD_WINDOW_SECONDS, FORGOT_PASSWORD_MAX_ATTEMPTS, response, "forgot-password")) {
                return;
            }
        }

        cleanupCounter++;
        if (cleanupCounter % 100 == 0) {
            cleanupExpiredEntries();
        }

        chain.doFilter(request, response);
    }

    private boolean checkRateLimit(
            String ip,
            Map<String, RateLimitEntry> store,
            int windowSeconds,
            int maxAttempts,
            HttpServletResponse response,
            String action
    ) throws IOException {
        long now = Instant.now().getEpochSecond();
        long windowStart = now - windowSeconds;

        RateLimitEntry entry = store.compute(ip, (key, existing) -> {
            if (existing == null || existing.windowStart < windowStart) {
                return new RateLimitEntry(now, 1);
            } else {
                return new RateLimitEntry(existing.windowStart, existing.count + 1);
            }
        });

        if (entry.count > maxAttempts) {
            long retryAfter = windowStart + windowSeconds - now + 1;
            log.warn("Rate limit exceeded for IP {} on {}: {} attempts in window", ip, action, entry.count);

            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setHeader("X-RateLimit-Limit", String.valueOf(maxAttempts));
            response.setHeader("X-RateLimit-Remaining", "0");
            response.setHeader("X-RateLimit-Reset", String.valueOf(windowStart + windowSeconds));
            response.setHeader("Retry-After", String.valueOf(Math.max(1, retryAfter)));

            response.getWriter().write(String.format(
                    "{\"error\":\"RATE_LIMIT_EXCEEDED\",\"message\":\"Too many requests. Please try again in %d seconds.\",\"status\":429,\"retryAfter\":%d}",
                    Math.max(1, retryAfter),
                    Math.max(1, retryAfter)
            ));
            return false;
        }

        response.setHeader("X-RateLimit-Limit", String.valueOf(maxAttempts));
        response.setHeader("X-RateLimit-Remaining", String.valueOf(Math.max(0, maxAttempts - entry.count)));
        response.setHeader("X-RateLimit-Reset", String.valueOf(entry.windowStart + windowSeconds));

        return true;
    }

    private void cleanupExpiredEntries() {
        long now = Instant.now().getEpochSecond();

        loginAttempts.entrySet().removeIf(entry ->
                entry.getValue().windowStart < now - LOGIN_WINDOW_SECONDS * 2
        );
        forgotPasswordAttempts.entrySet().removeIf(entry ->
                entry.getValue().windowStart < now - FORGOT_PASSWORD_WINDOW_SECONDS * 2
        );
    }

    private String resolveIpAddress(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isBlank()) {
            return xForwardedFor.split(",")[0].trim();
        }
        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isBlank()) {
            return xRealIp.trim();
        }
        return request.getRemoteAddr();
    }

    private record RateLimitEntry(long windowStart, int count) {}
}
