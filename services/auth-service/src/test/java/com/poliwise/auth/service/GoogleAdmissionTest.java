package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.ClientMetadata;
import com.poliwise.auth.dto.auth.GoogleTokenPayload;
import com.poliwise.auth.dto.roster.AdmitGoogleLoginRequest;
import com.poliwise.auth.dto.roster.ClaimRosterResponse;
import com.poliwise.auth.entity.ExternalIdentity;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.exception.RosterNotFoundException;
import com.poliwise.auth.exception.RosterDeactivatedException;
import com.poliwise.auth.feign.UserServiceClient;
import com.poliwise.auth.repository.ExternalIdentityRepository;
import com.poliwise.auth.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class GoogleAdmissionTest {
    private static final String ISSUER = GoogleTokenVerifierService.CANONICAL_ISSUER;
    private static final String EMAIL = "employee@company.com";
    private static final String SUBJECT = "google-subject";
    private final ClientMetadata metadata = new ClientMetadata("127.0.0.1", "test", "test");
    @Mock private UserRepository userRepository;
    @Mock private ExternalIdentityRepository externalIdentityRepository;
    @Mock private UserServiceClient userServiceClient;
    @Mock private GoogleTokenVerifierService googleTokenVerifierService;
    @Mock private JwtTokenProvider jwtTokenProvider;
    @Mock private RefreshTokenService refreshTokenService;
    @Mock private com.poliwise.auth.repository.LoginHistoryRepository loginHistoryRepository;
    @Mock private com.poliwise.auth.event.AuthEventPublisher authEventPublisher;
    @InjectMocks private AuthService authService;
    private User user;

    @BeforeEach
    void setUp() {
        user = User.builder().id(UUID.randomUUID()).username("employee").email(EMAIL)
                .role(UserRole.USER).status(AccountStatus.ACTIVE).failedLoginAttempts(0).build();
    }

    private void validGoogle(String email) {
        when(googleTokenVerifierService.verify("id-token"))
                .thenReturn(new GoogleTokenPayload(email, SUBJECT, "Employee", null, true, true));
    }

    private ExternalIdentity link(UUID userId) {
        ExternalIdentity link = new ExternalIdentity();
        org.springframework.test.util.ReflectionTestUtils.setField(link, "userId", userId);
        org.springframework.test.util.ReflectionTestUtils.setField(link, "subject", SUBJECT);
        return link;
    }

    private void admit(UUID expectedId, String email) {
        when(userServiceClient.admitGoogleLogin(new AdmitGoogleLoginRequest(email, expectedId)))
                .thenReturn(new ClaimRosterResponse(user.getId(), user.getUsername(), user.getEmail(), "Employee",
                        UserRole.USER, null, null, null));
        when(userRepository.findByIdForUpdate(user.getId())).thenReturn(Optional.of(user));
    }

    private void issueTokens() {
        when(jwtTokenProvider.createAccessToken(user)).thenReturn("access");
        when(jwtTokenProvider.getAccessTokenTtl()).thenReturn(Duration.ofMinutes(15));
        when(refreshTokenService.createRefreshToken(user, metadata)).thenReturn("refresh");
    }

    @Test
    void login_ShouldBindSubjectAndIssueTokens_WhenFirstEnrollmentIsAdmitted() {
        // Arrange
        validGoogle(EMAIL);
        admit(null, EMAIL);
        when(externalIdentityRepository.findByIssuerAndSubject(ISSUER, SUBJECT))
                .thenReturn(Optional.empty(), Optional.of(link(user.getId())));
        issueTokens();
        // Act
        var result = authService.loginWithGoogle("id-token", metadata);
        // Assert
        assertEquals("access", result.accessToken());
        assertEquals("refresh", result.refreshToken());
        verify(externalIdentityRepository).insertIfAbsent(any(UUID.class), eq(user.getId()), eq(ISSUER), eq(SUBJECT), eq(EMAIL));
        verify(userRepository, never()).findByEmailIgnoreCase(anyString());
    }

    @Test
    void login_ShouldFollowLinkedUserAndCheckRoster_WhenEmailChanges() {
        // Arrange
        String changedEmail = "changed@company.com";
        validGoogle(changedEmail);
        when(externalIdentityRepository.findByIssuerAndSubject(ISSUER, SUBJECT)).thenReturn(Optional.of(link(user.getId())));
        admit(user.getId(), changedEmail);
        issueTokens();
        // Act
        var result = authService.loginWithGoogle("id-token", metadata);
        // Assert
        assertEquals(user.getId(), result.user().id());
        verify(userServiceClient).admitGoogleLogin(new AdmitGoogleLoginRequest(changedEmail, user.getId()));
        verify(externalIdentityRepository, never()).findByIssuerAndUserEmail(anyString(), anyString());
    }

    @Test
    void login_ShouldRejectLegacyUserWithoutRoster_IncludingAdmin() {
        // Arrange: there is no user-by-email shortcut, even for an existing ADMIN.
        validGoogle(EMAIL);
        when(userServiceClient.admitGoogleLogin(new AdmitGoogleLoginRequest(EMAIL, null)))
                .thenThrow(new RosterNotFoundException("Not enrolled"));
        // Act / Assert
        assertThrows(RosterNotFoundException.class, () -> authService.loginWithGoogle("id-token", metadata));
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
        verify(externalIdentityRepository, never()).insertIfAbsent(any(), any(), any(), any(), any());
    }

    @Test
    void login_ShouldRejectBoundUser_WhenRosterIsDeactivated() {
        // Arrange
        validGoogle(EMAIL);
        when(externalIdentityRepository.findByIssuerAndSubject(ISSUER, SUBJECT)).thenReturn(Optional.of(link(user.getId())));
        when(userServiceClient.admitGoogleLogin(any())).thenThrow(new RosterDeactivatedException("Deactivated"));
        // Act / Assert
        assertThrows(RosterDeactivatedException.class, () -> authService.loginWithGoogle("id-token", metadata));
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldRejectDifferentSubjectWithSameEmail_WithoutChangingRoster() {
        // Arrange
        validGoogle(EMAIL);
        when(externalIdentityRepository.findByIssuerAndUserEmail(ISSUER, EMAIL)).thenReturn(Optional.of(mock(ExternalIdentity.class)));
        // Act
        var error = assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        // Assert
        assertEquals(HttpStatus.CONFLICT, error.getStatusCode());
        verifyNoInteractions(userServiceClient, jwtTokenProvider, refreshTokenService);
    }

    @ParameterizedTest
    @EnumSource(value = AccountStatus.class, names = {"DEACTIVATED", "REVOKED"})
    void login_ShouldRejectInactiveUser_EvenWithValidRoster(AccountStatus status) {
        // Arrange
        validGoogle(EMAIL);
        admit(null, EMAIL);
        user.setStatus(status);
        // Act
        var error = assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        // Assert
        assertEquals(HttpStatus.FORBIDDEN, error.getStatusCode());
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldRejectLockedUser_EvenWithValidRoster() {
        // Arrange
        validGoogle(EMAIL);
        admit(null, EMAIL);
        user.setLockedUntil(OffsetDateTime.now().plusMinutes(5));
        // Act / Assert
        assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldRejectConcurrentConflictingBinding_WithoutIssuingTokens() {
        // Arrange
        validGoogle(EMAIL);
        admit(null, EMAIL);
        when(externalIdentityRepository.findByIssuerAndSubject(ISSUER, SUBJECT))
                .thenReturn(Optional.empty(), Optional.of(link(UUID.randomUUID())));
        // Act
        var error = assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        // Assert
        assertEquals(HttpStatus.CONFLICT, error.getStatusCode());
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldRejectWhenUserAlreadyHasAnotherSubject_AfterConcurrentEnrollment() {
        // Arrange
        validGoogle(EMAIL);
        admit(null, EMAIL);
        // Act
        var error = assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        // Assert
        assertEquals(HttpStatus.CONFLICT, error.getStatusCode());
        verifyNoInteractions(jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldFailClosed_WhenProviderTokenIsInvalid() {
        // Arrange
        when(googleTokenVerifierService.verify("id-token")).thenThrow(new ResponseStatusException(HttpStatus.UNAUTHORIZED));
        // Act / Assert
        assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        verifyNoInteractions(userServiceClient, jwtTokenProvider, refreshTokenService, externalIdentityRepository);
    }

    @Test
    void login_ShouldRequireEmailAuthority_ForFirstEnrollmentOnly() {
        // Arrange
        when(googleTokenVerifierService.verify("id-token"))
                .thenReturn(new GoogleTokenPayload(EMAIL, SUBJECT, "Employee", null, true, false));
        // Act
        var error = assertThrows(ResponseStatusException.class, () -> authService.loginWithGoogle("id-token", metadata));
        // Assert
        assertEquals(HttpStatus.FORBIDDEN, error.getStatusCode());
        verifyNoInteractions(userServiceClient, jwtTokenProvider, refreshTokenService);
    }

    @Test
    void login_ShouldAdoptSameSubjectBinding_WhenParallelLoginCommitsBetweenReads() {
        // Arrange
        validGoogle(EMAIL);
        ExternalIdentity committed = link(user.getId());
        when(externalIdentityRepository.findByIssuerAndSubject(ISSUER, SUBJECT))
                .thenReturn(Optional.empty(), Optional.of(committed));
        when(externalIdentityRepository.findByIssuerAndUserEmail(ISSUER, EMAIL)).thenReturn(Optional.of(committed));
        admit(user.getId(), EMAIL);
        issueTokens();
        // Act
        var result = authService.loginWithGoogle("id-token", metadata);
        // Assert
        assertEquals(user.getId(), result.user().id());
        verify(userServiceClient).admitGoogleLogin(new AdmitGoogleLoginRequest(EMAIL, user.getId()));
    }
}
