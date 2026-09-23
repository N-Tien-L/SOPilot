package com.poliwise.metadata.controller;

import com.poliwise.metadata.dto.*;
import com.poliwise.metadata.security.SecurityUtils;
import com.poliwise.metadata.service.CategoryService;
import com.poliwise.metadata.service.CategoryService.CategoryTreeNode;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/categories")
public class CategoryController {

    private final CategoryService categoryService;

    public CategoryController(CategoryService categoryService) {
        this.categoryService = categoryService;
    }

    // ===== CRUD Operations =====

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<CategoryResponse> create(@Valid @RequestBody CreateCategoryRequest request) {
        CategoryResponse response = categoryService.create(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping
    public ResponseEntity<List<CategoryResponse>> getAll() {
        List<CategoryResponse> categories = categoryService.getAll();
        return ResponseEntity.ok(categories);
    }

    @GetMapping("/active")
    public ResponseEntity<List<CategoryResponse>> getActive() {
        List<CategoryResponse> categories = categoryService.getActive();
        return ResponseEntity.ok(categories);
    }

    @GetMapping("/active/tree")
    public ResponseEntity<List<CategoryTreeNode>> getActiveTree() {
        List<CategoryTreeNode> tree = categoryService.getActiveCategoryTree();
        return ResponseEntity.ok(tree);
    }

    @GetMapping("/tree")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<List<CategoryTreeNode>> getTree() {
        List<CategoryTreeNode> tree = categoryService.getCategoryTree();
        return ResponseEntity.ok(tree);
    }

    @GetMapping("/active/children")
    public ResponseEntity<List<CategoryResponse>> getActiveByParent(
            @RequestParam(required = false) UUID parentId) {
        List<CategoryResponse> children = categoryService.getActiveByParent(parentId);
        return ResponseEntity.ok(children);
    }

    @GetMapping("/active/children/{parentId}")
    public ResponseEntity<List<CategoryResponse>> getActiveChildren(@PathVariable UUID parentId) {
        List<CategoryResponse> children = categoryService.getActiveByParent(parentId);
        return ResponseEntity.ok(children);
    }

    @GetMapping("/{id}")
    public ResponseEntity<CategoryResponse> get(@PathVariable UUID id) {
        CategoryResponse response = categoryService.getById(id);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/slug/{slug}")
    public ResponseEntity<CategoryResponse> getBySlug(@PathVariable String slug) {
        CategoryResponse response = categoryService.getBySlug(slug);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/resolve/{slug}")
    public ResponseEntity<ResolveSlugResponse> resolveSlug(@PathVariable String slug) {
        UUID categoryId = categoryService.resolveSlug(slug);
        return ResponseEntity.ok(new ResolveSlugResponse(categoryId));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<CategoryResponse> update(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateCategoryRequest request) {
        CategoryResponse response = categoryService.update(id, request);
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        categoryService.delete(id);
        return ResponseEntity.noContent().build();
    }

    // Response record for slug resolution
    record ResolveSlugResponse(UUID categoryId) {}
}
