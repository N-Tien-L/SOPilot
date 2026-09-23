package com.poliwise.knowledge.dto;

import java.util.UUID;

/**
 * Conflict status returned to the frontend when a save callback detects
 * a newer version has been uploaded by someone else.
 */
public record ConflictStatusResponse(
    boolean hasConflict,
    boolean hasConflictFile,
    UUID documentId,
    int lockedVersion,
    int currentVersion,
    UUID lockedBy,
    String lockedByUsername,
    String message,
    VersionDiffInfo diffInfo
) {}
