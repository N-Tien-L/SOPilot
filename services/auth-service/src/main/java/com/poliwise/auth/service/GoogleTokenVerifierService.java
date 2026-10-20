package com.poliwise.auth.service;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.DefaultJWKSetCache;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.JWSKeySelector;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jose.util.DefaultResourceRetriever;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import com.poliwise.auth.dto.auth.GoogleTokenPayload;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.net.MalformedURLException;
import java.net.URI;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Service verifying Google ID tokens using Google's public JWKS.
 * Caches public keys in RAM with configurable TTL (default: 60 minutes).
 * Validates signature (RS256), audience, issuer, expiration, and email_verified.
 */
@Service
public class GoogleTokenVerifierService {

    public static final String CANONICAL_ISSUER = "https://accounts.google.com";

    private static final Logger log = LoggerFactory.getLogger(GoogleTokenVerifierService.class);
    private static final Set<String> VALID_ISSUERS = Set.of("https://accounts.google.com", "accounts.google.com");

    private final String clientId;
    private final ConfigurableJWTProcessor<SecurityContext> jwtProcessor;

    @Autowired
    public GoogleTokenVerifierService(
            @Value("${auth.oauth.google.client-id}") String clientId,
            @Value("${auth.oauth.google.jwks-uri:https://www.googleapis.com/oauth2/v3/certs}") String jwksUri,
            @Value("${auth.oauth.google.jwks-cache-ttl-minutes:60}") long cacheTtlMinutes
    ) {
        this.clientId = clientId;
        this.jwtProcessor = createDefaultJwtProcessor(jwksUri, cacheTtlMinutes);
    }

    // Constructor for testing with mock processor
    public GoogleTokenVerifierService(String clientId, ConfigurableJWTProcessor<SecurityContext> jwtProcessor) {
        this.clientId = clientId;
        this.jwtProcessor = jwtProcessor;
    }

    private static ConfigurableJWTProcessor<SecurityContext> createDefaultJwtProcessor(String jwksUri, long cacheTtlMinutes) {
        try {
            ConfigurableJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
            JWKSource<SecurityContext> keySource = new RemoteJWKSet<>(
                    URI.create(jwksUri).toURL(),
                    new DefaultResourceRetriever(5000, 5000),
                    new DefaultJWKSetCache(cacheTtlMinutes, cacheTtlMinutes, TimeUnit.MINUTES)
            );
            JWSKeySelector<SecurityContext> keySelector =
                    new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, keySource);
            processor.setJWSKeySelector(keySelector);
            return processor;
        } catch (MalformedURLException e) {
            throw new IllegalArgumentException("Invalid Google JWKS URI: " + jwksUri, e);
        }
    }

    /**
     * Verifies the given Google ID token and returns extracted payload.
     *
     * @param idToken raw Google ID Token JWT
     * @return GoogleTokenPayload with email, sub, name, etc.
     * @throws ResponseStatusException with 401 Unauthorized or 400 Bad Request on failure
     */
    public GoogleTokenPayload verify(String idToken) {
        if (idToken == null || idToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Google ID token cannot be empty");
        }

        try {
            JWTClaimsSet claims = jwtProcessor.process(idToken, null);

            // 1. Verify Issuer
            String issuer = claims.getIssuer();
            if (issuer == null || !VALID_ISSUERS.contains(issuer)) {
                log.warn("Invalid Google token issuer: {}", issuer);
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid Google token issuer");
            }

            // 2. Verify Audience
            List<String> audience = claims.getAudience();
            if (audience == null || !audience.contains(clientId)) {
                log.warn("Invalid Google token audience: expected {}, got {}", clientId, audience);
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid Google token audience");
            }

            // 3. Verify Expiration
            Date exp = claims.getExpirationTime();
            Date now = new Date();
            if (exp == null || exp.before(now)) {
                log.warn("Google token is expired: exp={}", exp);
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Google token has expired");
            }

            // 4. Verify email_verified
            Boolean emailVerified = claims.getBooleanClaim("email_verified");
            if (!Boolean.TRUE.equals(emailVerified)) {
                log.warn("Google token email is not verified");
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Google email must be verified");
            }

            // 5. Extract email & details
            String email = claims.getStringClaim("email");
            if (email == null || email.isBlank()) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Google token does not contain an email");
            }

            String sub = claims.getSubject();
            if (sub == null || sub.isBlank() || sub.length() > 255) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Google token has no valid subject");
            }
            // Enrollment by email needs current email authority; a returning subject does not.
            String hostedDomain = claims.getStringClaim("hd");
            boolean emailAuthoritative = email.trim().toLowerCase(java.util.Locale.ROOT).endsWith("@gmail.com")
                    || (hostedDomain != null && !hostedDomain.isBlank());
            String name = claims.getStringClaim("name");
            String picture = claims.getStringClaim("picture");

            return new GoogleTokenPayload(
                    email.trim().toLowerCase(java.util.Locale.ROOT),
                    sub,
                    name != null ? name.trim() : email.split("@")[0],
                    picture,
                    true,
                    emailAuthoritative
            );

        } catch (ResponseStatusException rse) {
            throw rse;
        } catch (Exception e) {
            log.error("Google token verification failed: {}", e.getMessage());
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Failed to verify Google ID token: " + e.getMessage());
        }
    }
}
