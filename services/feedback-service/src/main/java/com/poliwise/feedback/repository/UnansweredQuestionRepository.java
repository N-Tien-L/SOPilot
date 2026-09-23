package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.UnansweredQuestion;
import com.poliwise.feedback.enums.PriorityLevel;
import com.poliwise.feedback.enums.UnansweredStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface UnansweredQuestionRepository extends JpaRepository<UnansweredQuestion, UUID> {

    Page<UnansweredQuestion> findByResolved(Boolean resolved, Pageable pageable);

    Page<UnansweredQuestion> findByStatus(UnansweredStatus status, Pageable pageable);

    Page<UnansweredQuestion> findByUserId(UUID userId, Pageable pageable);

    List<UnansweredQuestion> findByPriorityOrderByCreatedAtDesc(PriorityLevel priority);

    long countByResolved(Boolean resolved);

    long countByStatusIn(List<UnansweredStatus> statuses);

    @Query("SELECT COUNT(u) FROM UnansweredQuestion u WHERE u.resolved = false AND u.createdAt BETWEEN :from AND :to")
    Long countUnansweredBetween(@Param("from") Instant from, @Param("to") Instant to);

    @Query("SELECT COUNT(u) FROM UnansweredQuestion u WHERE u.createdAt < :before")
    long countByCreatedAtBefore(@Param("before") Instant before);

    @Query("SELECT u FROM UnansweredQuestion u WHERE u.resolved = true AND u.resolvedAt < :before")
    List<UnansweredQuestion> findResolvedBefore(@Param("before") Instant before);
}
