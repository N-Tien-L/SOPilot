package com.poliwise.feedback.feign;

import com.poliwise.feedback.config.InternalServiceFeignConfig;
import com.poliwise.feedback.feign.dto.DocumentStatsResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(
        name = "knowledge-service",
        url = "${app.services.knowledge-service-url:http://localhost:8083}",
        configuration = InternalServiceFeignConfig.class)
public interface KnowledgeServiceClient {

    @GetMapping("/api/v1/documents/stats")
    DocumentStatsResponse getStats();
}
