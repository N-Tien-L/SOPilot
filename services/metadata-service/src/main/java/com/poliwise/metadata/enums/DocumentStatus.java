package com.poliwise.metadata.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum DocumentStatus {

    DRAFT("DRAFT"), PUBLISHED("PUBLISHED"), ARCHIVED("ARCHIVED"), EXPIRED("EXPIRED");

    private final String value;

    DocumentStatus(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static DocumentStatus fromValue(String value) {
        return Arrays.stream(DocumentStatus.values()).filter(v -> v.value.equalsIgnoreCase(value))
                .findFirst().orElseThrow(
                        () -> new IllegalArgumentException("Unknown DocumentStatus: " + value));
    }
}
