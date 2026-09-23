package com.poliwise.metadata.feign;

import com.poliwise.metadata.security.SecurityUtils;
import feign.RequestInterceptor;
import feign.RequestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class FeignAuthInterceptor implements RequestInterceptor {

    private static final Logger log = LoggerFactory.getLogger(FeignAuthInterceptor.class);

    @Override
    public void apply(RequestTemplate template) {
        try {
            var token = SecurityUtils.getCurrentToken();
            if (token != null && !token.isBlank()) {
                template.header("Authorization", "Bearer " + token);
                log.debug("Feign: added Authorization header to {} {}", template.method(), template.url());
            } else {
                log.warn("Feign: no token available in SecurityContext for {} {}", template.method(), template.url());
            }

            var userId = SecurityUtils.getCurrentUserIdStr();
            if (userId != null) {
                template.header("X-User-Id", userId);
            }

            var role = SecurityUtils.getCurrentUserRole();
            if (role != null) {
                template.header("X-User-Role", role.name());
            }

            var dept = SecurityUtils.getCurrentDepartmentId();
            if (dept != null) {
                template.header("X-Department-Id", dept.toString());
            }

            var username = SecurityUtils.getCurrentUsername();
            if (username != null) {
                template.header("X-Username", username);
            }
        } catch (Exception e) {
            log.warn("Feign: failed to extract auth context: {}", e.getMessage());
        }
    }
}
