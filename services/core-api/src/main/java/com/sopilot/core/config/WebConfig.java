package com.sopilot.core.config;

import com.sopilot.core.security.PrincipalArgumentResolver;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final PrincipalArgumentResolver principals;

    public WebConfig(PrincipalArgumentResolver principals) {
        this.principals = principals;
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(principals);
    }
}
