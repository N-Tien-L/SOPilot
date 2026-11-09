package com.sopilot.core.security;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** Rotating the signing key must not drop sessions signed by the previous key (TECH §5.1). */
class SigningKeyRotationTest {

    private static RSAKey oldKey;
    private static RSAKey newKey;

    @BeforeAll
    static void keys() throws Exception {
        oldKey = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
        newKey = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
    }

    @Test
    void jwksPublishesCurrentThenPreviousPublicKeyOnly() {
        var provider = new SigningKeyProvider(newKey, oldKey);

        var published = provider.publicJwkSet().getKeys();

        assertThat(published).extracting(k -> k.getKeyID()).containsExactly(newKey.getKeyID(), oldKey.getKeyID());
        assertThat(published).allMatch(k -> !k.isPrivate());
    }

    @Test
    void tokenSignedByPreviousKeyStillVerifiesAfterRotation() throws Exception {
        var verifier = new AccessTokenVerifier(new SigningKeyProvider(newKey, oldKey), java.time.Clock.systemUTC());

        assertThat(verifier.verify(sign(oldKey))).isPresent();
        assertThat(verifier.verify(sign(newKey))).isPresent();
    }

    @Test
    void tokenSignedByPreviousKeyIsRejectedWhenNoPreviousKeyIsConfigured() throws Exception {
        var verifier = new AccessTokenVerifier(new SigningKeyProvider(newKey), java.time.Clock.systemUTC());

        assertThat(verifier.verify(sign(oldKey))).isEmpty();
    }

    @Test
    void tokenSignedByAnUnrelatedKeyIsRejected() throws Exception {
        RSAKey stranger = new RSAKeyGenerator(2048).keyIDFromThumbprint(true).generate();
        var verifier = new AccessTokenVerifier(new SigningKeyProvider(newKey, oldKey), java.time.Clock.systemUTC());

        assertThat(verifier.verify(sign(stranger))).isEmpty();
    }

    @Test
    void tokenClaimingAKnownKidButSignedByAnotherKeyIsRejected() throws Exception {
        RSAKey stranger = new RSAKeyGenerator(2048).keyID(oldKey.getKeyID()).generate();
        var verifier = new AccessTokenVerifier(new SigningKeyProvider(newKey, oldKey), java.time.Clock.systemUTC());

        assertThat(verifier.verify(sign(stranger))).isEmpty();
    }

    private static String sign(RSAKey key) throws Exception {
        Instant now = Instant.now();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer(AccessTokenIssuer.ISSUER).audience(List.of("sopilot-core", "sopilot-ai"))
                .subject(UUID.randomUUID().toString())
                .claim("wid", UUID.randomUUID().toString()).claim("wrole", "MEMBER").claim("wdept", null)
                .issueTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(300))).build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID()).build(), claims);
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }
}
