package com.poliwise.knowledge.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum ProcessingStep {

    UPLOAD("UPLOAD"), PARSE("PARSE"), CHUNK("CHUNK"), EMBED("EMBED"), INDEX("INDEX");

    private final String value;

    ProcessingStep(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static ProcessingStep fromValue(String value) {
        return Arrays.stream(values()).filter(v -> v.value.equalsIgnoreCase(value)).findFirst()
                .orElseThrow(
                        () -> new IllegalArgumentException("Unknown ProcessingStep: " + value));
    }
}
