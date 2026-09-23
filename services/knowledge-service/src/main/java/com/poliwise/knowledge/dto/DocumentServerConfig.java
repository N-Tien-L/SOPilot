package com.poliwise.knowledge.dto;

public record DocumentServerConfig(
    Lang lang,
    CallbackSettings callbacks,
    EditorConfig editorConfig,
    EmbeddedConfig embedded
) {}
