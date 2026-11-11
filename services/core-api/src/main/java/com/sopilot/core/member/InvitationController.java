package com.sopilot.core.member;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.identity.AuthCookies;
import com.sopilot.core.identity.IdentityService.LoginSession;
import com.sopilot.core.identity.RefreshTokenService;
import com.sopilot.core.identity.dto.LoginResponse;
import com.sopilot.core.member.InvitationRepository.Invitation;
import com.sopilot.core.member.InvitationService.CreateCommand;
import com.sopilot.core.member.InvitationService.Created;
import com.sopilot.core.security.AuthPrincipal;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** Invitations (TECH §5.3). Bulk CSV import (FR-24) is deferred, see TECH §15 notes. */
@RestController
@RequestMapping("/api/v1/invitations")
public class InvitationController {

    private final InvitationService service;
    private final AuthCookies cookies;
    private final RefreshTokenService refreshTokens;

    public InvitationController(InvitationService service, AuthCookies cookies, RefreshTokenService refreshTokens) {
        this.service = service;
        this.cookies = cookies;
        this.refreshTokens = refreshTokens;
    }

    @GetMapping
    public ApiResponse<List<InvitationView>> list(AuthPrincipal principal) {
        return ApiResponse.of(service.listPending(principal).stream().map(InvitationView::of).toList());
    }

    @PostMapping
    public ResponseEntity<ApiResponse<Created>> create(AuthPrincipal principal,
                                                       @Valid @RequestBody CreateRequest request) {
        Created created = service.create(principal, new CreateCommand(request.email(), request.role(),
                request.displayName(), request.departmentId(), request.employeeCode(), request.jobTitle()));
        return ResponseEntity.status(HttpStatus.CREATED).cacheControl(CacheControl.noStore())
                .body(ApiResponse.of(created));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> revoke(AuthPrincipal principal, @PathVariable UUID id) {
        service.revoke(principal, id);
        return ResponseEntity.noContent().build();
    }

    /** Signs the caller into the workspace they joined: same body and refresh cookie as a workspace switch. */
    @PostMapping("/accept")
    public ResponseEntity<ApiResponse<LoginResponse>> accept(
            AuthPrincipal principal,
            @RequestBody AcceptRequest request,
            @CookieValue(name = AuthCookies.REFRESH_COOKIE, required = false) String refreshCookie) {
        LoginSession session = service.accept(principal, request.invitationToken(), request.invitationId(),
                refreshCookie);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .header(HttpHeaders.SET_COOKIE, cookies.refreshCookie(session.refreshToken(), refreshTokens.ttl()))
                .body(ApiResponse.of(session.response()));
    }

    public record CreateRequest(@NotNull String email, @NotNull String role, String displayName, UUID departmentId,
                                String employeeCode, String jobTitle) {
    }

    /** Exactly one of the two fields; {@code invitationToken} is a secret and is never logged. */
    public record AcceptRequest(String invitationToken, UUID invitationId) {
        @Override
        public String toString() {
            return "AcceptRequest[invitationToken=<redacted>, invitationId=" + invitationId + "]";
        }
    }

    public record InvitationView(UUID id, String email, String role, String displayName, String employeeCode,
                                 String jobTitle, UUID departmentId, String departmentName, UUID invitedBy,
                                 OffsetDateTime expiresAt, OffsetDateTime createdAt) {
        static InvitationView of(Invitation i) {
            return new InvitationView(i.id(), i.email(), i.role(), i.displayName(), i.employeeCode(), i.jobTitle(),
                    i.departmentId(), i.departmentName(), i.invitedBy(), i.expiresAt(), i.createdAt());
        }
    }
}
