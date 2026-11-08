package com.sopilot.core.security;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.KeyUse;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.sopilot.core.config.SopilotProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateCrtKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.RSAPublicKeySpec;
import java.util.Base64;

/**
 * RS256 signing key for access tokens (TECH §5.1). Loaded from a PKCS#8 PEM file at
 * {@code SOPILOT_JWT_PRIVATE_KEY_PATH}; only the {@code local}/{@code test} profiles may fall
 * back to a key generated in memory. Key material is never logged.
 */
@Component
public class SigningKeyProvider {

    private static final Logger log = LoggerFactory.getLogger(SigningKeyProvider.class);
    private static final int MIN_RSA_BITS = 2048;

    private final RSAKey signingKey;

    @Autowired
    public SigningKeyProvider(SopilotProperties properties) {
        SopilotProperties.Jwt jwt = properties.jwt();
        this.signingKey = load(jwt);
    }

    /** Package-private for tests. */
    SigningKeyProvider(RSAKey signingKey) {
        this.signingKey = signingKey;
    }

    public RSAKey signingKey() {
        return signingKey;
    }

    /** Public keys only; safe to publish at {@code /.well-known/jwks.json}. */
    public JWKSet publicJwkSet() {
        return new JWKSet(signingKey.toPublicJWK());
    }

    private static RSAKey load(SopilotProperties.Jwt jwt) {
        String path = jwt.privateKeyPath();
        try {
            if (path == null || path.isBlank()) {
                if (!jwt.generateIfMissing()) {
                    throw new IllegalStateException(
                            "SOPILOT_JWT_PRIVATE_KEY_PATH is required outside the local/test profiles");
                }
                RSAKey generated = new RSAKeyGenerator(MIN_RSA_BITS)
                        .keyUse(KeyUse.SIGNATURE).algorithm(JWSAlgorithm.RS256)
                        .keyIDFromThumbprint(true).generate();
                log.warn("Using an in-memory access-token signing key (local/test profile); tokens do not survive a restart");
                return withKid(generated, jwt.kid());
            }
            return withKid(fromPem(Files.readString(Path.of(path), StandardCharsets.US_ASCII)), jwt.kid());
        } catch (IOException | GeneralSecurityException | JOSEException e) {
            // Do not include the key path contents; the exception type is enough to diagnose.
            throw new IllegalStateException("Cannot load the access-token signing key (" + e.getClass().getSimpleName() + ")");
        }
    }

    static RSAKey fromPem(String pem) throws GeneralSecurityException, JOSEException {
        if (!pem.contains("-----BEGIN PRIVATE KEY-----")) {
            throw new GeneralSecurityException("Expected an unencrypted PKCS#8 PEM private key");
        }
        String base64 = pem.replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");
        KeyFactory factory = KeyFactory.getInstance("RSA");
        var privateKey = (RSAPrivateCrtKey) factory.generatePrivate(
                new PKCS8EncodedKeySpec(Base64.getDecoder().decode(base64)));
        if (privateKey.getModulus().bitLength() < MIN_RSA_BITS) {
            throw new GeneralSecurityException("RSA key must be at least " + MIN_RSA_BITS + " bits");
        }
        var publicKey = (RSAPublicKey) factory.generatePublic(
                new RSAPublicKeySpec(privateKey.getModulus(), privateKey.getPublicExponent()));
        RSAKey key = new RSAKey.Builder(publicKey).privateKey(privateKey)
                .keyUse(KeyUse.SIGNATURE).algorithm(JWSAlgorithm.RS256).build();
        return new RSAKey.Builder(key).keyIDFromThumbprint().build();
    }

    private static RSAKey withKid(RSAKey key, String kid) {
        if (kid == null || kid.isBlank()) {
            return key;
        }
        return new RSAKey.Builder(key).keyID(kid).build();
    }
}
