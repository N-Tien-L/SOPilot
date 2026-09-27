package com.poliwise.auth.feign;

import com.poliwise.auth.exception.RosterDeactivatedException;
import com.poliwise.auth.exception.RosterNotFoundException;
import feign.RequestInterceptor;
import feign.Response;
import feign.codec.ErrorDecoder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;

public class UserServiceClientConfig {

    private static final Logger log = LoggerFactory.getLogger(UserServiceClientConfig.class);
    private static final String HEADER_INTERNAL_SERVICE = "X-Internal-Service";

    @Bean
    public RequestInterceptor internalServiceRequestInterceptor(
            @Value("${poliwise.service-token:sopilot-internal-service-token}") String serviceToken) {
        return requestTemplate -> {
            requestTemplate.header(HEADER_INTERNAL_SERVICE, serviceToken);
        };
    }

    @Bean
    public ErrorDecoder userServiceErrorDecoder() {
        return new ErrorDecoder() {
            private final ErrorDecoder defaultDecoder = new Default();

            @Override
            public Exception decode(String methodKey, Response response) {
                int status = response.status();
                log.warn("UserServiceClient error on {}: HTTP status {}", methodKey, status);

                if (status == 404) {
                    return new RosterNotFoundException(
                            "Tài khoản chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR.");
                }

                if (status == 403) {
                    return new RosterDeactivatedException(
                            "Định danh nhân sự của tài khoản này đã bị vô hiệu hóa. Vui lòng liên hệ HR.");
                }

                return defaultDecoder.decode(methodKey, response);
            }
        };
    }
}
