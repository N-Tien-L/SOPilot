package com.sopilot.core.identity;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class NonceServiceTest {

    private static final byte[] KEY = "0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8);
    private static final Instant NOW = Instant.parse("2026-11-04T08:00:00Z");
    private static final Duration TTL = Duration.ofMinutes(5);

    private final NonceService service = new NonceService(KEY, TTL, Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void validCookieYieldsItsNonce() {
        NonceService.IssuedNonce issued = service.issue();

        assertThat(service.validate(issued.cookieValue())).contains(issued.nonce());
        assertThat(issued.nonce()).hasSize(22); // 128 bits, base64url without padding
    }

    @Test
    void noncesAreUnique() {
        assertThat(service.issue().nonce()).isNotEqualTo(service.issue().nonce());
    }

    @Test
    void rejectsTamperedNonce() {
        String cookie = service.issue().cookieValue();
        String tampered = "AAAAAAAAAAAAAAAAAAAAAA" + cookie.substring(cookie.indexOf('.'));

        assertThat(service.validate(tampered)).isEmpty();
    }

    @Test
    void rejectsExtendedExpiry() {
        String[] parts = service.issue().cookieValue().split("\\.");
        String extended = parts[0] + "." + (Long.parseLong(parts[1]) + 3600) + "." + parts[2];

        assertThat(service.validate(extended)).isEmpty();
    }

    @Test
    void rejectsExpiredCookie() {
        String cookie = service.issue().cookieValue();
        NonceService later = new NonceService(KEY, TTL, Clock.fixed(NOW.plus(TTL).plusSeconds(1), ZoneOffset.UTC));

        assertThat(later.validate(cookie)).isEmpty();
    }

    @Test
    void rejectsCookieSignedWithAnotherKey() {
        String cookie = service.issue().cookieValue();
        NonceService other = new NonceService("ffffffffffffffffffffffffffffffff".getBytes(StandardCharsets.UTF_8),
                TTL, Clock.fixed(NOW, ZoneOffset.UTC));

        assertThat(other.validate(cookie)).isEmpty();
    }

    @Test
    void rejectsMalformedCookies() {
        assertThat(service.validate(null)).isEmpty();
        assertThat(service.validate("")).isEmpty();
        assertThat(service.validate("a.b")).isEmpty();
        assertThat(service.validate("a.notanumber.c")).isEmpty();
    }

    @Test
    void refusesShortKeys() {
        assertThatThrownBy(() -> new NonceService(new byte[16], TTL, Clock.systemUTC()))
                .isInstanceOf(IllegalStateException.class);
    }
}
