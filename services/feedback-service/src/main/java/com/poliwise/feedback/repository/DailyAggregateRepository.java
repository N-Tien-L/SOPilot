package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.DailyAggregate;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DailyAggregateRepository extends JpaRepository<DailyAggregate, UUID> {

    Optional<DailyAggregate> findByDate(LocalDate date);

    List<DailyAggregate> findByDateBetweenOrderByDateDesc(LocalDate from, LocalDate to);

    @Query("SELECT SUM(d.totalQuestions) FROM DailyAggregate d WHERE d.date BETWEEN :from AND :to")
    Long sumTotalQuestions(@Param("from") LocalDate from, @Param("to") LocalDate to);

    @Query("SELECT SUM(d.totalLikes) FROM DailyAggregate d WHERE d.date BETWEEN :from AND :to")
    Long sumTotalLikes(@Param("from") LocalDate from, @Param("to") LocalDate to);

    @Query("SELECT SUM(d.totalDislikes) FROM DailyAggregate d WHERE d.date BETWEEN :from AND :to")
    Long sumTotalDislikes(@Param("from") LocalDate from, @Param("to") LocalDate to);
}
