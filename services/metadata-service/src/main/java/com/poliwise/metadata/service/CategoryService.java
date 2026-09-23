package com.poliwise.metadata.service;

import com.poliwise.metadata.dto.CreateCategoryRequest;
import com.poliwise.metadata.dto.UpdateCategoryRequest;
import com.poliwise.metadata.dto.CategoryResponse;
import com.poliwise.metadata.entity.Category;
import com.poliwise.metadata.exception.ResourceNotFoundException;
import com.poliwise.metadata.exception.DuplicateResourceException;
import com.poliwise.metadata.repository.CategoryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class CategoryService {

    private static final Logger log = LoggerFactory.getLogger(CategoryService.class);

    private final CategoryRepository categoryRepository;

    public CategoryService(CategoryRepository categoryRepository) {
        this.categoryRepository = categoryRepository;
    }

    @Transactional
    public CategoryResponse create(CreateCategoryRequest request) {
        String slug = generateSlug(request.name());

        if (categoryRepository.findBySlug(slug).isPresent()) {
            throw new DuplicateResourceException("Category already exists with name: " + request.name());
        }

        // Validate parent exists if provided
        if (request.parentId() != null) {
            categoryRepository.findById(request.parentId())
                    .orElseThrow(() -> new ResourceNotFoundException("Parent category not found: " + request.parentId()));
        }

        OffsetDateTime now = OffsetDateTime.now();
        Category category = Category.builder()
                .id(UUID.randomUUID())
                .name(request.name())
                .slug(slug)
                .description(request.description())
                .parentId(request.parentId())
                .icon(request.icon())
                .displayOrder(request.displayOrder() != null ? request.displayOrder() : getNextDisplayOrder(request.parentId()))
                .isActive(true)
                .createdAt(now)
                .updatedAt(now)
                .build();

        Category saved = categoryRepository.save(category);
        log.info("Created category: id={}, name={}, parentId={}", saved.getId(), saved.getName(), saved.getParentId());
        return toResponse(saved);
    }

    public List<CategoryResponse> getAll() {
        return categoryRepository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public List<CategoryResponse> getActive() {
        return categoryRepository.findByIsActiveTrueOrderByDisplayOrderAscNameAsc().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public List<CategoryResponse> getActiveByParent(UUID parentId) {
        if (parentId == null) {
            // Get root categories (no parent)
            return categoryRepository.findByIsActiveTrueOrderByDisplayOrderAscNameAsc().stream()
                    .filter(c -> c.getParentId() == null)
                    .map(this::toResponse)
                    .collect(Collectors.toList());
        }
        return categoryRepository.findByParentIdAndIsActiveTrueOrderByDisplayOrderAscNameAsc(parentId).stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    public CategoryResponse getById(UUID id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + id));
        return toResponse(category);
    }

    public CategoryResponse getBySlug(String slug) {
        Category category = categoryRepository.findBySlug(slug)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found with slug: " + slug));
        return toResponse(category);
    }

    public UUID resolveSlug(String slug) {
        if (slug == null || slug.isBlank()) return null;
        return categoryRepository.findBySlug(slug).map(Category::getId).orElse(null);
    }

    @Transactional
    public CategoryResponse update(UUID id, UpdateCategoryRequest request) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + id));

        // Prevent circular reference in parent hierarchy
        if (request.parentId() != null && request.parentId().equals(id)) {
            throw new IllegalArgumentException("Category cannot be its own parent");
        }

        // Validate new parent exists if provided
        if (request.parentId() != null) {
            categoryRepository.findById(request.parentId())
                    .orElseThrow(() -> new ResourceNotFoundException("Parent category not found: " + request.parentId()));
        }

        String newSlug = generateSlug(request.name());
        if (!newSlug.equals(category.getSlug())) {
            categoryRepository.findBySlug(newSlug).ifPresent(existing -> {
                throw new DuplicateResourceException("Category already exists with name: " + request.name());
            });
        }

        category.setName(request.name());
        category.setSlug(newSlug);
        category.setDescription(request.description());
        category.setParentId(request.parentId());
        if (request.icon() != null) {
            category.setIcon(request.icon());
        }
        if (request.displayOrder() != null) {
            category.setDisplayOrder(request.displayOrder());
        }
        category.setUpdatedAt(OffsetDateTime.now());

        Category saved = categoryRepository.save(category);
        log.info("Updated category: id={}, name={}", id, saved.getName());
        return toResponse(saved);
    }

    @Transactional
    public void delete(UUID id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + id));

        // Check if category has children
        List<Category> children = categoryRepository.findByParentIdAndIsActiveTrueOrderByDisplayOrderAscNameAsc(id);
        if (!children.isEmpty()) {
            // Option 1: Prevent deletion if has children
            // throw new IllegalStateException("Cannot delete category with children. Delete children first.");
            
            // Option 2: Move children to root level (cascade)
            for (Category child : children) {
                child.setParentId(null);
                categoryRepository.save(child);
            }
            log.info("Moved {} children of category {} to root level", children.size(), id);
        }

        category.setIsActive(false);
        category.setUpdatedAt(OffsetDateTime.now());
        categoryRepository.save(category);

        log.info("Deactivated category: id={}, name={}", id, category.getName());
    }

    /**
     * Get full category tree (hierarchical structure)
     */
    public List<CategoryTreeNode> getCategoryTree() {
        List<Category> allCategories = categoryRepository.findAll();
        return buildTree(null, allCategories);
    }

    /**
     * Get active category tree (hierarchical structure)
     */
    public List<CategoryTreeNode> getActiveCategoryTree() {
        List<Category> activeCategories = categoryRepository.findByIsActiveTrueOrderByDisplayOrderAscNameAsc();
        return buildTree(null, activeCategories);
    }

    private List<CategoryTreeNode> buildTree(UUID parentId, List<Category> categories) {
        return categories.stream()
                .filter(c -> Objects.equals(c.getParentId(), parentId))
                .sorted(Comparator.comparing(Category::getDisplayOrder, Comparator.nullsLast(Comparator.naturalOrder()))
                        .thenComparing(Category::getName))
                .map(c -> new CategoryTreeNode(
                        c.getId(),
                        c.getName(),
                        c.getSlug(),
                        c.getDescription(),
                        c.getParentId(),
                        c.getIcon(),
                        c.getDisplayOrder(),
                        c.getIsActive(),
                        c.getCreatedAt(),
                        c.getUpdatedAt(),
                        buildTree(c.getId(), categories)
                ))
                .collect(Collectors.toList());
    }

    private int getNextDisplayOrder(UUID parentId) {
        return categoryRepository.findByParentIdAndIsActiveTrueOrderByDisplayOrderAscNameAsc(parentId)
                .stream()
                .mapToInt(c -> c.getDisplayOrder() != null ? c.getDisplayOrder() : 0)
                .max()
                .orElse(0) + 1;
    }

    private String generateSlug(String name) {
        if (name == null) return "";
        return name.trim().toLowerCase()
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
    }

    private CategoryResponse toResponse(Category category) {
        return new CategoryResponse(
                category.getId(),
                category.getName(),
                category.getSlug(),
                category.getDescription(),
                category.getParentId(),
                category.getIcon(),
                category.getDisplayOrder(),
                category.getIsActive(),
                category.getCreatedAt(),
                category.getUpdatedAt()
        );
    }

    // Inner record for tree structure
    public record CategoryTreeNode(
            UUID id,
            String name,
            String slug,
            String description,
            UUID parentId,
            String icon,
            Integer displayOrder,
            Boolean isActive,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt,
            List<CategoryTreeNode> children
    ) {}
}
