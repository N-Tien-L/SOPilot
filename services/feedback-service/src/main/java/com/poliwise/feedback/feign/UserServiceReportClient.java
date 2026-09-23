package com.poliwise.feedback.feign;

import com.poliwise.feedback.config.InternalServiceFeignConfig;
import com.poliwise.feedback.feign.dto.DepartmentListResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@FeignClient(
        name = "user-service",
        url = "${app.services.user-service-url:http://localhost:8082}",
        configuration = InternalServiceFeignConfig.class)
public interface UserServiceReportClient {

    @GetMapping("/api/v1/departments")
    List<DepartmentListResponse> getAllDepartments();
}
