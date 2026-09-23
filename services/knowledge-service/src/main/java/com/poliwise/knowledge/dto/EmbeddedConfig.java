package com.poliwise.knowledge.dto;

public record EmbeddedConfig(
    String embedUrl,
    String fullscreenUrl,
    String saveUrl,
    String snapshotUrl,
    String toolbarDocked
) {}
