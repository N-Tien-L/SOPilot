package com.poliwise.knowledge.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record VersionDiffInfo(
    String baseContent,
    String theirContent,
    String theirChangelog,
    OffsetDateTime theirCreatedAt,
    String theirCreatedByUsername
) {}
