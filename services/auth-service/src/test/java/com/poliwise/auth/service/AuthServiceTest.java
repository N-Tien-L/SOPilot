package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.AuthUserView;
import com.poliwise.auth.dto.auth.ClientMetadata;
import com.poliwise.auth.dto.auth.LoginRequest;
import com.poliwise.auth.dto.auth.RegisterRequest;
import com.poliwise.auth.dto.auth.TokenResponse;
import com.poliwise.auth.dto.event.UserRegisteredEvent;
import com.poliwise.auth.entity.LoginHistory;
import com.poliwise.auth.entity.RefreshToken;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.LoginStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.event.AuthEventPublisher;
import com.poliwise.auth.repository.LoginHistoryRepository;
import com.poliwise.auth.repository.RefreshTokenRepository;
import com.poliwise.auth.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.server.ResponseStatusException;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @Mock
    private LoginHistoryRepository loginHistoryRepository;

    @Mock
    private JwtTokenProvider jwtTokenProvider;

    @Mock
    private RefreshTokenService refreshTokenService;

    @Mock
    private AuthEventPublisher authEventPublisher;

    private PasswordEncoder passwordEncoder;
    private AuthService authService;
    private ClientMetadata testMetadata;

    @BeforeEach
    void setUp() {
        passwordEncoder = new BCryptPasswordEncoder();
        authService = new AuthService(
                userRepository,
                refreshTokenRepository,
                loginHistoryRepository,
                passwordEncoder,
                jwtTokenProvider,
                refreshTokenService,
                authEventPublisher
        );
        testMetadata = new ClientMetadata("127.0.0.1", "Mozilla/5.0", "Desktop");
    }

    @Nested
    @DisplayName("Register Tests")
    class RegisterTests {

        @Test
        @DisplayName("Should register new user successfully")
        void register_NewUser_Success() {
            RegisterRequest request = new RegisterRequest("testuser", "test@example.com", "Password123!", UserRole.USER);
            UUID registeredBy = UUID.randomUUID();

            when(userRepository.existsByUsernameIgnoreCase("testuser")).thenReturn(false);
            when(userRepository.existsByEmailIgnoreCase("test@example.com")).thenReturn(false);
            when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

            AuthUserView result = authService.register(request, registeredBy);

            assertNotNull(result);
            assertEquals("testuser", result.username());
            assertEquals("test@example.com", result.email());
            assertEquals(UserRole.USER, result.role());
            assertEquals(AccountStatus.ACTIVE, result.status());
            assertEquals(registeredBy, result.registeredBy());

            verify(userRepository).save(any(User.class));
        }

        @Test
        @DisplayName("Should register with default USER role when role is null")
        void register_DefaultRole_User() {
            RegisterRequest request = new RegisterRequest("testuser", "test@example.com", "Password123!", null);

            when(userRepository.existsByUsernameIgnoreCase("testuser")).thenReturn(false);
            when(userRepository.existsByEmailIgnoreCase("test@example.com")).thenReturn(false);
            when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

            AuthUserView result = authService.register(request, null);

            assertEquals(UserRole.USER, result.role());
        }

        @Test
        @DisplayName("Should register MANAGER role successfully")
        void register_ManagerRole_Success() {
            RegisterRequest request = new RegisterRequest("manager", "manager@example.com", "Password123!", UserRole.MANAGER);

            when(userRepository.existsByUsernameIgnoreCase("manager")).thenReturn(false);
            when(userRepository.existsByEmailIgnoreCase("manager@example.com")).thenReturn(false);
            when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

            AuthUserView result = authService.register(request, null);

            assertEquals(UserRole.MANAGER, result.role());
        }

        @Test
        @DisplayName("Should throw conflict when username exists")
        void register_UsernameExists_ThrowsConflict() {
            RegisterRequest request = new RegisterRequest("existinguser", "test@example.com", "Password123!", UserRole.USER);

            when(userRepository.existsByUsernameIgnoreCase("existinguser")).thenReturn(true);

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.register(request, null));
            assertEquals(409, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should throw conflict when email exists")
        void register_EmailExists_ThrowsConflict() {
            RegisterRequest request = new RegisterRequest("testuser", "existing@example.com", "Password123!", UserRole.USER);

            when(userRepository.existsByUsernameIgnoreCase("testuser")).thenReturn(false);
            when(userRepository.existsByEmailIgnoreCase("existing@example.com")).thenReturn(true);

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.register(request, null));
            assertEquals(409, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should publish UserRegisteredEvent after registration")
        void register_PublishesEvent() {
            RegisterRequest request = new RegisterRequest("testuser", "test@example.com", "Password123!", UserRole.USER);
            UUID registeredBy = UUID.randomUUID();

            when(userRepository.existsByUsernameIgnoreCase("testuser")).thenReturn(false);
            when(userRepository.existsByEmailIgnoreCase("test@example.com")).thenReturn(false);
            when(userRepository.save(any(User.class))).thenAnswer(invocation -> invocation.getArgument(0));

            authService.register(request, registeredBy);

            ArgumentCaptor<UserRegisteredEvent> eventCaptor = ArgumentCaptor.forClass(UserRegisteredEvent.class);
            verify(authEventPublisher).publishUserRegistered(eventCaptor.capture());

            UserRegisteredEvent event = eventCaptor.getValue();
            assertEquals("testuser", event.username());
            assertEquals("test@example.com", event.email());
            assertEquals(UserRole.USER, event.role());
            assertEquals(registeredBy, event.registeredBy());
        }
    }

    @Nested
    @DisplayName("Login Tests")
    class LoginTests {

        @Test
        @DisplayName("Should login successfully with valid credentials")
        void login_ValidCredentials_Success() {
            String rawPassword = "Password123!";
            User user = createTestUser(AccountStatus.ACTIVE, rawPassword);

            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("testuser", "testuser"))
                    .thenReturn(Optional.of(user));
            when(jwtTokenProvider.getAccessTokenTtl()).thenReturn(java.time.Duration.ofMinutes(15));
            when(jwtTokenProvider.createAccessToken(user)).thenReturn("mock-access-token");
            when(refreshTokenService.createRefreshToken(eq(user), any(ClientMetadata.class)))
                    .thenReturn("mock-refresh-token");

            LoginRequest request = new LoginRequest("testuser", rawPassword);
            TokenResponse response = authService.login(request, testMetadata);

            assertNotNull(response);
            assertEquals("mock-access-token", response.accessToken());
            assertEquals("mock-refresh-token", response.refreshToken());
            assertEquals("Bearer", response.tokenType());
            verify(loginHistoryRepository).save(any(LoginHistory.class));
        }

        @Test
        @DisplayName("Should throw unauthorized when user not found")
        void login_UserNotFound_ThrowsUnauthorized() {
            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("unknown", "unknown"))
                    .thenReturn(Optional.empty());

            LoginRequest request = new LoginRequest("unknown", "Password123!");

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.login(request, testMetadata));
            assertEquals(401, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should throw forbidden when account is deactivated")
        void login_DeactivatedAccount_ThrowsForbidden() {
            User user = createTestUser(AccountStatus.DEACTIVATED, "Password123!");

            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("testuser", "testuser"))
                    .thenReturn(Optional.of(user));

            LoginRequest request = new LoginRequest("testuser", "Password123!");

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.login(request, testMetadata));
            assertEquals(403, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should throw forbidden when account is revoked")
        void login_RevokedAccount_ThrowsForbidden() {
            User user = createTestUser(AccountStatus.REVOKED, "Password123!");

            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("testuser", "testuser"))
                    .thenReturn(Optional.of(user));

            LoginRequest request = new LoginRequest("testuser", "Password123!");

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.login(request, testMetadata));
            assertEquals(403, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should throw unauthorized when password is wrong")
        void login_WrongPassword_ThrowsUnauthorized() {
            User user = createTestUser(AccountStatus.ACTIVE, "Password123!");

            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("testuser", "testuser"))
                    .thenReturn(Optional.of(user));

            LoginRequest request = new LoginRequest("testuser", "WrongPassword!");

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.login(request, testMetadata));
            assertEquals(401, exception.getStatusCode().value());
        }

        @Test
        @DisplayName("Should lock account after 5 failed attempts")
        void login_FiveFailedAttempts_LocksAccount() {
            User user = createTestUser(AccountStatus.ACTIVE, "Password123!");
            user.setFailedLoginAttempts(4);

            when(userRepository.findByUsernameIgnoreCaseOrEmailIgnoreCase("testuser", "testuser"))
                    .thenReturn(Optional.of(user));

            LoginRequest request = new LoginRequest("testuser", "WrongPassword!");

            ResponseStatusException exception = assertThrows(ResponseStatusException.class,
                    () -> authService.login(request, testMetadata));
            assertEquals(401, exception.getStatusCode().value());

            ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
            verify(userRepository).save(userCaptor.capture());
            assertNotNull(userCaptor.getValue().getLockedUntil());
            assertEquals(0, userCaptor.getValue().getFailedLoginAttempts());
        }
    }

    @Nested
    @DisplayName("Logout Tests")
    class LogoutTests {

        @Test
        @DisplayName("Should logout successfully")
        void logout_Success() {
            String rawRefreshToken = "refresh-token";
            String rawAccessToken = "access-token";
            UUID userId = UUID.randomUUID();

            authService.logout(rawRefreshToken, userId, rawAccessToken);

            verify(refreshTokenService).revoke(rawRefreshToken, userId, "LOGOUT");
            verify(jwtTokenProvider).blacklistToken(rawAccessToken, userId, "LOGOUT");
        }

        @Test
        @DisplayName("Should logout all devices successfully")
        void logoutAllDevices_Success() {
            UUID userId = UUID.randomUUID();

            when(refreshTokenService.revokeAll(userId, "LOGOUT_ALL_DEVICES")).thenReturn(5);

            int count = authService.logoutAllDevices(userId, "access-token");

            assertEquals(5, count);
            verify(refreshTokenService).revokeAll(userId, "LOGOUT_ALL_DEVICES");
            verify(jwtTokenProvider).blacklistToken("access-token", userId, "LOGOUT_ALL_DEVICES");
        }
    }

    private User createTestUser(AccountStatus status, String rawPassword) {
        return User.builder()
                .id(UUID.randomUUID())
                .username("testuser")
                .email("test@example.com")
                .passwordHash(passwordEncoder.encode(rawPassword))
                .role(UserRole.USER)
                .status(status)
                .failedLoginAttempts(0)
                .mustChangePassword(false)
                .passwordChangedAt(OffsetDateTime.now())
                .createdAt(OffsetDateTime.now())
                .updatedAt(OffsetDateTime.now())
                .build();
    }
}