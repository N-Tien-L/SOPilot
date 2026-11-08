package com.sopilot.core.identity;

import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.PlainJWT;
import com.nimbusds.jwt.SignedJWT;
import com.sopilot.core.identity.GoogleTokenRejectedException.Reason;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.function.Consumer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** One test per rejected claim (TECH §10), signed with real RSA keys against a local JWKS. */
class GoogleIdTokenVerifierTest {

    private static final String CLIENT_ID = "test-client.apps.googleusercontent.com";
    private static final String NONCE = "n-0123456789abcdef";
    private static final Instant NOW = Instant.parse("2026-11-04T08:00:00Z");

    private static RSAKey googleKey;
    private static RSAKey attackerKey;

    private GoogleIdTokenVerifier verifier;

    @BeforeAll
    static void keys() throws Exception {
        googleKey = new RSAKeyGenerator(2048).keyID("google-kid").generate();
        attackerKey = new RSAKeyGenerator(2048).keyID("google-kid").generate();
    }

    @BeforeEach
    void setUp() {
        var jwks = new ImmutableJWKSet<com.nimbusds.jose.proc.SecurityContext>(new JWKSet(googleKey.toPublicJWK()));
        verifier = new GoogleIdTokenVerifier(CLIENT_ID, GoogleIdTokenVerifier.processorFor(jwks),
                Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void acceptsValidTokenAndNormalizesIdentity() throws Exception {
        String token = sign(googleKey, claims(b -> b.claim("email", " An@Acme.COM ").claim("hd", "Acme.com")));

        ExternalIdentityClaims identity = verifier.verify(token, NONCE);

        assertThat(identity.issuer()).isEqualTo(GoogleIdTokenVerifier.CANONICAL_ISSUER);
        assertThat(identity.subject()).isEqualTo("google-sub-1");
        assertThat(identity.email()).isEqualTo("an@acme.com");
        assertThat(identity.displayName()).isEqualTo("An");
        assertThat(identity.hostedDomain()).isEqualTo("acme.com");
    }

    @Test
    void mapsBothIssuerSpellingsToCanonicalIssuer() throws Exception {
        String token = sign(googleKey, claims(b -> b.issuer("accounts.google.com")));

        assertThat(verifier.verify(token, NONCE).issuer()).isEqualTo(GoogleIdTokenVerifier.CANONICAL_ISSUER);
    }

    @Test
    void rejectsWrongSignature() throws Exception {
        String token = sign(attackerKey, claims(b -> { }));

        assertRejected(token, NONCE, Reason.BAD_SIGNATURE);
    }

    @Test
    void rejectsHmacSignedToken() throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims(b -> { }));
        jwt.sign(new MACSigner(new byte[32]));

        assertRejected(jwt.serialize(), NONCE, Reason.BAD_SIGNATURE);
    }

    @Test
    void rejectsUnsignedToken() {
        // alg=none is refused by the RS256-only key selector.
        assertRejected(new PlainJWT(claims(b -> { })).serialize(), NONCE, Reason.BAD_SIGNATURE);
    }

    @Test
    void rejectsGarbage() {
        assertRejected("not-a-jwt", NONCE, Reason.MALFORMED);
        assertRejected("", NONCE, Reason.MALFORMED);
        assertRejected(null, NONCE, Reason.MALFORMED);
    }

    @Test
    void rejectsWrongIssuer() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.issuer("https://evil.example.com"))), NONCE, Reason.BAD_ISSUER);
    }

    @Test
    void rejectsWrongAudience() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.audience("other-client"))), NONCE, Reason.BAD_AUDIENCE);
    }

    @Test
    void rejectsExpiredTokenBeyondClockSkew() throws Exception {
        String token = sign(googleKey, claims(b -> b.expirationTime(Date.from(NOW.minusSeconds(61)))));

        assertRejected(token, NONCE, Reason.EXPIRED);
    }

    @Test
    void acceptsTokenExpiredWithinClockSkew() throws Exception {
        String token = sign(googleKey, claims(b -> b.expirationTime(Date.from(NOW.minusSeconds(30)))));

        assertThat(verifier.verify(token, NONCE).subject()).isEqualTo("google-sub-1");
    }

    @Test
    void rejectsTokenIssuedInTheFuture() throws Exception {
        String token = sign(googleKey, claims(b -> b.issueTime(Date.from(NOW.plusSeconds(120)))));

        assertRejected(token, NONCE, Reason.NOT_YET_VALID);
    }

    @Test
    void rejectsUnverifiedEmail() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.claim("email_verified", false))), NONCE, Reason.EMAIL_NOT_VERIFIED);
    }

    @Test
    void rejectsWrongNonce() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.claim("nonce", "other-nonce"))), NONCE, Reason.NONCE_MISMATCH);
    }

    @Test
    void rejectsTokenWithoutNonce() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.claim("nonce", null))), NONCE, Reason.NONCE_MISMATCH);
    }

    @Test
    void rejectsWhenCookieNonceIsMissing() throws Exception {
        assertRejected(sign(googleKey, claims(b -> { })), null, Reason.NONCE_MISSING);
    }

    @Test
    void rejectsMissingSubject() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.subject(null))), NONCE, Reason.MISSING_SUBJECT);
    }

    @Test
    void rejectsMissingEmail() throws Exception {
        assertRejected(sign(googleKey, claims(b -> b.claim("email", null))), NONCE, Reason.MISSING_EMAIL);
    }

    @Test
    void rejectsEverythingWhenClientIdIsNotConfigured() throws Exception {
        var unconfigured = new GoogleIdTokenVerifier("", GoogleIdTokenVerifier.processorFor(
                new ImmutableJWKSet<>(new JWKSet(googleKey.toPublicJWK()))), Clock.fixed(NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> unconfigured.verify(sign(googleKey, claims(b -> { })), NONCE))
                .isInstanceOfSatisfying(GoogleTokenRejectedException.class,
                        e -> assertThat(e.reason()).isEqualTo(Reason.NOT_CONFIGURED));
    }

    private void assertRejected(String token, String nonce, Reason reason) {
        assertThatThrownBy(() -> verifier.verify(token, nonce))
                .isInstanceOfSatisfying(GoogleTokenRejectedException.class, e -> assertThat(e.reason()).isEqualTo(reason));
    }

    private static JWTClaimsSet claims(Consumer<JWTClaimsSet.Builder> overrides) {
        JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                .issuer("https://accounts.google.com")
                .audience(CLIENT_ID)
                .subject("google-sub-1")
                .issueTime(Date.from(NOW.minusSeconds(10)))
                .expirationTime(Date.from(NOW.plusSeconds(3600)))
                .claim("email", "an@acme.com")
                .claim("email_verified", true)
                .claim("name", "An")
                .claim("nonce", NONCE);
        overrides.accept(builder);
        return builder.build();
    }

    private static String sign(RSAKey key, JWTClaimsSet claims) throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.getKeyID())
                .type(JOSEObjectType.JWT).build(), claims);
        jwt.sign(new RSASSASigner(key));
        return jwt.serialize();
    }
}
