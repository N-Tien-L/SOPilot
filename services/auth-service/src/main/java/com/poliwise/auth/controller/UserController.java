package com.poliwise.auth.controller;

import com.poliwise.auth.dto.auth.*;
import com.poliwise.auth.security.JwtAuthenticationToken;
import com.poliwise.auth.service.UserManagementService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private final UserManagementService userManagementService;

    public UserController(UserManagementService userManagementService) {
        this.userManagementService = userManagementService;
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> createUser(
            @Valid @RequestBody UserCreateRequest request,
            @AuthenticationPrincipal JwtAuthenticationToken authToken,
            HttpServletRequest httpRequest
    ) {
        UUID createdBy = authToken != null ? authToken.getPayload().sub() : null;
        AuthUserView user = userManagementService.createUser(request, createdBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(user);
    }

    @PostMapping("/bulk")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> createBulkUsers(
            @Valid @RequestBody BulkUserCreateRequest request,
            @AuthenticationPrincipal JwtAuthenticationToken authToken
    ) {
        UUID createdBy = authToken != null ? authToken.getPayload().sub() : null;
        BulkUserCreateResponse result = userManagementService.createBulkUsers(request, createdBy);
        return ResponseEntity.status(HttpStatus.CREATED).body(result);
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN') or hasRole('MANAGER')")
    public ResponseEntity<?> searchUsers(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) UUID departmentId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int limit
    ) {
        // Convert from 1-based (frontend) to 0-based (Spring Pageable)
        int pageNumber = Math.max(0, page - 1);
        Pageable pageable = PageRequest.of(pageNumber, Math.min(limit, 100));
        Page<UserBasicView> users = userManagementService.searchUsers(search, role, status, departmentId, pageable);
        return ResponseEntity.ok(Map.of(
                "data", users.getContent(),
                "pagination", Map.of(
                        "page", users.getNumber() + 1,  // Convert back to 1-based for frontend
                        "limit", users.getSize(),
                        "total", users.getTotalElements(),
                        "totalPages", users.getTotalPages()
                )
        ));
    }

    @GetMapping("/{userId}")
    @PreAuthorize("hasRole('ADMIN') or #userId.toString() == authentication.principal.sub")
    public ResponseEntity<?> getUser(@PathVariable UUID userId) {
        UserDetailView user = userManagementService.getUserById(userId);
        return ResponseEntity.ok(user);
    }

    @PutMapping("/{userId}")
    @PreAuthorize("hasRole('ADMIN') or #userId.toString() == authentication.principal.sub")
    public ResponseEntity<?> updateUser(
            @PathVariable UUID userId,
            @Valid @RequestBody UserUpdateRequest request,
            @AuthenticationPrincipal JwtAuthenticationToken authToken
    ) {
        UUID updatedBy = authToken != null ? authToken.getPayload().sub() : null;
        UserDetailView user = userManagementService.updateUser(userId, request, updatedBy);
        return ResponseEntity.ok(user);
    }

    @PostMapping("/{userId}/deactivate")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> deactivateUser(@PathVariable UUID userId) {
        userManagementService.deactivateUser(userId);
        return ResponseEntity.ok(MessageResponse.ok("User deactivated successfully"));
    }

    @PostMapping("/{userId}/reactivate")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> reactivateUser(@PathVariable UUID userId) {
        userManagementService.reactivateUser(userId);
        return ResponseEntity.ok(MessageResponse.ok("User reactivated successfully"));
    }

    @PostMapping("/{userId}/revoke")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> revokeUser(@PathVariable UUID userId) {
        userManagementService.revokeUser(userId);
        return ResponseEntity.ok(MessageResponse.ok("User revoked successfully"));
    }

    @DeleteMapping("/{userId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<?> deleteUser(@PathVariable UUID userId) {
        userManagementService.deleteUser(userId);
        return ResponseEntity.ok(MessageResponse.ok("User deleted successfully"));
    }

    @GetMapping("/{userId}/login-history")
    public ResponseEntity<?> getLoginHistory(
            @PathVariable UUID userId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int limit
    ) {
        JwtAuthenticationToken authToken = (JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication();
        
        // Check authorization: ADMIN or own user
        boolean isAdmin = authToken.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        boolean isOwnHistory = authToken.getPayload().sub().equals(userId);
        
        if (!isAdmin && !isOwnHistory) {
            throw new org.springframework.security.access.AccessDeniedException("Cannot view other user's login history");
        }
        
        int pageNumber = Math.max(0, page - 1);
        Pageable pageable = PageRequest.of(pageNumber, Math.min(limit, 100));
        Page<LoginHistoryInfo> history = userManagementService.getLoginHistory(userId, pageable);
        return ResponseEntity.ok(Map.of(
                "data", history.getContent(),
                "pagination", Map.of(
                        "page", history.getNumber() + 1,
                        "limit", history.getSize(),
                        "total", history.getTotalElements(),
                        "totalPages", history.getTotalPages()
                )
        ));
    }
}
