package com.sopilot.core.security;

import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** Every way a bearer token can be wrong must yield no principal (TECH §5.0, §5.1). */
class AccessTokenVerifierTest {

    private static final Instant NOW = Instant.parse("2026-11-05T08:00:00Z");
    private static RSAKey key;
    private static RSAKey otherKey;

    @BeforeAll
    static void keys() throws Exception {
        key = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
        otherKey = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
    }

    private final AccessTokenVerifier verifier =
            new AccessTokenVerifier(new SigningKeyProvider(key), Clock.fixed(NOW, ZoneOffset.UTC));

    private String issue(Duration ttl) {
        return new AccessTokenIssuer(key, ttl, Clock.fixed(NOW, ZoneOffset.UTC))
                .issue(UUID.randomUUID(), UUID.randomUUID(), "ADMIN", UUID.randomUUID()).value();
    }

    private String sign(RSAKey signingKey, JWTClaimsSet claims) throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(signingKey.getKeyID())
                .type(JOSEObjectType.JWT).build(), claims);
        jwt.sign(new RSASSASigner(signingKey));
        return jwt.serialize();
    }

    private JWTClaimsSet.Builder validClaims() {
        return new JWTClaimsSet.Builder().issuer("sopilot-core").audience(List.of("sopilot-core", "sopilot-ai"))
                .subject(UUID.randomUUID().toString()).claim("wid", UUID.randomUUID().toString())
                .claim("wrole", "MEMBER").claim("wdept", null).expirationTime(Date.from(NOW.plusSeconds(600)));
    }

    @Test
    void acceptsATokenFromTheIssuerAndReadsTheClaims() {
        AuthPrincipal p = verifier.verify(issue(Duration.ofMinutes(15))).orElseThrow();

        assertThat(p.role()).isEqualTo(WorkspaceRole.ADMIN);
        assertThat(p.departmentId()).isNotNull();
        assertThat(p.isManager()).isTrue();
    }

    @Test
    void acceptsAnAbsentDepartment() throws Exception {
        AuthPrincipal p = verifier.verify(sign(key, validClaims().build())).orElseThrow();

        assertThat(p.departmentId()).isNull();
        assertThat(p.isManager()).isFalse();
    }

    @Test
    void rejectsGarbageAndTamperedTokens() {
        String token = issue(Duration.ofMinutes(15));

        assertThat(verifier.verify("")).isEmpty();
        assertThat(verifier.verify("not-a-jwt")).isEmpty();
        assertThat(verifier.verify(token + "x")).isEmpty();
        String[] parts = token.split("\\.");
        assertThat(verifier.verify(parts[0] + "." + parts[1] + "AAAA." + parts[2])).isEmpty();
    }

    @Test
    void rejectsATokenSignedByAnotherKey() throws Exception {
        assertThat(verifier.verify(sign(otherKey, validClaims().build()))).isEmpty();
    }

    @Test
    void rejectsExpiredTokensBeyondTheSkew() throws Exception {
        assertThat(verifier.verify(sign(key, validClaims()
                .expirationTime(Date.from(NOW.minusSeconds(60))).build()))).isEmpty();
        assertThat(verifier.verify(sign(key, validClaims()
                .expirationTime(Date.from(NOW.minusSeconds(2))).build()))).isPresent();
    }

    @Test
    void rejectsWrongIssuerAudienceOrMissingClaims() throws Exception {
        assertThat(verifier.verify(sign(key, validClaims().issuer("someone-else").build()))).isEmpty();
        assertThat(verifier.verify(sign(key, validClaims().audience("sopilot-ai").build()))).isEmpty();
        assertThat(verifier.verify(sign(key, validClaims().claim("wrole", "ROOT").build()))).isEmpty();
        assertThat(verifier.verify(sign(key, validClaims().claim("wid", "not-a-uuid").build()))).isEmpty();
        assertThat(verifier.verify(sign(key, new JWTClaimsSet.Builder().issuer("sopilot-core")
                .audience("sopilot-core").subject(UUID.randomUUID().toString())
                .expirationTime(Date.from(NOW.plusSeconds(60))).build()))).isEmpty();
    }

    @Test
    void rejectsAnUnsignedToken() {
        String header = java.util.Base64.getUrlEncoder().withoutPadding()
                .encodeToString("{\"alg\":\"none\"}".getBytes());
        String body = java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(
                ("{\"iss\":\"sopilot-core\",\"aud\":[\"sopilot-core\"],\"sub\":\"" + UUID.randomUUID()
                        + "\",\"wid\":\"" + UUID.randomUUID() + "\",\"wrole\":\"OWNER\",\"exp\":"
                        + NOW.plusSeconds(600).getEpochSecond() + "}").getBytes());

        assertThat(verifier.verify(header + "." + body + ".")).isEmpty();
    }
}
