package com.poliwise.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.poliwise.auth.dto.auth.AuthUserView;
import com.poliwise.auth.dto.auth.ClientMetadata;
import com.poliwise.auth.dto.auth.GoogleVerifyRequest;
import com.poliwise.auth.dto.auth.TokenResponse;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.exception.GlobalExceptionHandler;
import com.poliwise.auth.exception.RosterDeactivatedException;
import com.poliwise.auth.exception.RosterNotFoundException;
import com.poliwise.auth.repository.LoginHistoryRepository;
import com.poliwise.auth.repository.RefreshTokenRepository;
import com.poliwise.auth.repository.UserRepository;
import com.poliwise.auth.service.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class GoogleAuthControllerTest {

    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @Mock
    private AuthService authService;
    @Mock
    private RefreshTokenService refreshTokenService;
    @Mock
    private UserRepository userRepository;
    @Mock
    private RefreshTokenRepository refreshTokenRepository;
    @Mock
    private LoginHistoryRepository loginHistoryRepository;
    @Mock
    private ForgotPasswordService forgotPasswordService;
    @Mock
    private ChangePasswordService changePasswordService;
    @Mock
    private OtpService otpService;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        AuthController controller = new AuthController(
                authService,
                refreshTokenService,
                userRepository,
                refreshTokenRepository,
                loginHistoryRepository,
                forgotPasswordService,
                changePasswordService,
                otpService
        );
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    @DisplayName("POST /api/v1/auth/google/verify - Success 200 OK")
    void verifyGoogle_Success() throws Exception {
        UUID userId = UUID.randomUUID();
        AuthUserView userView = new AuthUserView(userId, "emp_user", "emp@sopilot.com", UserRole.USER, AccountStatus.ACTIVE, false, null);
        TokenResponse tokenResponse = new TokenResponse("mock-access-token", "mock-refresh-token", "Bearer", 900, userView);

        when(authService.loginWithGoogle(eq("valid-google-id-token"), any(ClientMetadata.class)))
                .thenReturn(tokenResponse);

        GoogleVerifyRequest request = new GoogleVerifyRequest("valid-google-id-token");

        mockMvc.perform(post("/api/v1/auth/google/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value("mock-access-token"))
                .andExpect(jsonPath("$.refreshToken").value("mock-refresh-token"))
                .andExpect(jsonPath("$.user.email").value("emp@sopilot.com"));
    }

    @Test
    @DisplayName("POST /api/v1/auth/google/verify - Roster not found returns 403 Forbidden")
    void verifyGoogle_RosterNotFound_Returns403() throws Exception {
        when(authService.loginWithGoogle(eq("unauthorized-token"), any(ClientMetadata.class)))
                .thenThrow(new RosterNotFoundException("Tài khoản chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR."));

        GoogleVerifyRequest request = new GoogleVerifyRequest("unauthorized-token");

        mockMvc.perform(post("/api/v1/auth/google/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("ROSTER_NOT_FOUND"))
                .andExpect(jsonPath("$.message").value("Tài khoản chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR."));
    }

    @Test
    @DisplayName("POST /api/v1/auth/google/verify - Roster deactivated returns 403 Forbidden")
    void verifyGoogle_RosterDeactivated_Returns403() throws Exception {
        when(authService.loginWithGoogle(eq("deactivated-token"), any(ClientMetadata.class)))
                .thenThrow(new RosterDeactivatedException("Định danh nhân sự của tài khoản này đã bị vô hiệu hóa. Vui lòng liên hệ HR."));

        GoogleVerifyRequest request = new GoogleVerifyRequest("deactivated-token");

        mockMvc.perform(post("/api/v1/auth/google/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("ROSTER_DEACTIVATED"));
    }

    @Test
    @DisplayName("POST /api/v1/auth/google/verify - Empty idToken returns 400 Bad Request")
    void verifyGoogle_BlankIdToken_Returns400() throws Exception {
        GoogleVerifyRequest request = new GoogleVerifyRequest("");

        mockMvc.perform(post("/api/v1/auth/google/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("VALIDATION_ERROR"));
    }
}
