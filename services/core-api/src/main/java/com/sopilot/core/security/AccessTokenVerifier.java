package com.sopilot.core.security;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Verifies the RS256 access token this service issued: signature, algorithm, issuer, audience,
 * expiry and claim shape. Any failure yields empty; the reason is deliberately not exposed.
 */
@Component
public class AccessTokenVerifier {

    private static final long SKEW_SECONDS = 5;

    /** Verifier per {@code kid}: the current key and, during a rotation, the previous one. */
    private final Map<String, RSASSAVerifier> verifiers;
    private final Clock clock;

    @Autowired
    public AccessTokenVerifier(SigningKeyProvider keys) {
        this(keys, Clock.systemUTC());
    }

    AccessTokenVerifier(SigningKeyProvider keys, Clock clock) {
        try {
            Map<String, RSASSAVerifier> byKid = new HashMap<>();
            for (RSAKey key : keys.verificationKeys()) {
                byKid.put(key.getKeyID(), new RSASSAVerifier(key.toRSAPublicKey()));
            }
            this.verifiers = Map.copyOf(byKid);
        } catch (Exception e) {
            throw new IllegalStateException("Invalid access-token verification key");
        }
        this.clock = clock;
    }

    public Optional<AuthPrincipal> verify(String token) {
        try {
            SignedJWT jwt = SignedJWT.parse(token);
            RSASSAVerifier verifier = verifiers.get(jwt.getHeader().getKeyID());
            if (verifier == null || !JWSAlgorithm.RS256.equals(jwt.getHeader().getAlgorithm()) || !jwt.verify(verifier)) {
                return Optional.empty();
            }
            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            Date exp = claims.getExpirationTime();
            if (!AccessTokenIssuer.ISSUER.equals(claims.getIssuer()) || exp == null
                    || exp.toInstant().plusSeconds(SKEW_SECONDS).isBefore(clock.instant())
                    || claims.getAudience() == null || !claims.getAudience().contains("sopilot-core")) {
                return Optional.empty();
            }
            String dept = claims.getStringClaim("wdept");
            return Optional.of(new AuthPrincipal(
                    UUID.fromString(claims.getSubject()),
                    UUID.fromString(claims.getStringClaim("wid")),
                    WorkspaceRole.valueOf(claims.getStringClaim("wrole")),
                    dept == null ? null : UUID.fromString(dept)));
        } catch (Exception e) {
            return Optional.empty();
        }
    }
}
