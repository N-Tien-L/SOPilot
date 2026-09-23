package com.poliwise.knowledge.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum ChunkingStrategy {

    RECURSIVE("RECURSIVE"), SEMANTIC("SEMANTIC"), FIXED_SIZE("FIXED_SIZE"), SENTENCE("SENTENCE");

    private final String value;

    ChunkingStrategy(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static ChunkingStrategy fromValue(String value) {
        return Arrays.stream(values()).filter(v -> v.value.equalsIgnoreCase(value)).findFirst()
                .orElseThrow(
                        () -> new IllegalArgumentException("Unknown ChunkingStrategy: " + value));
    }
}
