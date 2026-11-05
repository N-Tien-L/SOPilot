package com.sopilot.core.identity;

import com.sopilot.core.identity.GoogleTokenRejectedException.Reason;
import com.sopilot.core.identity.dto.LoginResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** HTTP contract of the auth endpoints: error envelope (A8), nonce cookie, dev-login profile gate. */
class AuthControllerTest {

    private static final String CLEARED = "sp_nonce=; Path=/api/v1/auth; Max-Age=0";

    abstract static class Base {
        @Autowired
        MockMvc mvc;
        @MockitoBean
        NonceService nonces;
        @MockitoBean
        GoogleIdTokenVerifier verifier;
        @MockitoBean
        IdentityService identityService;
        @MockitoBean
        AuthCookies cookies;

        @BeforeEach
        void stubCookies() {
            when(cookies.clearNonceCookie()).thenReturn(CLEARED);
            when(cookies.nonceCookie(anyString(), any())).thenReturn("sp_nonce=signed; Path=/api/v1/auth; HttpOnly");
            when(nonces.ttl()).thenReturn(Duration.ofMinutes(5));
        }

        static LoginResponse login() {
            return new LoginResponse("header.payload.sig", 900,
                    new LoginResponse.UserView(UUID.randomUUID(), "an@acme.com", "An"),
                    new LoginResponse.WorkspaceView(UUID.randomUUID(), "An's workspace", "PERSONAL", "OWNER"),
                    List.of());
        }
    }

    @Nested
    @WebMvcTest(controllers = {AuthController.class, DevLoginController.class})
    @ActiveProfiles("prod")
    class OutsideLocalAndTest extends Base {

        @Test
        void devLoginIsNotRegistered() throws Exception {
            mvc.perform(post("/api/v1/auth/dev-login").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\":\"a@b.com\"}"))
                    .andExpect(status().isNotFound())
                    .andExpect(jsonPath("$.error.code").value("NOT_FOUND"));
        }

        @Test
        void nonceEndpointSetsCookieAndReturnsNonce() throws Exception {
            when(nonces.issue()).thenReturn(new NonceService.IssuedNonce("the-nonce", "the-nonce.1.sig"));

            mvc.perform(post("/api/v1/auth/google/nonce"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.nonce").value("the-nonce"))
                    .andExpect(jsonPath("$.traceId").isNotEmpty())
                    .andExpect(header().string("Set-Cookie", containsString("sp_nonce=")))
                    .andExpect(header().string("Cache-Control", containsString("no-store")));
        }

        @Test
        void googleLoginPassesCookieNonceToVerifier() throws Exception {
            var identity = new ExternalIdentityClaims("https://accounts.google.com", "sub", "an@acme.com", "An", null, null);
            when(nonces.validate("cookie-value")).thenReturn(Optional.of("the-nonce"));
            when(verifier.verify("id-token", "the-nonce")).thenReturn(identity);
            when(identityService.login(identity)).thenReturn(login());

            mvc.perform(post("/api/v1/auth/google").contentType(MediaType.APPLICATION_JSON)
                            .cookie(new jakarta.servlet.http.Cookie("sp_nonce", "cookie-value"))
                            .content("{\"idToken\":\"id-token\"}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.accessToken").value("header.payload.sig"))
                    .andExpect(jsonPath("$.data.expiresIn").value(900))
                    .andExpect(jsonPath("$.data.workspace.kind").value("PERSONAL"))
                    .andExpect(jsonPath("$.data.workspace.role").value("OWNER"))
                    .andExpect(jsonPath("$.data.pendingInvitations").isArray())
                    .andExpect(header().string("Set-Cookie", containsString(CLEARED)));
        }

        @Test
        void rejectedGoogleTokenReturnsGenericErrorAndClearsNonce() throws Exception {
            when(nonces.validate(any())).thenReturn(Optional.empty());
            when(verifier.verify(eq("bad-token"), isNull()))
                    .thenThrow(new GoogleTokenRejectedException(Reason.NONCE_MISSING));

            mvc.perform(post("/api/v1/auth/google").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"idToken\":\"bad-token\"}"))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.error.code").value("INVALID_GOOGLE_TOKEN"))
                    .andExpect(content().string(not(containsString("NONCE"))))
                    .andExpect(header().string("Set-Cookie", containsString(CLEARED)));
        }

        @Test
        void unexpectedErrorDoesNotLeakInternalMessage() throws Exception {
            var identity = new ExternalIdentityClaims("https://accounts.google.com", "sub", "an@acme.com", "An", null, null);
            when(nonces.validate(any())).thenReturn(Optional.of("n"));
            when(verifier.verify(anyString(), anyString())).thenReturn(identity);
            when(identityService.login(any()))
                    .thenThrow(new IllegalStateException("password=hunter2 at jdbc:postgresql://db"));

            mvc.perform(post("/api/v1/auth/google").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"idToken\":\"t\"}"))
                    .andExpect(status().isInternalServerError())
                    .andExpect(jsonPath("$.error.code").value("INTERNAL_ERROR"))
                    .andExpect(header().string("Set-Cookie", containsString(CLEARED)))
                    .andExpect(content().string(not(containsString("hunter2"))))
                    .andExpect(content().string(not(containsString("jdbc"))));
        }

        @Test
        void blankIdTokenIsValidationError() throws Exception {
            mvc.perform(post("/api/v1/auth/google").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"idToken\":\"  \"}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"))
                    .andExpect(jsonPath("$.error.details.fields.idToken").value("invalid"));
        }

        @Test
        void malformedBodyIsValidationError() throws Exception {
            mvc.perform(post("/api/v1/auth/google").contentType(MediaType.APPLICATION_JSON).content("{oops"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"));
        }
    }

    @Nested
    @WebMvcTest(controllers = {AuthController.class, DevLoginController.class})
    @ActiveProfiles("test")
    class InTestProfile extends Base {

        @Test
        void devLoginUsesDevIssuerAndNormalizedEmail() throws Exception {
            when(identityService.login(any())).thenReturn(login());

            mvc.perform(post("/api/v1/auth/dev-login").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\":\"Binh@Acme.com\",\"displayName\":\"Binh\"}"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.accessToken").isNotEmpty());

            verify(identityService).login(argThat(c -> c.issuer().equals("sopilot-dev")
                    && c.subject().equals("binh@acme.com") && c.email().equals("binh@acme.com")));
        }

        @Test
        void devLoginValidatesEmail() throws Exception {
            mvc.perform(post("/api/v1/auth/dev-login").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\":\"not-an-email\"}"))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.error.code").value("VALIDATION_FAILED"));
        }
    }
}
