package com.poliwise.user.controller;

import com.poliwise.user.dto.*;
import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.service.UserService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    // ─── GET PROFILE ───────────────────────────────────────────────────────────

    /**
     * Lấy profile của chính mình (self-service).
     * Mọi authenticated user đều có quyền.
     */
    @GetMapping("/me")
    public ResponseEntity<UserResponse> getMyProfile(
            @RequestHeader("X-User-Id") UUID userId) {
        return ResponseEntity.ok(userService.getProfile(userId));
    }

    /**
     * Lấy profile của bất kỳ user nào (Admin/Manager).
     */
    @GetMapping("/{userId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<UserResponse> getUserProfile(
            @PathVariable UUID userId,
            @RequestHeader(value = "X-User-Id", required = false) UUID requesterId) {
        return ResponseEntity.ok(userService.getProfileAdmin(userId));
    }

    // ─── UPDATE PROFILE ────────────────────────────────────────────────────────

    /**
     * Cập nhật profile của chính mình.
     * User chỉ được sửa profile của mình.
     */
    @PutMapping("/me")
    public ResponseEntity<UserResponse> updateMyProfile(
            @RequestHeader("X-User-Id") UUID userId,
            @Valid @RequestBody UpdateProfileRequest request) {
        return ResponseEntity.ok(userService.updateProfile(userId, request));
    }

    /**
     * Lấy trạng thái tài khoản của chính mình.
     */
    @GetMapping("/me/status")
    public ResponseEntity<UserStatusResponse> getMyStatus(
            @RequestHeader("X-User-Id") UUID userId) {
        return ResponseEntity.ok(userService.getMyStatus(userId));
    }

    /**
     * Thay đổi phòng ban của chính mình.
     */
    // ─── SEARCH (Admin / Manager) ──────────────────────────────────────────────

    /**
     * Tìm kiếm + phân trang users.
     * Admin: xem tất cả.
     * Manager: xem tất cả.
     */
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'MANAGER')")
    public ResponseEntity<PageResponse<UserResponse>> searchUsers(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) UserRole role,
            @RequestParam(required = false) AccountStatus status,
            @RequestParam(required = false) UUID departmentId,
            @RequestParam(defaultValue = "false") Boolean includeDeleted,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "username") String sortBy,
            @RequestParam(defaultValue = "ASC") String sortDir) {

        UserSearchCriteria criteria = new UserSearchCriteria(
                keyword, role, status, departmentId, includeDeleted
        );
        return ResponseEntity.ok(userService.searchUsers(criteria, page, size, sortBy, sortDir));
    }

    // ─── CHANGE STATUS ─────────────────────────────────────────────────────────

    /**
     * Thay đổi trạng thái tài khoản (ACTIVE / DEACTIVATED / REVOKED).
     * Chỉ Admin được phép.
     */
    @PatchMapping("/{userId}/status")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> changeStatus(
            @PathVariable UUID userId,
            @Valid @RequestBody ChangeStatusRequest request,
            @RequestHeader("X-User-Id") UUID changedBy) {
        return ResponseEntity.ok(userService.changeStatus(userId, request, changedBy));
    }

    // ─── UPDATE USER (Admin) ─────────────────────────────────────────────────────

    /**
     * Cập nhật role, status, department của bất kỳ user nào.
     * Chỉ Admin được phép.
     */
    @PutMapping("/{userId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> updateUser(
            @PathVariable UUID userId,
            @Valid @RequestBody UpdateUserRequest request,
            @RequestHeader("X-User-Id") UUID changedBy) {
        return ResponseEntity.ok(userService.updateUser(userId, request, changedBy));
    }

    // ─── CHANGE STATUS (convenience aliases) ───────────────────────────────────

    @PostMapping("/{userId}/deactivate")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> deactivateUser(
            @PathVariable UUID userId,
            @RequestHeader("X-User-Id") UUID changedBy) {
        return ResponseEntity.ok(userService.changeStatus(userId,
                new ChangeStatusRequest(AccountStatus.DEACTIVATED, null), changedBy));
    }

    @PostMapping("/{userId}/reactivate")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> reactivateUser(
            @PathVariable UUID userId,
            @RequestHeader("X-User-Id") UUID changedBy) {
        return ResponseEntity.ok(userService.changeStatus(userId,
                new ChangeStatusRequest(AccountStatus.ACTIVE, null), changedBy));
    }

    @PostMapping("/{userId}/revoke")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<UserResponse> revokeUser(
            @PathVariable UUID userId,
            @RequestHeader("X-User-Id") UUID changedBy) {
        return ResponseEntity.ok(userService.changeStatus(userId,
                new ChangeStatusRequest(AccountStatus.REVOKED, null), changedBy));
    }

    // ─── STATS (internal service / Admin / Manager) ─────────────────────────────────

    @GetMapping("/stats")
    public ResponseEntity<UserStatsResponse> getStats() {
        return ResponseEntity.ok(userService.getStats());
    }

    // ─── SOFT DELETE ───────────────────────────────────────────────────────────

    /**
     * Soft delete — anonymize PII thay vì xóa vật lý.
     * Chỉ Admin được phép.
     */
    @DeleteMapping("/{userId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, String>> deleteUser(
            @PathVariable UUID userId,
            @RequestHeader("X-User-Id") UUID deletedBy) {
        userService.softDelete(userId, deletedBy);
        return ResponseEntity.ok(Map.of(
                "message", "User deleted successfully",
                "userId", userId.toString()
        ));
    }
}
