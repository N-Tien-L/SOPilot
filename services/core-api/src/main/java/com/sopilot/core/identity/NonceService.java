package com.sopilot.core.identity;

import com.sopilot.core.config.SopilotProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.util.Base64;
import java.util.Optional;

/**
 * Stateless login nonce (TECH-V2-core-api §5.1, A9). The browser gets the nonce for Google
 * Identity Services and an HttpOnly cookie {@code <nonce>.<expEpochSeconds>.<HMAC-SHA256>};
 * on login the ID token's {@code nonce} claim must equal the nonce in a valid, unexpired cookie.
 * Nothing is stored in the database.
 */
@Component
public class NonceService {

    private static final Logger log = LoggerFactory.getLogger(NonceService.class);
    private static final int MIN_KEY_BYTES = 32;
    private static final Base64.Encoder B64 = Base64.getUrlEncoder().withoutPadding();

    private final SecureRandom random = new SecureRandom();
    private final byte[] key;
    private final Duration ttl;
    private final Clock clock;

    @Autowired
    public NonceService(SopilotProperties properties) {
        this(resolveKey(properties.auth()), properties.auth().nonceTtl(), Clock.systemUTC());
    }

    NonceService(byte[] key, Duration ttl, Clock clock) {
        if (key.length < MIN_KEY_BYTES) {
            throw new IllegalStateException("SOPILOT_NONCE_HMAC_KEY must be at least " + MIN_KEY_BYTES + " bytes");
        }
        this.key = key.clone();
        this.ttl = ttl;
        this.clock = clock;
    }

    public Duration ttl() {
        return ttl;
    }

    /** New 128-bit nonce and the signed cookie value that binds it to this browser. */
    public IssuedNonce issue() {
        byte[] raw = new byte[16];
        random.nextBytes(raw);
        String nonce = B64.encodeToString(raw);
        long exp = clock.instant().plus(ttl).getEpochSecond();
        String signed = nonce + "." + exp;
        return new IssuedNonce(nonce, signed + "." + hmac(signed));
    }

    /** The nonce inside a cookie value if the HMAC is valid and it has not expired. */
    public Optional<String> validate(String cookieValue) {
        if (cookieValue == null || cookieValue.length() > 256) {
            return Optional.empty();
        }
        String[] parts = cookieValue.split("\\.", -1);
        if (parts.length != 3 || parts[0].isEmpty()) {
            return Optional.empty();
        }
        String signed = parts[0] + "." + parts[1];
        if (!MessageDigest.isEqual(hmac(signed).getBytes(StandardCharsets.US_ASCII),
                parts[2].getBytes(StandardCharsets.US_ASCII))) {
            return Optional.empty();
        }
        long exp;
        try {
            exp = Long.parseLong(parts[1]);
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
        if (clock.instant().getEpochSecond() > exp) {
            return Optional.empty();
        }
        return Optional.of(parts[0]);
    }

    private String hmac(String value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return B64.encodeToString(mac.doFinal(value.getBytes(StandardCharsets.US_ASCII)));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("HmacSHA256 unavailable");
        }
    }

    private static byte[] resolveKey(SopilotProperties.Auth auth) {
        String configured = auth.nonceHmacKey();
        if (configured != null && !configured.isBlank()) {
            return configured.getBytes(StandardCharsets.UTF_8);
        }
        if (!auth.allowEphemeralNonceKey()) {
            throw new IllegalStateException("SOPILOT_NONCE_HMAC_KEY is required outside the local/test profiles");
        }
        log.warn("Using an ephemeral nonce HMAC key (local/test profile)");
        byte[] generated = new byte[MIN_KEY_BYTES];
        new SecureRandom().nextBytes(generated);
        return generated;
    }

    public record IssuedNonce(String nonce, String cookieValue) {
    }
}
