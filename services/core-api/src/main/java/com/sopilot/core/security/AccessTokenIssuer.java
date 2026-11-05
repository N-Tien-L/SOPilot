package com.sopilot.core.security;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSObject;
import com.nimbusds.jose.Payload;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.config.SopilotProperties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Issues RS256 access tokens bound to one workspace (TECH-V2-core-api §5.1):
 * {@code iss, aud, sub, wid, wrole, wdept, jti, iat, exp}. No email or name in the token.
 * {@code wdept} is always present (null until V2-23 assigns departments).
 */
@Component
public class AccessTokenIssuer {

    public static final String ISSUER = "sopilot-core";
    public static final List<String> AUDIENCE = List.of("sopilot-core", "sopilot-ai");

    private final RSAKey signingKey;
    private final RSASSASigner signer;
    private final Duration ttl;
    private final Clock clock;

    @Autowired
    public AccessTokenIssuer(SigningKeyProvider keys, SopilotProperties properties) {
        this(keys.signingKey(), properties.jwt().accessTtl(), Clock.systemUTC());
    }

    AccessTokenIssuer(RSAKey signingKey, Duration ttl, Clock clock) {
        if (ttl.isZero() || ttl.isNegative() || ttl.compareTo(SopilotProperties.MAX_ACCESS_TTL) > 0) {
            throw new IllegalStateException("SOPILOT_ACCESS_TTL must be positive and at most PT15M");
        }
        try {
            this.signer = new RSASSASigner(signingKey);
        } catch (JOSEException e) {
            throw new IllegalStateException("Invalid access-token signing key");
        }
        this.signingKey = signingKey;
        this.ttl = ttl;
        this.clock = clock;
    }

    public IssuedToken issue(UUID userId, UUID workspaceId, String workspaceRole, UUID departmentId) {
        Instant now = clock.instant();
        Instant exp = now.plus(ttl);
        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("iss", ISSUER);
        claims.put("aud", AUDIENCE);
        claims.put("sub", userId.toString());
        claims.put("wid", workspaceId.toString());
        claims.put("wrole", workspaceRole);
        claims.put("wdept", departmentId == null ? null : departmentId.toString());
        claims.put("jti", UuidV7.generate().toString());
        claims.put("iat", now.getEpochSecond());
        claims.put("exp", exp.getEpochSecond());

        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.RS256)
                .keyID(signingKey.getKeyID()).type(JOSEObjectType.JWT).build();
        JWSObject jws = new JWSObject(header, new Payload(claims));
        try {
            jws.sign(signer);
        } catch (JOSEException e) {
            throw new IllegalStateException("Access token signing failed");
        }
        return new IssuedToken(jws.serialize(), ttl.toSeconds());
    }

    public record IssuedToken(String value, long expiresInSeconds) {
        @Override
        public String toString() {
            return "IssuedToken[value=<redacted>, expiresInSeconds=" + expiresInSeconds + "]";
        }
    }
}
