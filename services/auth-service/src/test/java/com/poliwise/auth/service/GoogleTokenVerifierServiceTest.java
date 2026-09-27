package com.poliwise.auth.service;

import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.poliwise.auth.dto.auth.GoogleTokenPayload;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.Date;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GoogleTokenVerifierServiceTest {

    private static final String CLIENT_ID = "test-sopilot-google-client-id";

    @Mock
    private ConfigurableJWTProcessor<SecurityContext> jwtProcessor;

    private GoogleTokenVerifierService verifierService;

    @BeforeEach
    void setUp() {
        verifierService = new GoogleTokenVerifierService(CLIENT_ID, jwtProcessor);
    }

    @Test
    @DisplayName("Should successfully verify token and return payload when all claims are valid")
    void verify_ValidToken_ReturnsPayload() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("https://accounts.google.com")
                .audience(List.of(CLIENT_ID))
                .expirationTime(new Date(System.currentTimeMillis() + 3600_000))
                .claim("email_verified", true)
                .claim("email", "EMPLOYEE@SOPILOT.COM")
                .subject("google-sub-999")
                .claim("name", "Nguyen Van A")
                .claim("picture", "https://photo.url")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        GoogleTokenPayload payload = verifierService.verify("valid-id-token");

        assertNotNull(payload);
        assertEquals("employee@sopilot.com", payload.email());
        assertEquals("google-sub-999", payload.sub());
        assertEquals("Nguyen Van A", payload.name());
        assertEquals("https://photo.url", payload.picture());
        assertTrue(payload.emailVerified());
    }

    @Test
    @DisplayName("Should accept accounts.google.com without https prefix as valid issuer")
    void verify_AlternativeValidIssuer_Success() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("accounts.google.com")
                .audience(List.of(CLIENT_ID))
                .expirationTime(new Date(System.currentTimeMillis() + 3600_000))
                .claim("email_verified", true)
                .claim("email", "user@sopilot.com")
                .subject("google-sub-123")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        GoogleTokenPayload payload = verifierService.verify("valid-token");
        assertNotNull(payload);
        assertEquals("user@sopilot.com", payload.email());
    }

    @Test
    @DisplayName("Should reject token with invalid issuer")
    void verify_InvalidIssuer_ThrowsUnauthorized() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("https://fake-google.com")
                .audience(List.of(CLIENT_ID))
                .expirationTime(new Date(System.currentTimeMillis() + 3600_000))
                .claim("email_verified", true)
                .claim("email", "attacker@sopilot.com")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify("fake-token"));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        assertTrue(ex.getReason().contains("Invalid Google token issuer"));
    }

    @Test
    @DisplayName("Should reject token when audience does not match configured client-id")
    void verify_AudienceMismatch_ThrowsUnauthorized() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("https://accounts.google.com")
                .audience(List.of("different-google-client-id"))
                .expirationTime(new Date(System.currentTimeMillis() + 3600_000))
                .claim("email_verified", true)
                .claim("email", "user@sopilot.com")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify("mismatched-aud-token"));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        assertTrue(ex.getReason().contains("Invalid Google token audience"));
    }

    @Test
    @DisplayName("Should reject token when expiration is in the past")
    void verify_ExpiredToken_ThrowsUnauthorized() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("https://accounts.google.com")
                .audience(List.of(CLIENT_ID))
                .expirationTime(new Date(System.currentTimeMillis() - 10_000)) // 10 seconds ago
                .claim("email_verified", true)
                .claim("email", "user@sopilot.com")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify("expired-token"));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        assertTrue(ex.getReason().contains("expired"));
    }

    @Test
    @DisplayName("Should reject token when email_verified is false")
    void verify_UnverifiedEmail_ThrowsUnauthorized() throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("https://accounts.google.com")
                .audience(List.of(CLIENT_ID))
                .expirationTime(new Date(System.currentTimeMillis() + 3600_000))
                .claim("email_verified", false)
                .claim("email", "unverified@sopilot.com")
                .build();

        when(jwtProcessor.process(any(String.class), isNull())).thenReturn(claims);

        ResponseStatusException ex = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify("unverified-email-token"));

        assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
        assertTrue(ex.getReason().contains("Google email must be verified"));
    }

    @Test
    @DisplayName("Should reject empty or blank token with 400 Bad Request")
    void verify_BlankToken_ThrowsBadRequest() {
        ResponseStatusException ex1 = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify(""));
        assertEquals(HttpStatus.BAD_REQUEST, ex1.getStatusCode());

        ResponseStatusException ex2 = assertThrows(ResponseStatusException.class, () ->
                verifierService.verify(null));
        assertEquals(HttpStatus.BAD_REQUEST, ex2.getStatusCode());
    }
}
