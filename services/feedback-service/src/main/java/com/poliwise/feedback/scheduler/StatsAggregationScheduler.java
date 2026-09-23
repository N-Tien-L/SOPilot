package com.poliwise.feedback.scheduler;

import com.poliwise.feedback.entity.DailyAggregate;
import com.poliwise.feedback.entity.DepartmentDailyStat;
import com.poliwise.feedback.entity.HourlyAggregate;
import com.poliwise.feedback.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.temporal.ChronoUnit;

@Component
public class StatsAggregationScheduler {

    private static final Logger log = LoggerFactory.getLogger(StatsAggregationScheduler.class);

    private final UsageStatRepository usageStatRepository;
    private final HourlyAggregateRepository hourlyAggregateRepository;
    private final DailyAggregateRepository dailyAggregateRepository;
    private final DepartmentDailyStatRepository departmentDailyStatRepository;

    @Value("${poliwise.cleanup.usage-stats-retention-days:7}")
    private int usageStatsRetentionDays;

    @Value("${poliwise.cleanup.hourly-aggregate-retention-days:30}")
    private int hourlyAggregateRetentionDays;

    public StatsAggregationScheduler(
            UsageStatRepository usageStatRepository,
            HourlyAggregateRepository hourlyAggregateRepository,
            DailyAggregateRepository dailyAggregateRepository,
            DepartmentDailyStatRepository departmentDailyStatRepository) {
        this.usageStatRepository = usageStatRepository;
        this.hourlyAggregateRepository = hourlyAggregateRepository;
        this.dailyAggregateRepository = dailyAggregateRepository;
        this.departmentDailyStatRepository = departmentDailyStatRepository;
    }

    @Scheduled(cron = "0 5 * * * *")
    @Transactional
    public void aggregateHourlyStats() {
        ZonedDateTime now = ZonedDateTime.now(ZoneOffset.UTC);
        ZonedDateTime hourStart = now.truncatedTo(ChronoUnit.HOURS).minusHours(1);
        ZonedDateTime hourEnd = hourStart.plusHours(1);

        Instant from = hourStart.toInstant();
        Instant to = hourEnd.toInstant();

        Long totalQuestions = hourlyAggregateRepository.sumTotalQuestions(from, to);
        Long totalLikes = hourlyAggregateRepository.sumLikes(from, to);
        Long totalDislikes = hourlyAggregateRepository.sumDislikes(from, to);

        Long usageCount = usageStatRepository.countByCreatedAtBetween(from, to);
        Long distinctUsers = usageStatRepository.countDistinctUsers(from, to);
        Double avgResponse = usageStatRepository.avgResponseTime(from, to);

        if (totalQuestions == null) totalQuestions = 0L;
        if (totalLikes == null) totalLikes = 0L;
        if (totalDislikes == null) totalDislikes = 0L;
        if (usageCount == null) usageCount = 0L;
        if (distinctUsers == null) distinctUsers = 0L;

        HourlyAggregate hourly = hourlyAggregateRepository.findByDatetime(hourStart.toInstant())
                .orElse(HourlyAggregate.builder().datetime(hourStart.toInstant()).hour(hourStart.getHour()).build());

        hourly.setTotalQuestions(totalQuestions.intValue());
        hourly.setTotalRequests(usageCount.intValue());
        hourly.setUniqueUsers(distinctUsers.intValue());
        hourly.setLikes(totalLikes.intValue());
        hourly.setDislikes(totalDislikes.intValue());
        hourly.setAvgResponseTimeMs(avgResponse != null ? avgResponse.intValue() : null);
        hourly.setComputedAt(Instant.now());
        hourlyAggregateRepository.save(hourly);

        log.info("Hourly aggregation completed for {}: {} questions, {} likes, {} dislikes",
                hourStart, totalQuestions, totalLikes, totalDislikes);
    }

    @Scheduled(cron = "0 10 0 * * *")
    @Transactional
    public void aggregateDailyStats() {
        LocalDate yesterday = LocalDate.now(ZoneOffset.UTC).minusDays(1);
        LocalDate today = LocalDate.now(ZoneOffset.UTC);

        Instant dayStart = yesterday.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant dayEnd = today.atStartOfDay().toInstant(ZoneOffset.UTC);

        Long totalQuestions = hourlyAggregateRepository.sumTotalQuestions(dayStart, dayEnd);
        Long totalLikes = hourlyAggregateRepository.sumLikes(dayStart, dayEnd);
        Long totalDislikes = hourlyAggregateRepository.sumDislikes(dayStart, dayEnd);
        Long distinctUsers = usageStatRepository.countDistinctUsers(dayStart, dayEnd);

        DailyAggregate daily = dailyAggregateRepository.findByDate(yesterday)
                .orElse(DailyAggregate.builder().date(yesterday).build());

        daily.setTotalQuestions(totalQuestions != null ? totalQuestions.intValue() : 0);
        daily.setTotalLikes(totalLikes != null ? totalLikes.intValue() : 0);
        daily.setTotalDislikes(totalDislikes != null ? totalDislikes.intValue() : 0);
        daily.setUniqueActiveUsers(distinctUsers != null ? distinctUsers.intValue() : 0);
        daily.setUniqueUsersAsked(distinctUsers != null ? distinctUsers.intValue() : 0);
        daily.setTotalRequests(daily.getTotalQuestions());
        daily.setComputedAt(Instant.now());
        dailyAggregateRepository.save(daily);

        cleanupOldUsageStats();
        cleanupOldHourlyAggregates();

        log.info("Daily aggregation completed for {}: {} questions", yesterday, totalQuestions);
    }

    private void cleanupOldUsageStats() {
        Instant cutoff = Instant.now().minusSeconds((long) usageStatsRetentionDays * 24 * 60 * 60);
        usageStatRepository.deleteByCreatedAtBefore(cutoff);
        log.info("Cleaned up usage stats older than {} days", usageStatsRetentionDays);
    }

    private void cleanupOldHourlyAggregates() {
        Instant cutoff = Instant.now().minusSeconds((long) hourlyAggregateRetentionDays * 24 * 60 * 60);
        hourlyAggregateRepository.deleteByDatetimeBefore(cutoff);
        log.info("Cleaned up hourly aggregates older than {} days", hourlyAggregateRetentionDays);
    }
}
