package com.poliwise.metadata.security;

import com.poliwise.metadata.enums.UserRole;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.UUID;

public final class SecurityUtils {

    private SecurityUtils() {}

    public static UUID getCurrentUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getUserId();
        }
        throw new IllegalStateException("No authenticated user context available");
    }

    public static String getCurrentUsername() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getUsername();
        }
        throw new IllegalStateException("No authenticated user context available");
    }

    public static UUID getCurrentDepartmentId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getDepartment();
        }
        throw new IllegalStateException("No authenticated user context available");
    }

    public static UserRole getCurrentUserRole() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getRole();
        }
        throw new IllegalStateException("No authenticated user context available");
    }

    public static String getCurrentToken() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return jwt.getCredentials().toString();
        }
        throw new IllegalStateException("No authenticated user context available");
    }

    public static String getCurrentUserIdStr() {
        UUID id = getCurrentUserId();
        return id != null ? id.toString() : null;
    }
}
