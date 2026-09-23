package com.poliwise.metadata.service;

import com.poliwise.metadata.dto.CreateTagRequest;
import com.poliwise.metadata.dto.UpdateTagRequest;
import com.poliwise.metadata.dto.TagResponse;
import com.poliwise.metadata.entity.Tag;
import com.poliwise.metadata.exception.ResourceNotFoundException;
import com.poliwise.metadata.exception.DuplicateResourceException;
import com.poliwise.metadata.repository.TagRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class TagService {

    private static final Logger log = LoggerFactory.getLogger(TagService.class);

    private final TagRepository tagRepository;

    public TagService(TagRepository tagRepository) {
        this.tagRepository = tagRepository;
    }

    @Transactional
    public TagResponse create(CreateTagRequest request) {
        // Check duplicate name (case-insensitive)
        if (tagRepository.existsByNameIgnoreCase(request.name())) {
            throw new DuplicateResourceException("Tag name already exists: " + request.name());
        }

        String slug = generateSlug(request.name());

        if (tagRepository.findBySlug(slug).isPresent()) {
            throw new DuplicateResourceException("Tag slug already exists: " + slug);
        }

        Tag tag = Tag.builder()
                .id(UUID.randomUUID())
                .name(request.name().trim())
                .slug(slug)
                .color(request.color() != null ? request.color() : "#6366f1")
                .usageCount(0)
                .createdAt(OffsetDateTime.now())
                .build();

        Tag saved = tagRepository.save(tag);
        log.info("Created tag: id={}, name={}", saved.getId(), saved.getName());
        return toResponse(saved);
    }

    public List<TagResponse> getAll() {
        return tagRepository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public List<TagResponse> getActive() {
        return tagRepository.findAll().stream()
                .filter(t -> t.getUsageCount() != null && t.getUsageCount() >= 0)
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public List<TagResponse> getPopular() {
        return tagRepository.findTopByOrderByUsageCountDesc().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public TagResponse getById(UUID id) {
        Tag tag = tagRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Tag not found: " + id));
        return toResponse(tag);
    }

    public TagResponse getBySlug(String slug) {
        Tag tag = tagRepository.findBySlug(slug)
                .orElseThrow(() -> new ResourceNotFoundException("Tag not found with slug: " + slug));
        return toResponse(tag);
    }

    public TagResponse getByName(String name) {
        Tag tag = tagRepository.findByNameIgnoreCase(name)
                .orElseThrow(() -> new ResourceNotFoundException("Tag not found with name: " + name));
        return toResponse(tag);
    }

    public Page<TagResponse> search(String keyword, Pageable pageable) {
        return tagRepository.searchByName(keyword, pageable).map(this::toResponse);
    }

    @Transactional
    public TagResponse update(UUID id, UpdateTagRequest request) {
        Tag tag = tagRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Tag not found: " + id));

        if (request.name() != null && !request.name().equals(tag.getName())) {
            String newSlug = generateSlug(request.name());
            tagRepository.findBySlug(newSlug).ifPresent(existing -> {
                if (!existing.getId().equals(id)) {
                    throw new DuplicateResourceException("Tag already exists with name: " + request.name());
                }
            });
            tag.setName(request.name().trim());
            tag.setSlug(newSlug);
        }

        if (request.color() != null) {
            tag.setColor(request.color());
        }

        Tag saved = tagRepository.save(tag);
        log.info("Updated tag: id={}, name={}", id, saved.getName());
        return toResponse(saved);
    }

    @Transactional
    public void delete(UUID id) {
        Tag tag = tagRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Tag not found: " + id));

        tagRepository.delete(tag);
        log.info("Deleted tag: id={}, name={}", id, tag.getName());
    }

    /**
     * Bulk resolve tags - find existing or create new ones.
     * This is the "find-or-create" strategy for tags.
     * 
     * @param tagNames List of tag names to resolve
     * @return ResolveTagsResponse containing resolved tag IDs and any newly created tags
     */
    @Transactional
    public com.poliwise.metadata.dto.ResolveTagsResponse resolveTags(List<String> tagNames) {
        if (tagNames == null || tagNames.isEmpty()) {
            return new com.poliwise.metadata.dto.ResolveTagsResponse(Collections.emptyMap(), Collections.emptyList());
        }

        // 1. Normalize tag names and find existing tags
        List<String> normalizedNames = tagNames.stream()
                .filter(name -> name != null && !name.isBlank())
                .map(String::trim)
                .map(this::generateSlug)
                .distinct()
                .toList();

        if (normalizedNames.isEmpty()) {
            return new com.poliwise.metadata.dto.ResolveTagsResponse(Collections.emptyMap(), Collections.emptyList());
        }

        // 2. Find existing tags by name (case-insensitive)
        List<Tag> existingTags = tagRepository.findByNameInIgnoreCase(tagNames);
        Map<String, UUID> resolvedMap = new LinkedHashMap<>();
        List<UUID> orderedTagIds = new ArrayList<>();
        Set<UUID> foundIds = new HashSet<>();

        // Map existing tags
        for (Tag tag : existingTags) {
            String normalizedName = generateSlug(tag.getName());
            resolvedMap.put(normalizedName, tag.getId());
            foundIds.add(tag.getId());
        }

        // 3. Create missing tags (find-or-create)
        List<Tag> newTags = new ArrayList<>();
        for (String tagName : tagNames) {
            if (tagName == null || tagName.isBlank()) continue;
            
            String normalizedName = generateSlug(tagName.trim());
            
            if (!resolvedMap.containsKey(normalizedName)) {
                // Not found, create new tag
                String slug = generateSlug(tagName.trim());
                
                // Double-check with slug (race condition prevention)
                Optional<Tag> bySlug = tagRepository.findBySlug(slug);
                if (bySlug.isPresent()) {
                    // Tag was created by another request (race condition)
                    Tag existingBySlug = bySlug.get();
                    resolvedMap.put(normalizedName, existingBySlug.getId());
                    if (!foundIds.contains(existingBySlug.getId())) {
                        orderedTagIds.add(existingBySlug.getId());
                        foundIds.add(existingBySlug.getId());
                    }
                } else {
                    // Create new tag
                    Tag newTag = Tag.builder()
                            .id(UUID.randomUUID())
                            .name(tagName.trim())
                            .slug(slug)
                            .color("#6366f1")
                            .usageCount(0)
                            .createdAt(OffsetDateTime.now())
                            .build();
                    newTag = tagRepository.save(newTag);
                    resolvedMap.put(normalizedName, newTag.getId());
                    newTags.add(newTag);
                    orderedTagIds.add(newTag.getId());
                    foundIds.add(newTag.getId());
                    
                    log.info("Auto-created tag during resolution: name={}, id={}", tagName.trim(), newTag.getId());
                }
            } else {
                // Found existing tag
                UUID existingId = resolvedMap.get(normalizedName);
                if (!foundIds.contains(existingId)) {
                    orderedTagIds.add(existingId);
                    foundIds.add(existingId);
                }
            }
        }

        log.info("Resolved {} tags: {} existing, {} newly created", 
                tagNames.size(), existingTags.size(), newTags.size());

        return new com.poliwise.metadata.dto.ResolveTagsResponse(resolvedMap, orderedTagIds);
    }

    /**
     * Increment usage count for tags (called when documents are tagged)
     */
    @Transactional
    public void incrementUsageCount(List<UUID> tagIds) {
        if (tagIds == null || tagIds.isEmpty()) return;
        
        for (UUID tagId : tagIds) {
            tagRepository.findById(tagId).ifPresent(tag -> {
                tag.setUsageCount(tag.getUsageCount() != null ? tag.getUsageCount() + 1 : 1);
                tagRepository.save(tag);
            });
        }
    }

    /**
     * Decrement usage count for tags (called when documents are untagged)
     */
    @Transactional
    public void decrementUsageCount(List<UUID> tagIds) {
        if (tagIds == null || tagIds.isEmpty()) return;
        
        for (UUID tagId : tagIds) {
            tagRepository.findById(tagId).ifPresent(tag -> {
                tag.setUsageCount(tag.getUsageCount() != null && tag.getUsageCount() > 0 
                        ? tag.getUsageCount() - 1 : 0);
                tagRepository.save(tag);
            });
        }
    }

    private String generateSlug(String name) {
        if (name == null) {
            // Fallback random slug
            return "tag-" + UUID.randomUUID().toString().substring(0, 8);
        }
        String slug = name.trim().toLowerCase()
                .replaceAll("[àáạảãâầấậẩẫăằắặẳẵ]", "a")
                .replaceAll("[èéẹẻẽêềếệểễ]", "e")
                .replaceAll("[ìíịỉĩ]", "i")
                .replaceAll("[òóọỏõôồốộổỗơờớợởỡ]", "o")
                .replaceAll("[ùúụủũưừứựửữ]", "u")
                .replaceAll("[ỳýỵỷỹ]", "y")
                .replaceAll("[đ]", "d")
                .replaceAll("[^a-z0-9\\s-]", "")
                .replaceAll("\\s+", "-")
                .replaceAll("-+", "-")
                .replaceAll("^-|-$", "");
        if (slug.isEmpty()) {
            // Fallback random slug
            return "tag-" + UUID.randomUUID().toString().substring(0, 8);
        }
        return slug;
    }

    private TagResponse toResponse(Tag tag) {
        return new TagResponse(
                tag.getId(),
                tag.getName(),
                tag.getSlug(),
                tag.getColor(),
                tag.getUsageCount(),
                tag.getCreatedAt());
    }
}
