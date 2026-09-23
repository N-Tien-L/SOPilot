package com.poliwise.metadata.feign;

import com.poliwise.metadata.feign.dto.DepartmentDto;
import com.poliwise.metadata.feign.dto.UserDto;
import com.poliwise.metadata.feign.dto.UserPageResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.UUID;

@FeignClient(name = "user-service", url = "${app.services.user-service-url:http://localhost:8082}")
public interface UserServiceClient {

    @GetMapping("/api/v1/departments/{id}")
    DepartmentDto getDepartmentById(@PathVariable UUID id);

    @GetMapping("/api/v1/departments/active")
    List<DepartmentDto> getActiveDepartments();

    @GetMapping("/api/v1/users/{id}")
    UserDto getUserById(@PathVariable UUID id);

    @GetMapping("/api/v1/users")
    UserPageResponse searchUsers(
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "limit", defaultValue = "1000") int limit,
            @RequestParam(value = "status", defaultValue = "ACTIVE") String status
    );
}

