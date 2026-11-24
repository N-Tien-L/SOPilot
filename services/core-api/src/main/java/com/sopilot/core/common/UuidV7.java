package com.sopilot.core.common;

import java.security.SecureRandom;
import java.util.UUID;

/** RFC 9562 UUIDv7: time-ordered primary keys generated in the application (TECH §3). */
public final class UuidV7 {

    private static final SecureRandom RANDOM = new SecureRandom();

    private UuidV7() {
    }

    public static UUID generate() {
        long millis = System.currentTimeMillis();
        byte[] rand = new byte[10];
        RANDOM.nextBytes(rand);

        long msb = (millis & 0xFFFF_FFFF_FFFFL) << 16;
        msb |= 0x7000L;                                        // version 7
        msb |= ((rand[0] & 0x0FL) << 8) | (rand[1] & 0xFFL);    // rand_a (12 bits)

        long lsb = 0x8000_0000_0000_0000L;                     // variant 10
        lsb |= (rand[2] & 0x3FL) << 56;
        for (int i = 3; i < 10; i++) {
            lsb |= (rand[i] & 0xFFL) << (8 * (9 - i));
        }
        return new UUID(msb, lsb);
    }
}
