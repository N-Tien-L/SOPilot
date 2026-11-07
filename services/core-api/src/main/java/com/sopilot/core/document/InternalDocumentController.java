package com.sopilot.core.document;

import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

/**
 * Callbacks from ai-service (TECH-V2-core-api §8.2), guarded by {@code InternalTokenFilter} and never
 * reachable from the browser origin. The workspace comes from the body because there is no user token;
 * the internal token is what authorises that.
 */
@RestController
@RequestMapping("/internal/documents")
public class InternalDocumentController {

    private final VersionStatusService statuses;

    public InternalDocumentController(VersionStatusService statuses) {
        this.statuses = statuses;
    }

    /** {@code applied} is false for a stale {@code attempt}; both outcomes are {@code 200}. */
    @PatchMapping("/{documentId}/versions/{versionId}/status")
    public Map<String, Boolean> status(@PathVariable UUID documentId, @PathVariable UUID versionId,
                                       @RequestBody VersionStatusService.Update update) {
        return Map.of("applied", statuses.apply(documentId, versionId, update));
    }
}
