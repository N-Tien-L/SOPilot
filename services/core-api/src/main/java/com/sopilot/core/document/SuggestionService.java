package com.sopilot.core.document;

import com.sopilot.core.category.CategoryRepository;
import com.sopilot.core.category.CategoryRepository.CategoryStatus;
import com.sopilot.core.common.ApiException;
import com.sopilot.core.document.DocumentRepository.DocumentHead;
import com.sopilot.core.document.DocumentRepository.MetaSources;
import com.sopilot.core.tag.TagRepository;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Applies ai-service metadata suggestions (V2-25, TECH-V2-ai-service §5.7).
 *
 * <p>The suggestion is stored for every version it belongs to, but it changes the document only while
 * that version is the current one. A field is changed only when its source is not {@code USER}; the
 * visibility and department fields are never touched. Tags attach only when they already exist in the
 * workspace, so a model cannot create tags. A proposed new category is stored and not created.
 */
@Service
public class SuggestionService {

    static final Set<String> METHODS = Set.of("LLM", "RULES_FALLBACK");
    private static final String USER = "USER";
    private static final String SUGGESTED = "SUGGESTED";

    /** What ai-service reports; {@code tags} are names, {@code timings} are for logs and reports only. */
    public record Update(UUID workspaceId, UUID versionId, String method, String title, String description,
                         UUID categoryId, String proposedCategoryName, List<String> tags,
                         Map<String, Object> timings) {
    }

    private final DocumentRepository docs;
    private final CategoryRepository categories;
    private final TagRepository tags;
    private final TenantTx tenant;

    public SuggestionService(DocumentRepository docs, CategoryRepository categories, TagRepository tags,
                             TenantTx tenant) {
        this.docs = docs;
        this.categories = categories;
        this.tags = tags;
        this.tenant = tenant;
    }

    /** @return false when the version is not the document's current one; nothing is applied then */
    public boolean apply(UUID documentId, Update u) {
        if (u.workspaceId() == null || u.versionId() == null || !METHODS.contains(u.method())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Request is invalid.");
        }
        UUID wid = u.workspaceId();
        return tenant.run(wid, null, () -> {
            DocumentHead head = docs.lockDocument(wid, documentId)
                    .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Document not found."));
            // A version of another document (same workspace or not) is rejected before anything is written:
            // the suggestion row is keyed by version_id, so storing it under this document would be wrong.
            docs.findVersion(wid, documentId, u.versionId())
                    .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "Version not found."));
            List<String> tagNames = cleanTags(u.tags());
            docs.upsertSuggestion(wid, documentId, u.versionId(), u.method(), clean(u.title(), 200),
                    clean(u.description(), 500), u.categoryId(), clean(u.proposedCategoryName(), 100),
                    tagNames.toArray(String[]::new));
            if (!u.versionId().equals(head.currentVersionId())) {
                return false;
            }
            MetaSources cur = docs.metaSources(wid, documentId);

            String title = cur.title();
            String titleSource = cur.titleSource();
            // The title is never applied automatically: a wrong title is the most visible mistake, and the first
            // Markdown heading is often a section name. The suggestion is stored (upsertSuggestion above) so the
            // user can accept it.

            String description = cur.description();
            String descriptionSource = cur.descriptionSource();
            String suggestedDescription = clean(u.description(), 500);
            if (!USER.equals(descriptionSource) && suggestedDescription != null) {
                description = suggestedDescription;
                descriptionSource = SUGGESTED;
            }

            UUID categoryId = cur.categoryId();
            String categorySource = cur.categorySource();
            if (!USER.equals(categorySource) && u.categoryId() != null && activeCategory(wid, u.categoryId())) {
                categoryId = u.categoryId();
                categorySource = SUGGESTED;
            }

            String tagsSource = cur.tagsSource();
            if (!USER.equals(tagsSource)) {
                List<UUID> tagIds = existingTagIds(wid, tagNames);
                if (!tagIds.isEmpty()) {
                    tags.setDocumentTags(wid, documentId, tagIds);
                    tagsSource = SUGGESTED;
                }
            }

            docs.updateMetadata(wid, documentId, title, titleSource, description, descriptionSource,
                    categoryId, categorySource, cur.language(), cur.languageSource(), tagsSource);
            return true;
        });
    }

    private boolean activeCategory(UUID wid, UUID categoryId) {
        return categories.find(wid, categoryId).filter(c -> c.status() == CategoryStatus.ACTIVE).isPresent();
    }

    private List<UUID> existingTagIds(UUID wid, List<String> names) {
        List<UUID> ids = new ArrayList<>();
        for (String name : names) {
            tags.findByName(wid, name).ifPresent(tag -> ids.add(tag.id()));
        }
        return ids;
    }

    private static List<String> cleanTags(List<String> raw) {
        List<String> out = new ArrayList<>();
        if (raw == null) {
            return out;
        }
        for (String t : raw) {
            String c = clean(t, 50);
            if (c != null && !out.contains(c)) {
                out.add(c);
            }
        }
        return out;
    }

    /** Stripped, capped, and {@code null} when nothing is left. */
    static String clean(String value, int max) {
        if (value == null) {
            return null;
        }
        String s = value.strip();
        if (s.isEmpty()) {
            return null;
        }
        return s.length() <= max ? s : s.substring(0, max).strip();
    }
}
