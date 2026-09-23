package com.poliwise.knowledge.dto;

public record EditorConfigResponse(
    String documentType,
    String documentTitle,
    String documentUrl,
    String documentFileType,
    DocumentServerConfig config
) {}
