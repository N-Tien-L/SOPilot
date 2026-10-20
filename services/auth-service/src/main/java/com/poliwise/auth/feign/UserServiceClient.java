package com.poliwise.auth.feign;

import com.poliwise.auth.dto.roster.ClaimRosterRequest;
import com.poliwise.auth.dto.roster.ClaimRosterResponse;
import com.poliwise.auth.dto.roster.AdmitGoogleLoginRequest;
import jakarta.validation.Valid;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

/**
 * OpenFeign Client connecting to user-service for employee roster JIT claims.
 * Target endpoint: POST /internal/v1/roster/claim
 */
@FeignClient(
        name = "user-service",
        url = "${app.services.user-service-url:http://localhost:8082}",
        configuration = UserServiceClientConfig.class
)
public interface UserServiceClient {

    @PostMapping("/internal/v1/roster/google-admission")
    ClaimRosterResponse admitGoogleLogin(@Valid @RequestBody AdmitGoogleLoginRequest request);

    @PostMapping("/internal/v1/roster/claim")
    ClaimRosterResponse claimRoster(@Valid @RequestBody ClaimRosterRequest request);
}
