package com.sopilot.core.common;

import org.springframework.http.HttpStatus;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.UUID;

/** Opaque keyset cursor over {@code (created_at DESC, id DESC)}. */
public record Cursor(OffsetDateTime createdAt, UUID id) {

    public String encode() {
        String raw = createdAt.toString() + "|" + id;
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    /** Null or blank means the first page; a malformed cursor is a client error. */
    public static Cursor decode(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            String raw = new String(Base64.getUrlDecoder().decode(value), StandardCharsets.UTF_8);
            int bar = raw.indexOf('|');
            return new Cursor(OffsetDateTime.parse(raw.substring(0, bar)), UUID.fromString(raw.substring(bar + 1)));
        } catch (RuntimeException e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Cursor is invalid.");
        }
    }

    public static int limit(Integer requested) {
        return requested == null ? 20 : Math.max(1, Math.min(requested, 100));
    }
}
