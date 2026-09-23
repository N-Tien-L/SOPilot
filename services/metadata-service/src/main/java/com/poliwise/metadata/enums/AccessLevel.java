package com.poliwise.metadata.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum AccessLevel {

    PUBLIC("PUBLIC"), DEPARTMENT_ONLY("DEPARTMENT_ONLY"), RESTRICTED("RESTRICTED");

    private final String value;

    AccessLevel(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static AccessLevel fromValue(String value) {
        return Arrays.stream(AccessLevel.values()).filter(v -> v.value.equalsIgnoreCase(value))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unknown AccessLevel: " + value));
    }
}
