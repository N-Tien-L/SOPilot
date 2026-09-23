package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.AuthUserView;
import com.poliwise.auth.dto.auth.ClientMetadata;
import com.poliwise.auth.dto.auth.JwtPayload;
import com.poliwise.auth.dto.auth.LoginRequest;
import com.poliwise.auth.dto.auth.RegisterRequest;
import com.poliwise.auth.dto.auth.TokenResponse;
import com.poliwise.auth.dto.event.UserRegisteredEvent;
import com.poliwise.auth.dto.event.LoginAuditEvent;
import com.poliwise.auth.entity.LoginHistory;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.LoginStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.event.AuthEventPublisher;
import com.poliwise.auth.feign.FeedbackServiceClient;
import com.poliwise.auth.repository.LoginHistoryRepository;
import com.poliwise.auth.repository.RefreshTokenRepository;
import com.poliwise.auth.repository.UserRepository;
import com.poliwise.auth.security.JwtAuthenticationToken;
import io.jsonwebtoken.JwtException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final Logger log = LoggerFactory.getLogger(AuthService.class);

    private final UserRepository userRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final LoginHistoryRepository loginHistoryRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenService refreshTokenService;
    private final AuthEventPublisher authEventPublisher;
    private final FeedbackServiceClient feedbackServiceClient;

    @Transactional
    public AuthUserView register(RegisterRequest request, UUID registeredBy) {
        String normalizedUsername = normalize(request.username());
        String normalizedEmail = normalize(request.email());

        if (userRepository.existsByUsernameIgnoreCase(normalizedUsername)) {
            throw conflict("Username already exists");
        }
        if (userRepository.existsByEmailIgnoreCase(normalizedEmail)) {
            throw conflict("Email already exists");
        }

        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);

        User user = User.builder()
                .id(UUID.randomUUID())
                .username(normalizedUsername)
                .email(normalizedEmail)
                .passwordHash(passwordEncoder.encode(request.password()))
                .role(request.role() == null ? UserRole.USER : request.role())
                .status(AccountStatus.ACTIVE)
                .failedLoginAttempts(0)
                .mustChangePassword(false)
                .passwordChangedAt(now)
                .createdAt(now)
                .updatedAt(now)
                .build();

        User savedUser = userRepository.save(user);

        publishUserRegisteredEvent(savedUser, registeredBy);

        return toUserView(savedUser, registeredBy);
    }

    private void publishUserRegisteredEvent(User user, UUID registeredBy) {
        try {
            // Publish to RabbitMQ
            UserRegisteredEvent event;
            if (registeredBy != null) {
                event = UserRegisteredEvent.create(
                        user.getId(),
                        user.getUsername(),
                        user.getEmail(),
                        user.getRole(),
                        registeredBy
                );
            } else {
                event = UserRegisteredEvent.createSelfRegistered(
                        user.getId(),
                        user.getUsername(),
                        user.getEmail(),
                        user.getRole()
                );
            }
            authEventPublisher.publishUserRegistered(event);
            
            // Also call feedback service directly via REST to ensure audit is logged
            try {
                Map<String, Object> payload = Map.of(
                        "actorId", registeredBy != null ? registeredBy.toString() : "",
                        "actorName", registeredBy != null ? "Admin" : "Self-registered",
                        "userId", user.getId().toString(),
                        "username", user.getUsername(),
                        "email", user.getEmail(),
                        "role", user.getRole().name()
                );
                feedbackServiceClient.logUserCreated(payload);
                log.info("Called feedback-service to log user creation: {}", user.getUsername());
            } catch (Exception e) {
                log.warn("Failed to call feedback-service for user creation audit: {}", e.getMessage());
            }
        } catch (Exception e) {
            log.error("Failed to publish UserRegisteredEvent for user {}: {}", user.getId(), e.getMessage(), e);
        }
    }

    @Transactional
    public TokenResponse login(LoginRequest request, ClientMetadata metadata) {
        String identifier = normalize(request.username());

        Optional<User> candidate = userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase(identifier, identifier);
        if (candidate.isEmpty()) {
            saveFailedHistory(null, identifier, metadata, LoginStatus.FAILED_CREDENTIALS, "USER_NOT_FOUND");
            throw unauthorized("Invalid credentials");
        }

        User user = candidate.get();

        if (user.getStatus() == AccountStatus.DEACTIVATED) {
            saveFailedHistory(user.getId(), user.getUsername(), metadata, LoginStatus.FAILED_DEACTIVATED, "ACCOUNT_DEACTIVATED");
            throw forbidden("Account is deactivated");
        }

        if (user.getStatus() == AccountStatus.REVOKED) {
            saveFailedHistory(user.getId(), user.getUsername(), metadata, LoginStatus.FAILED_REVOKED, "ACCOUNT_REVOKED");
            throw forbidden("Account is revoked");
        }

        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        if (isLocked(user, now)) {
            saveFailedHistory(user.getId(), user.getUsername(), metadata, LoginStatus.FAILED_LOCKED, "ACCOUNT_LOCKED");
            throw forbidden("Account is temporarily locked");
        }

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            processFailedLogin(user, now);
            saveFailedHistory(user.getId(), user.getUsername(), metadata, LoginStatus.FAILED_CREDENTIALS, "WRONG_PASSWORD");
            throw unauthorized("Invalid credentials");
        }

        resetLockStateIfNeeded(user, now);
        saveSuccessHistory(user, metadata);

        String accessToken = jwtTokenProvider.createAccessToken(user);
        String rawRefreshToken = refreshTokenService.createRefreshToken(user, metadata);

        return new TokenResponse(
                accessToken,
                rawRefreshToken,
                "Bearer",
                jwtTokenProvider.getAccessTokenTtl().toSeconds(),
                toUserView(user, null)
        );
    }

    @Transactional
    public TokenResponse refresh(String rawRefreshToken, ClientMetadata metadata) {
        RefreshTokenService.RefreshTokenResult result = refreshTokenService.rotate(rawRefreshToken, metadata);

        String newAccessToken = jwtTokenProvider.createAccessToken(result.user());

        return new TokenResponse(
                newAccessToken,
                result.newRawToken(),
                "Bearer",
                jwtTokenProvider.getAccessTokenTtl().toSeconds(),
                toUserView(result.user(), null)
        );
    }

    @Transactional
    public void logout(String rawRefreshToken, UUID userId, String rawAccessToken) {
        refreshTokenService.revoke(rawRefreshToken, userId, "LOGOUT");

        if (rawAccessToken != null && !rawAccessToken.isBlank()) {
            jwtTokenProvider.blacklistToken(rawAccessToken, userId, "LOGOUT");
        }

        try {
            authEventPublisher.publishLogout(
                    LoginAuditEvent.logout(userId, null, null, null)
            );
        } catch (Exception e) {
            log.warn("Failed to publish logout audit event for userId={}: {}", userId, e.getMessage());
        }
    }

    @Transactional
    public int logoutAllDevices(UUID userId, String rawAccessToken) {
        int count = refreshTokenService.revokeAll(userId, "LOGOUT_ALL_DEVICES");

        if (rawAccessToken != null && !rawAccessToken.isBlank()) {
            jwtTokenProvider.blacklistToken(rawAccessToken, userId, "LOGOUT_ALL_DEVICES");
        }

        return count;
    }

    public JwtPayload verifyAccessToken(String accessToken) {
        try {
            return jwtTokenProvider.verifyAccessToken(accessToken);
        } catch (JwtException | IllegalArgumentException ex) {
            throw unauthorized("Invalid access token");
        }
    }

    private void processFailedLogin(User user, OffsetDateTime now) {
        int attempts = (user.getFailedLoginAttempts() == null ? 0 : user.getFailedLoginAttempts()) + 1;
        user.setFailedLoginAttempts(attempts);
        user.setUpdatedAt(now);

        if (attempts >= 5) {
            user.setLockedUntil(now.plusSeconds(900));
            user.setFailedLoginAttempts(0);
        }

        userRepository.save(user);
    }

    private void resetLockStateIfNeeded(User user, OffsetDateTime now) {
        boolean changed = false;

        if (user.getFailedLoginAttempts() != null && user.getFailedLoginAttempts() > 0) {
            user.setFailedLoginAttempts(0);
            changed = true;
        }

        if (user.getLockedUntil() != null && user.getLockedUntil().isBefore(now)) {
            user.setLockedUntil(null);
            changed = true;
        }

        if (changed) {
            user.setUpdatedAt(now);
            userRepository.save(user);
        }
    }

    private boolean isLocked(User user, OffsetDateTime now) {
        return user.getLockedUntil() != null && user.getLockedUntil().isAfter(now);
    }

    private void saveSuccessHistory(User user, ClientMetadata metadata) {
        LoginHistory history = LoginHistory.builder()
                .id(UUID.randomUUID())
                .userId(user.getId())
                .username(user.getUsername())
                .ipAddress(metadata.ipAddress())
                .userAgent(metadata.userAgent())
                .deviceType(metadata.deviceInfo())
                .status(LoginStatus.SUCCESS)
                .createdAt(Instant.now())
                .build();
        loginHistoryRepository.save(history);
        publishLoginAuditEvent(user.getId(), user.getUsername(), "SUCCESS", null, metadata);
    }

    private void saveFailedHistory(UUID userId, String username, ClientMetadata metadata, LoginStatus status, String reason) {
        LoginHistory history = LoginHistory.builder()
                .id(UUID.randomUUID())
                .userId(userId)
                .username(username == null ? "unknown" : username)
                .ipAddress(metadata.ipAddress())
                .userAgent(metadata.userAgent())
                .deviceType(metadata.deviceInfo())
                .status(status)
                .failureReason(reason)
                .createdAt(Instant.now())
                .build();
        loginHistoryRepository.save(history);
        publishLoginAuditEvent(userId, username, "FAILED", reason, metadata);
    }

    private void publishLoginAuditEvent(UUID userId, String username, String status, String reason, ClientMetadata metadata) {
        try {
            LoginAuditEvent event = new LoginAuditEvent(
                    UUID.randomUUID(),
                    userId,
                    username,
                    status,
                    reason,
                    metadata.ipAddress(),
                    metadata.userAgent(),
                    OffsetDateTime.now()
            );
            if ("SUCCESS".equals(status)) {
                authEventPublisher.publishLoginSuccess(event);
            } else if ("LOGOUT".equals(status)) {
                authEventPublisher.publishLogout(event);
            } else {
                authEventPublisher.publishLoginFailed(event);
            }
        } catch (Exception e) {
            log.warn("Failed to publish login audit event for user {}: {}", username, e.getMessage());
        }
    }

    private AuthUserView toUserView(User user, UUID registeredBy) {
        return new AuthUserView(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getRole(),
                user.getStatus(),
                user.getMustChangePassword(),
                registeredBy
        );
    }

    public JwtAuthenticationToken extractToken(String rawToken) {
        JwtPayload payload = jwtTokenProvider.verifyAccessToken(rawToken);
        return new JwtAuthenticationToken(payload, rawToken, buildAuthorities(payload.role()));
    }

    private List<GrantedAuthority> buildAuthorities(UserRole role) {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase();
    }

    private ResponseStatusException unauthorized(String message) {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, message);
    }

    private ResponseStatusException forbidden(String message) {
        return new ResponseStatusException(HttpStatus.FORBIDDEN, message);
    }

    private ResponseStatusException conflict(String message) {
        return new ResponseStatusException(HttpStatus.CONFLICT, message);
    }
}
