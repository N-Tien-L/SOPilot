package com.sopilot.core.tag;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tag.TagRepository.Tag;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * Flat tags per workspace (TECH §3.4, §5.6). Tags are created when attached to a document.
 */
@Service
public class TagService {

    private static final int MAX_TAG_LENGTH = 50;

    private final TagRepository tags;
    private final TenantTx tenant;

    public TagService(TagRepository tags, TenantTx tenant) {
        this.tags = tags;
        this.tenant = tenant;
    }

    public List<Tag> list(AuthPrincipal principal) {
        return tenant.run(principal, () -> tags.list(principal.workspaceId()));
    }

    public List<String> findTagsForDocument(UUID workspaceId, UUID documentId) {
        return tags.findTagsForDocument(workspaceId, documentId);
    }

    /**
     * Validates, deduplicates case-insensitively, creates missing tags, and updates
     * {@code core.document_tags}. Must be called inside a tenant transaction.
     */
    public List<String> assignTags(UUID workspaceId, UUID documentId, List<String> rawTags) {
        if (rawTags == null || rawTags.isEmpty()) {
            tags.setDocumentTags(workspaceId, documentId, List.of());
            return List.of();
        }
        Map<String, String> unique = new LinkedHashMap<>();
        for (String raw : rawTags) {
            if (raw == null) {
                throw invalidTag();
            }
            String trimmed = raw.strip();
            if (trimmed.isEmpty() || trimmed.length() > MAX_TAG_LENGTH) {
                throw invalidTag();
            }
            unique.putIfAbsent(trimmed.toLowerCase(Locale.ROOT), trimmed);
        }
        List<UUID> tagIds = new ArrayList<>();
        List<String> assignedNames = new ArrayList<>();
        for (String tagName : unique.values()) {
            Tag tag = tags.findByName(workspaceId, tagName)
                    .orElseGet(() -> tags.findOrCreate(UuidV7.generate(), workspaceId, tagName));
            tagIds.add(tag.id());
            assignedNames.add(tag.name());
        }
        tags.setDocumentTags(workspaceId, documentId, tagIds);
        return assignedNames;
    }

    private static ApiException invalidTag() {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Tag name is invalid.",
                Map.of("fields", Map.of("tags", "Each tag must be between 1 and " + MAX_TAG_LENGTH + " characters.")));
    }
}
