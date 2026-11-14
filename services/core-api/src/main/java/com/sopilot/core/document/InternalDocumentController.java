package com.sopilot.core.document;

import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PutMapping;
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
    private final SuggestionService suggestions;

    public InternalDocumentController(VersionStatusService statuses, SuggestionService suggestions) {
        this.statuses = statuses;
        this.suggestions = suggestions;
    }

    /** Metadata suggestions (V2-25): {@code applied} is false when the version is no longer current. */
    @PutMapping("/{documentId}/suggestions")
    public Map<String, Boolean> suggestions(@PathVariable UUID documentId,
                                            @RequestBody SuggestionService.Update update) {
        return Map.of("applied", suggestions.apply(documentId, update));
    }

    /** {@code applied} is false for a stale {@code attempt}; both outcomes are {@code 200}. */
    @PatchMapping("/{documentId}/versions/{versionId}/status")
    public Map<String, Boolean> status(@PathVariable UUID documentId, @PathVariable UUID versionId,
                                       @RequestBody VersionStatusService.Update update) {
        return Map.of("applied", statuses.apply(documentId, versionId, update));
    }
}
