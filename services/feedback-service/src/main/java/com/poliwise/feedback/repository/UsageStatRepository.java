package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.UsageStat;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface UsageStatRepository extends JpaRepository<UsageStat, UUID> {

    List<UsageStat> findByCreatedAtBetween(Instant from, Instant to);

    long countByServiceNameAndIsError(String serviceName, Boolean isError);

    @Query("SELECT SUM(u.responseTimeMs) FROM UsageStat u WHERE u.serviceName = :serviceName AND u.createdAt BETWEEN :from AND :to")
    Long sumResponseTimeByService(@Param("serviceName") String serviceName,
                                  @Param("from") Instant from,
                                  @Param("to") Instant to);

    @Query("SELECT AVG(u.responseTimeMs) FROM UsageStat u WHERE u.createdAt BETWEEN :from AND :to")
    Double avgResponseTime(@Param("from") Instant from, @Param("to") Instant to);

    @Query("SELECT COUNT(DISTINCT u.userId) FROM UsageStat u WHERE u.createdAt BETWEEN :from AND :to")
    Long countDistinctUsers(@Param("from") Instant from, @Param("to") Instant to);

    @Query("SELECT COUNT(u) FROM UsageStat u WHERE u.createdAt BETWEEN :from AND :to")
    Long countByCreatedAtBetween(@Param("from") Instant from, @Param("to") Instant to);

    void deleteByCreatedAtBefore(Instant before);

    long countByCreatedAtBefore(Instant before);
}
