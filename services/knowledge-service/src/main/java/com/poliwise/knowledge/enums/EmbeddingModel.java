package com.poliwise.knowledge.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum EmbeddingModel {

    TEXT_EMBEDDING_3_SMALL("TEXT_EMBEDDING_3_SMALL"), TEXT_EMBEDDING_3_LARGE(
            "TEXT_EMBEDDING_3_LARGE"), MULTILINGUAL_E5_LARGE("MULTILINGUAL_E5_LARGE"), BGE_M3("BGE_M3");

    private final String value;

    EmbeddingModel(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static EmbeddingModel fromValue(String value) {
        return Arrays.stream(values()).filter(v -> v.value.equalsIgnoreCase(value)).findFirst()
                .orElseThrow(
                        () -> new IllegalArgumentException("Unknown EmbeddingModel: " + value));
    }
}
