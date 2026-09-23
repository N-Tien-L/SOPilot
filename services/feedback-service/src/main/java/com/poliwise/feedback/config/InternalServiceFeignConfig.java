package com.poliwise.feedback.config;

import feign.RequestInterceptor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class InternalServiceFeignConfig {

    @Bean
    RequestInterceptor serviceTokenInterceptor(
            @Value("${poliwise.service-token:}") String serviceToken) {
        return template -> {
            if (serviceToken.isBlank()) {
                throw new IllegalStateException("INTERNAL_SERVICE_TOKEN is required for internal stats calls");
            }
            template.header("X-Service-Token", serviceToken);
        };
    }
}
