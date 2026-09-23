package com.poliwise.metadata.controller;

import com.poliwise.metadata.dto.*;
import com.poliwise.metadata.security.SecurityUtils;
import com.poliwise.metadata.service.TagService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/tags")
public class TagController {

    private final TagService tagService;

    public TagController(TagService tagService) {
        this.tagService = tagService;
    }

    // ===== CRUD Operations =====

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<TagResponse> create(@Valid @RequestBody CreateTagRequest request) {
        TagResponse response = tagService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping
    public ResponseEntity<List<TagResponse>> getAll() {
        List<TagResponse> tags = tagService.getAll();
        return ResponseEntity.ok(tags);
    }

    @GetMapping("/active")
    public ResponseEntity<List<TagResponse>> getActive() {
        List<TagResponse> tags = tagService.getActive();
        return ResponseEntity.ok(tags);
    }

    @GetMapping("/popular")
    public ResponseEntity<List<TagResponse>> getPopular() {
        List<TagResponse> tags = tagService.getPopular();
        return ResponseEntity.ok(tags);
    }

    @GetMapping("/search")
    public ResponseEntity<PagedTagResponse> search(
            @RequestParam String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        Page<TagResponse> result = tagService.search(keyword, PageRequest.of(page - 1, size, Sort.by("usageCount").descending()));
        return ResponseEntity.ok(new PagedTagResponse(
                result.getContent(),
                result.getNumber() + 1,
                result.getSize(),
                result.getTotalElements(),
                result.getTotalPages()
        ));
    }

    @GetMapping("/{id}")
    public ResponseEntity<TagResponse> get(@PathVariable UUID id) {
        TagResponse response = tagService.getById(id);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/slug/{slug}")
    public ResponseEntity<TagResponse> getBySlug(@PathVariable String slug) {
        TagResponse response = tagService.getBySlug(slug);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/name/{name}")
    public ResponseEntity<TagResponse> getByName(@PathVariable String name) {
        TagResponse response = tagService.getByName(name);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<TagResponse> update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateTagRequest request) {
        TagResponse response = tagService.update(id, request);
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        tagService.delete(id);
        return ResponseEntity.noContent().build();
    }

    // ===== Bulk Operations =====

    /**
     * Resolve tags - find existing tags or create new ones (find-or-create).
     * This endpoint allows bulk creation of tags with automatic slug generation.
     */
    @PostMapping("/resolve")
    @PreAuthorize("hasRole('ADMIN') or hasRole('MANAGER')")
    public ResponseEntity<ResolveTagsResponse> resolve(@Valid @RequestBody ResolveTagsRequest request) {
        ResolveTagsResponse response = tagService.resolveTags(request.tagNames());
        return ResponseEntity.ok(response);
    }

    // Response record for paged tag search
    record PagedTagResponse(
            List<TagResponse> data,
            int page,
            int limit,
            long total,
            int totalPages
    ) {}
}
