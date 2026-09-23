package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.PopularQuestion;
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
public interface PopularQuestionRepository extends JpaRepository<PopularQuestion, UUID> {

    Optional<PopularQuestion> findByQuestionNormalized(String questionNormalized);

    List<PopularQuestion> findTop10ByOrderByAskCountDesc(Pageable pageable);

    List<PopularQuestion> findByAskCountGreaterThanOrderByAskCountDesc(Integer count, Pageable pageable);

    @Query("SELECT COUNT(p) FROM PopularQuestion p WHERE p.lastAskedAt < :before")
    long countByLastAskedAtBefore(@Param("before") Instant before);

    @Query("SELECT SUM(p.askCount) FROM PopularQuestion p WHERE p.lastAskedAt BETWEEN :from AND :to")
    Long sumAskCountBetween(@Param("from") Instant from, @Param("to") Instant to);
}
