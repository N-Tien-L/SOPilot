package com.sopilot.core.identity;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.JWKSourceBuilder;
import com.nimbusds.jose.proc.BadJOSEException;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jose.util.DefaultResourceRetriever;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import com.sopilot.core.config.SopilotProperties;
import com.sopilot.core.identity.GoogleTokenRejectedException.Reason;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.net.MalformedURLException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.ParseException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Verifies Google ID tokens. Ported from V1 {@code auth-service} {@code GoogleTokenVerifierService}
 * (read-only source), with these changes for V2 (TECH-V2-core-api §5.1, A8, A9):
 * <ul>
 *   <li>checks {@code nonce} against the value bound to the {@code sp_nonce} cookie;</li>
 *   <li>allows at most 60 s clock skew on {@code exp}/{@code iat}/{@code nbf};</li>
 *   <li>never returns exception messages to the client and never logs the token or email;</li>
 *   <li>returns the canonical issuer so {@code (issuer, subject)} is stable for both issuer spellings.</li>
 * </ul>
 */
@Component
public class GoogleIdTokenVerifier {

    public static final String CANONICAL_ISSUER = "https://accounts.google.com";
    static final Duration MAX_CLOCK_SKEW = Duration.ofSeconds(60);

    private static final Logger log = LoggerFactory.getLogger(GoogleIdTokenVerifier.class);
    private static final Set<String> VALID_ISSUERS = Set.of("https://accounts.google.com", "accounts.google.com");
    private static final int MAX_TOKEN_LENGTH = 8192;

    private final String clientId;
    private final ConfigurableJWTProcessor<SecurityContext> processor;
    private final Clock clock;

    @Autowired
    public GoogleIdTokenVerifier(SopilotProperties properties) {
        this(properties.google().clientId(),
                remoteProcessor(properties.google().jwksUri(), properties.google().jwksCacheTtl()),
                Clock.systemUTC());
        if (clientId == null || clientId.isBlank()) {
            log.warn("GOOGLE_CLIENT_ID is not set; every Google login will be rejected");
        }
    }

    /** For tests: a processor backed by a local key set and a fixed clock. */
    GoogleIdTokenVerifier(String clientId, ConfigurableJWTProcessor<SecurityContext> processor, Clock clock) {
        this.clientId = clientId;
        this.processor = processor;
        this.clock = clock;
    }

    static ConfigurableJWTProcessor<SecurityContext> processorFor(JWKSource<SecurityContext> keys) {
        DefaultJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
        // RS256 only: rejects alg=none, HS256 key confusion and any other algorithm.
        processor.setJWSKeySelector(new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, keys));
        // Claims are checked explicitly in verify() so each failure has a distinct reason.
        processor.setJWTClaimsSetVerifier((claims, context) -> { });
        return processor;
    }

    private static ConfigurableJWTProcessor<SecurityContext> remoteProcessor(String jwksUri, Duration cacheTtl) {
        try {
            JWKSource<SecurityContext> keys = JWKSourceBuilder
                    .<SecurityContext>create(URI.create(jwksUri).toURL(), new DefaultResourceRetriever(5000, 5000))
                    .cache(cacheTtl.toMillis(), 15_000)
                    .rateLimited(false)
                    .build();
            return processorFor(keys);
        } catch (MalformedURLException e) {
            throw new IllegalStateException("GOOGLE_JWKS_URI is not a valid URL");
        }
    }

    /**
     * @param idToken       raw Google ID token
     * @param expectedNonce nonce bound to the caller's {@code sp_nonce} cookie, or null if absent/invalid
     * @return verified identity with the canonical Google issuer
     * @throws GoogleTokenRejectedException on any failure
     */
    public ExternalIdentityClaims verify(String idToken, String expectedNonce) {
        if (clientId == null || clientId.isBlank()) {
            throw reject(Reason.NOT_CONFIGURED);
        }
        if (idToken == null || idToken.isBlank() || idToken.length() > MAX_TOKEN_LENGTH) {
            throw reject(Reason.MALFORMED);
        }

        JWTClaimsSet claims;
        try {
            claims = processor.process(idToken, null);
        } catch (ParseException e) {
            throw reject(Reason.MALFORMED);
        } catch (BadJOSEException e) {
            throw reject(Reason.BAD_SIGNATURE);
        } catch (Exception e) {
            // JOSEException or JWKS retrieval failure; the type is enough to diagnose.
            log.warn("Google token verification error: {}", e.getClass().getSimpleName());
            throw reject(Reason.BAD_SIGNATURE);
        }

        try {
            return checkClaims(claims, expectedNonce);
        } catch (ParseException e) {
            throw reject(Reason.MALFORMED);
        }
    }

    private ExternalIdentityClaims checkClaims(JWTClaimsSet claims, String expectedNonce) throws ParseException {
        if (claims.getIssuer() == null || !VALID_ISSUERS.contains(claims.getIssuer())) {
            throw reject(Reason.BAD_ISSUER);
        }
        List<String> audience = claims.getAudience();
        if (audience == null || !audience.contains(clientId)) {
            throw reject(Reason.BAD_AUDIENCE);
        }

        Instant now = clock.instant();
        Date exp = claims.getExpirationTime();
        if (exp == null || exp.toInstant().plus(MAX_CLOCK_SKEW).isBefore(now)) {
            throw reject(Reason.EXPIRED);
        }
        Date iat = claims.getIssueTime();
        Date nbf = claims.getNotBeforeTime();
        if ((iat != null && iat.toInstant().minus(MAX_CLOCK_SKEW).isAfter(now))
                || (nbf != null && nbf.toInstant().minus(MAX_CLOCK_SKEW).isAfter(now))) {
            throw reject(Reason.NOT_YET_VALID);
        }

        if (!Boolean.TRUE.equals(claims.getBooleanClaim("email_verified"))) {
            throw reject(Reason.EMAIL_NOT_VERIFIED);
        }

        String nonce = claims.getStringClaim("nonce");
        if (expectedNonce == null || expectedNonce.isBlank()) {
            throw reject(Reason.NONCE_MISSING);
        }
        if (nonce == null || !MessageDigest.isEqual(
                nonce.getBytes(StandardCharsets.UTF_8), expectedNonce.getBytes(StandardCharsets.UTF_8))) {
            throw reject(Reason.NONCE_MISMATCH);
        }

        String email = claims.getStringClaim("email");
        if (email == null || email.isBlank()) {
            throw reject(Reason.MISSING_EMAIL);
        }
        String subject = claims.getSubject();
        if (subject == null || subject.isBlank() || subject.length() > 255) {
            throw reject(Reason.MISSING_SUBJECT);
        }

        String normalizedEmail = email.trim().toLowerCase(Locale.ROOT);
        String name = claims.getStringClaim("name");
        String hostedDomain = claims.getStringClaim("hd");
        return new ExternalIdentityClaims(
                CANONICAL_ISSUER,
                subject,
                normalizedEmail,
                name != null && !name.isBlank() ? name.trim() : normalizedEmail.split("@")[0],
                claims.getStringClaim("picture"),
                hostedDomain != null && !hostedDomain.isBlank() ? hostedDomain.trim().toLowerCase(Locale.ROOT) : null);
    }

    private static GoogleTokenRejectedException reject(Reason reason) {
        log.info("Google ID token rejected: {}", reason);
        return new GoogleTokenRejectedException(reason);
    }
}
