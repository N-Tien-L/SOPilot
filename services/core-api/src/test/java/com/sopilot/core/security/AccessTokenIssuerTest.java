package com.sopilot.core.security;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.crypto.RSASSAVerifier;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Personal-workspace access token shape (TECH §5.1, V2-11 acceptance). */
class AccessTokenIssuerTest {

    private static final Instant NOW = Instant.parse("2026-11-04T08:00:00Z");
    private static RSAKey key;

    @BeforeAll
    static void key() throws Exception {
        key = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
    }

    @Test
    void issuesWorkspaceBoundTokenWithWdeptSlot() throws Exception {
        var issuer = new AccessTokenIssuer(key, Duration.ofMinutes(15), Clock.fixed(NOW, ZoneOffset.UTC));
        UUID user = UUID.randomUUID();
        UUID workspace = UUID.randomUUID();

        AccessTokenIssuer.IssuedToken token = issuer.issue(user, workspace, "OWNER", null);

        SignedJWT jwt = SignedJWT.parse(token.value());
        assertThat(jwt.verify(new RSASSAVerifier(key.toRSAPublicKey()))).isTrue();
        assertThat(jwt.getHeader().getAlgorithm()).isEqualTo(JWSAlgorithm.RS256);
        assertThat(jwt.getHeader().getKeyID()).isEqualTo(key.getKeyID());

        var claims = jwt.getJWTClaimsSet();
        assertThat(claims.getIssuer()).isEqualTo("sopilot-core");
        assertThat(claims.getAudience()).containsExactly("sopilot-core", "sopilot-ai");
        assertThat(claims.getSubject()).isEqualTo(user.toString());
        assertThat(claims.getStringClaim("wid")).isEqualTo(workspace.toString());
        assertThat(claims.getStringClaim("wrole")).isEqualTo("OWNER");
        assertThat(claims.getClaims()).containsKey("wdept");
        assertThat(claims.getClaim("wdept")).isNull();
        assertThat(claims.getJWTID()).isNotBlank();
        assertThat(claims.getExpirationTime().toInstant()).isEqualTo(NOW.plus(Duration.ofMinutes(15)));
        assertThat(claims.getIssueTime().toInstant()).isEqualTo(NOW);
        assertThat(claims.getClaims()).doesNotContainKeys("email", "name");
        assertThat(token.expiresInSeconds()).isEqualTo(900);
        assertThat(token.toString()).doesNotContain(token.value());
    }

    @Test
    void carriesDepartmentWhenPresent() throws Exception {
        var issuer = new AccessTokenIssuer(key, Duration.ofMinutes(5), Clock.fixed(NOW, ZoneOffset.UTC));
        UUID dept = UUID.randomUUID();

        var claims = SignedJWT.parse(issuer.issue(UUID.randomUUID(), UUID.randomUUID(), "MEMBER", dept).value())
                .getJWTClaimsSet();

        assertThat(claims.getStringClaim("wdept")).isEqualTo(dept.toString());
    }

    @Test
    void refusesTtlAboveFifteenMinutes() {
        assertThatThrownBy(() -> new AccessTokenIssuer(key, Duration.ofMinutes(16), Clock.systemUTC()))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> new AccessTokenIssuer(key, Duration.ZERO, Clock.systemUTC()))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void jwksPublishesOnlyPublicKey() {
        var provider = new SigningKeyProvider(key);

        var json = provider.publicJwkSet().toJSONObject(true).toString();

        assertThat(provider.publicJwkSet().getKeys()).hasSize(1);
        assertThat(provider.publicJwkSet().getKeys().get(0).isPrivate()).isFalse();
        assertThat(json).doesNotContain("\"d\"");
    }
}
