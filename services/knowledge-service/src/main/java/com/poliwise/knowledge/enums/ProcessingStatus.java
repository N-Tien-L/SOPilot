package com.poliwise.knowledge.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum ProcessingStatus {

    STAGING("STAGING"), UPLOADED("UPLOADED"), PARSING("PARSING"), PARSED("PARSED"), CHUNKING("CHUNKING"), CHUNKED(
            "CHUNKED"), EMBEDDING("EMBEDDING"), EMBEDDED("EMBEDDED"), INDEXING(
                    "INDEXING"), INDEXED("INDEXED"), READY("READY"), FAILED("FAILED"), DUPLICATE("DUPLICATE");

    private final String value;

    ProcessingStatus(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static ProcessingStatus fromValue(String value) {
        return Arrays.stream(ProcessingStatus.values()).filter(v -> v.value.equalsIgnoreCase(value))
                .findFirst().orElseThrow(
                        () -> new IllegalArgumentException("Unknown ProcessingStatus: " + value));
    }
}
