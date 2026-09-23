package com.poliwise.metadata.repository;

import com.poliwise.metadata.entity.Category;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface CategoryRepository
        extends JpaRepository<Category, UUID>, JpaSpecificationExecutor<Category> {

    Optional<Category> findBySlugIgnoreCase(String slug);

    Optional<Category> findBySlug(String slug);

    boolean existsBySlugIgnoreCase(String slug);

    List<Category> findByIsActiveTrueOrderByDisplayOrderAscNameAsc();

    List<Category> findByParentIdAndIsActiveTrueOrderByDisplayOrderAscNameAsc(UUID parentId);
}
