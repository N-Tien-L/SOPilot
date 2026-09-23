package com.poliwise.knowledge.dto;

import java.util.UUID;

public record ConflictResolutionRequest(
    String strategy,       // "merge_as_new", "discard_mine", "force_push"
    UUID lockToken,
    String mergedChangelog
) {}
