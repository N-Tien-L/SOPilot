package com.sopilot.core.member;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.member.MemberRepository.Member;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.workspace.WorkspaceRepository.MembershipStatus;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Members of the caller's workspace (TECH §5.3). Invitations and role changes are V2-30. */
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {

    private final MemberService service;

    public MemberController(MemberService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<MemberView>> list(AuthPrincipal principal,
                                              @RequestParam(required = false) String status,
                                              @RequestParam(required = false) UUID departmentId,
                                              @RequestParam(required = false) String q) {
        MembershipStatus parsed = null;
        if (status != null && !status.isBlank()) {
            try {
                parsed = MembershipStatus.valueOf(status);
            } catch (IllegalArgumentException e) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Status must be ACTIVE or SUSPENDED.");
            }
        }
        return ApiResponse.of(service.list(principal, parsed, departmentId, q).stream().map(MemberView::of).toList());
    }

    @GetMapping("/me")
    public ApiResponse<MemberView> me(AuthPrincipal principal) {
        return ApiResponse.of(MemberView.of(service.me(principal)));
    }

    @PatchMapping("/{userId}")
    public ApiResponse<MemberView> update(AuthPrincipal principal, @PathVariable UUID userId,
                                          @RequestBody Map<String, Object> patch) {
        return ApiResponse.of(MemberView.of(service.updateProfile(principal, userId, patch)));
    }

    @PostMapping("/{userId}/suspend")
    public ResponseEntity<Void> suspend(AuthPrincipal principal, @PathVariable UUID userId) {
        service.suspend(principal, userId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{userId}/reactivate")
    public ResponseEntity<Void> reactivate(AuthPrincipal principal, @PathVariable UUID userId) {
        service.reactivate(principal, userId);
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/{userId}")
    public ResponseEntity<Void> remove(AuthPrincipal principal, @PathVariable UUID userId) {
        service.remove(principal, userId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/leave")
    public ResponseEntity<Void> leave(AuthPrincipal principal) {
        service.leave(principal);
        return ResponseEntity.noContent().build();
    }

    public record MemberView(UUID userId, String email, String displayName, String employeeCode, String jobTitle,
                             String role, String status, UUID departmentId, String departmentName,
                             OffsetDateTime joinedAt) {
        static MemberView of(Member m) {
            return new MemberView(m.userId(), m.email(), m.displayName(), m.employeeCode(), m.jobTitle(),
                    m.role().name(), m.status().name(), m.departmentId(), m.departmentName(), m.joinedAt());
        }
    }
}
