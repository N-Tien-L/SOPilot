package com.sopilot.core.common;

import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class UuidV7Test {

    @Test
    void hasVersion7AndRfcVariant() {
        UUID id = UuidV7.generate();

        assertThat(id.version()).isEqualTo(7);
        assertThat(id.variant()).isEqualTo(2);
    }

    @Test
    void embedsCurrentTimeAndIsUnique() {
        long before = System.currentTimeMillis();
        UUID id = UuidV7.generate();
        long after = System.currentTimeMillis();

        long millis = id.getMostSignificantBits() >>> 16;
        assertThat(millis).isBetween(before, after);

        var seen = new HashSet<UUID>();
        for (int i = 0; i < 10_000; i++) {
            assertThat(seen.add(UuidV7.generate())).isTrue();
        }
    }
}
