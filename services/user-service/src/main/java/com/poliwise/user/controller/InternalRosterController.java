package com.poliwise.user.controller;

import com.poliwise.user.dto.roster.ClaimRosterRequest;
import com.poliwise.user.dto.roster.ClaimRosterResponse;
import com.poliwise.user.dto.roster.AdmitGoogleLoginRequest;
import com.poliwise.user.service.EmployeeRosterService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Controller phục vụ giao tiếp nội bộ giữa các microservices (Internal Service-to-Service).
 * Được gọi bởi auth-service khi thực hiện quy trình Google OAuth JIT Claim.
 * Bảo vệ bởi InternalServiceAuthFilter (yêu cầu ROLE_INTERNAL).
 */
@RestController
@RequestMapping("/internal/v1/roster")
@PreAuthorize("hasRole('INTERNAL')")
public class InternalRosterController {

    private final EmployeeRosterService employeeRosterService;

    public InternalRosterController(EmployeeRosterService employeeRosterService) {
        this.employeeRosterService = employeeRosterService;
    }

    @PostMapping("/google-admission")
    public ResponseEntity<ClaimRosterResponse> admitGoogleLogin(@Valid @RequestBody AdmitGoogleLoginRequest request) {
        return ResponseEntity.ok(employeeRosterService.admitGoogleLogin(request));
    }

    /**
     * Thực hiện kiểm tra và claim danh bạ nhân sự nguyên tử (Atomic JIT Claim).
     * POST /internal/v1/roster/claim
     */
    @PostMapping("/claim")
    public ResponseEntity<ClaimRosterResponse> claimRoster(@Valid @RequestBody ClaimRosterRequest request) {
        ClaimRosterResponse response = employeeRosterService.claimRoster(request);
        return ResponseEntity.ok(response);
    }
}
