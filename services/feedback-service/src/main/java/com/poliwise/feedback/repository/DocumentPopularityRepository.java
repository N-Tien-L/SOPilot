package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.DocumentPopularity;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DocumentPopularityRepository extends JpaRepository<DocumentPopularity, UUID> {

    Optional<DocumentPopularity> findByDocumentId(UUID documentId);

    List<DocumentPopularity> findTop10ByOrderByTotalCitationsDesc(Pageable pageable);

    @Query("SELECT SUM(d.totalCitations) FROM DocumentPopularity d WHERE d.lastCitedAt BETWEEN :from AND :to")
    Long sumTotalCitationsBetween(@Param("from") Instant from, @Param("to") Instant to);

    long countByTotalCitationsGreaterThan(Integer count);
}
