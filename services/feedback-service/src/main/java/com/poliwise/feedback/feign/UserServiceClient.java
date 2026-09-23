package com.poliwise.feedback.feign;

import com.poliwise.feedback.config.InternalServiceFeignConfig;
import com.poliwise.feedback.feign.dto.UserStatsResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

@FeignClient(
        name = "user-service",
        url = "${app.services.user-service-url:http://localhost:8082}",
        configuration = InternalServiceFeignConfig.class)
public interface UserServiceClient {

    @GetMapping("/api/v1/users/stats")
    UserStatsResponse getStats();

    @PostMapping("/api/v1/internal/{userId}/strikes/increment")
    void incrementStrikeCount(@PathVariable String userId);

    @PostMapping("/api/v1/internal/{userId}/strikes/decrement")
    void decrementStrikeCount(@PathVariable String userId);

    @PostMapping("/api/v1/internal/{userId}/strikes/decrement")
    void decrementStrikeCount(@PathVariable String userId, @RequestParam int count);

    @PostMapping("/api/v1/internal/{userId}/strikes/reset")
    void resetStrikeCount(@PathVariable String userId);

    @GetMapping("/api/v1/internal/{userId}/strikes")
    int getStrikeCount(@PathVariable String userId);

    @PostMapping("/api/v1/internal/users/{userId}/status")
    void changeUserStatus(@PathVariable String userId, @RequestParam String status);
}
