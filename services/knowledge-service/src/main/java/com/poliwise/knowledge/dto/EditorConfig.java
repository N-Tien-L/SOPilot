package com.poliwise.knowledge.dto;

public record EditorConfig(
    int width,
    int height,
    String autocompleteUrl,
    String sharingSettingsUrl,
    String fileChoiceUrl,
    CallbackUser user
) {}
