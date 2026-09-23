package com.poliwise.auth.feign;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import java.util.Map;

@FeignClient(
        name = "feedback-service",
        url = "${app.services.feedback-service-url:http://localhost:8085}"
)
public interface FeedbackServiceClient {

    @PostMapping("/api/v1/internal/audit/user-created")
    ResponseEntity<Void> logUserCreated(@RequestBody Map<String, Object> payload);
}
