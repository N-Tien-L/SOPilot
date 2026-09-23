package com.poliwise.auth.config;

import com.poliwise.auth.security.JwtAuthenticationEntryPoint;
import com.poliwise.auth.security.JwtAuthenticationFilter;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.security.web.util.matcher.OrRequestMatcher;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter,
                          JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
        this.jwtAuthenticationEntryPoint = jwtAuthenticationEntryPoint;
    }

    /**
     * Public endpoints: login, register, refresh, forgot-password, actuator.
     * Uses securityMatcher + OrRequestMatcher so AuthorizationManager is NEVER invoked.
     */
    @Bean
    public SecurityFilterChain publicSecurityFilterChain(HttpSecurity http) throws Exception {
        RequestMatcher publicMatcher = new OrRequestMatcher(List.of(
                new AntPathRequestMatcher("/api/v1/auth/login"),
                new AntPathRequestMatcher("/api/v1/auth/register"),
                new AntPathRequestMatcher("/api/v1/auth/refresh"),
                new AntPathRequestMatcher("/api/v1/auth/forgot-password"),
                new AntPathRequestMatcher("/api/v1/auth/send-otp"),
                new AntPathRequestMatcher("/api/v1/auth/verify-otp"),
                new AntPathRequestMatcher("/api/v1/auth/reset-password"),
                new AntPathRequestMatcher("/actuator/**"),
                new AntPathRequestMatcher("/**", "OPTIONS")
        ));

        return http
                .securityMatcher(publicMatcher)
                .csrf(AbstractHttpConfigurer::disable)
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().permitAll())
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
                .build();
    }

    /**
     * All other endpoints: require authentication via AuthorizationManager.
     */
    @Bean
    public SecurityFilterChain authenticatedSecurityFilterChain(HttpSecurity http) throws Exception {
        return http
                .csrf(AbstractHttpConfigurer::disable)
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(jwtAuthenticationEntryPoint)
                        .accessDeniedHandler((request, response, accessDeniedException) -> {
                            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                            response.setContentType("application/json");
                            response.getWriter().write(
                                    "{\"error\":\"Forbidden\",\"message\":\"" + accessDeniedException.getMessage() + "\",\"status\":401,\"path\":\"" + request.getServletPath() + "\"}");
                        })
                )
                .authorizeHttpRequests(authorize -> authorize.anyRequest().authenticated())
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
                .build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        // Restrict CORS to frontend origin - use environment variable for flexibility
        String frontendOrigin = System.getenv().getOrDefault("FRONTEND_ORIGIN", "http://localhost:3000");
        config.setAllowedOriginPatterns(List.of(frontendOrigin));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true);
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
