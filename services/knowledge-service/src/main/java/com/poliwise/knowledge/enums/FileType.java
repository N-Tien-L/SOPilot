package com.poliwise.knowledge.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Arrays;

public enum FileType {

    PDF("PDF"), DOCX("DOCX"), XLSX("XLSX"), DOC("DOC"), XLS("XLS"), TXT("TXT"), PNG("PNG"), JPG("JPG"), JPEG("JPEG"), MD("MD"), UNKNOWN("UNKNOWN");

    private final String value;

    FileType(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    @JsonCreator
    public static FileType fromValue(String value) {
        return Arrays.stream(values()).filter(v -> v.value.equalsIgnoreCase(value)).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unknown FileType: " + value));
    }
}
