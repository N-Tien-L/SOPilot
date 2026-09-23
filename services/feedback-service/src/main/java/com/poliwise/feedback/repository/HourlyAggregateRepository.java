package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.HourlyAggregate;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface HourlyAggregateRepository extends JpaRepository<HourlyAggregate, UUID> {

    Optional<HourlyAggregate> findByDatetime(Instant datetime);

    List<HourlyAggregate> findByDatetimeBetweenOrderByDatetimeDesc(Instant from, Instant to);

    @Query("SELECT SUM(h.totalQuestions) FROM HourlyAggregate h WHERE h.datetime BETWEEN :from AND :to")
    Long sumTotalQuestions(@Param("from") Instant from, @Param("to") Instant to);

    @Query("SELECT SUM(h.likes) FROM HourlyAggregate h WHERE h.datetime BETWEEN :from AND :to")
    Long sumLikes(@Param("from") Instant from, @Param("to") Instant to);

    @Query("SELECT SUM(h.dislikes) FROM HourlyAggregate h WHERE h.datetime BETWEEN :from AND :to")
    Long sumDislikes(@Param("from") Instant from, @Param("to") Instant to);

    void deleteByDatetimeBefore(Instant before);
}
