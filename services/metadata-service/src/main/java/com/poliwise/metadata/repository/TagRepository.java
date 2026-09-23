package com.poliwise.metadata.repository;

import com.poliwise.metadata.entity.Tag;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface TagRepository extends JpaRepository<Tag, UUID>, JpaSpecificationExecutor<Tag> {

    Optional<Tag> findBySlugIgnoreCase(String slug);

    Optional<Tag> findByNameIgnoreCase(String name);

    Optional<Tag> findBySlug(String slug);

    boolean existsBySlugIgnoreCase(String slug);

    boolean existsByNameIgnoreCase(String name);
    
    List<Tag> findByNameInIgnoreCase(java.util.Collection<String> names);

    List<Tag> findTopByOrderByUsageCountDesc();

    @Query("""
            select t
            from Tag t
            where lower(t.name) like lower(concat('%', :keyword, '%'))
            order by coalesce(t.usageCount, 0) desc, t.name asc
            """)
    Page<Tag> searchByName(@Param("keyword") String keyword, Pageable pageable);
}
