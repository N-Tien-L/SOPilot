package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.Feedback;
import com.poliwise.feedback.enums.FeedbackType;
import org.springframework.data.domain.Page;
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
public interface FeedbackRepository extends JpaRepository<Feedback, UUID> {

    List<Feedback> findByConversationId(UUID conversationId);

    Page<Feedback> findByUserId(UUID userId, Pageable pageable);

    List<Feedback> findByUserIdAndConversationId(UUID userId, UUID conversationId);

    Optional<Feedback> findByUserIdAndMessageId(UUID userId, UUID messageId);

    Page<Feedback> findByCreatedAtBetween(Instant start, Instant end, Pageable pageable);

    long countByType(FeedbackType type);

    long countByCreatedAtBetween(Instant from, Instant to);

    @Query("SELECT f.type, COUNT(f) FROM Feedback f WHERE f.createdAt BETWEEN :from AND :to GROUP BY f.type")
    List<Object[]> countByTypeGrouped(@Param("from") Instant from, @Param("to") Instant to);

    boolean existsByUserIdAndMessageId(UUID userId, UUID messageId);
}
