package com.poliwise.feedback.service;

import com.poliwise.feedback.dto.request.AnalyticsRequest;
import com.poliwise.feedback.dto.response.*;
import com.poliwise.feedback.enums.FeedbackType;
import com.poliwise.feedback.repository.*;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@Transactional
public class AnalyticsService {

    private final DailyAggregateRepository dailyAggregateRepository;
    private final FeedbackRepository feedbackRepository;
    private final PopularQuestionRepository popularQuestionRepository;
    private final DocumentPopularityRepository documentPopularityRepository;
    private final DepartmentDailyStatRepository departmentDailyStatRepository;
    private final UsageStatRepository usageStatRepository;

    public AnalyticsService(
            DailyAggregateRepository dailyAggregateRepository,
            FeedbackRepository feedbackRepository,
            PopularQuestionRepository popularQuestionRepository,
            DocumentPopularityRepository documentPopularityRepository,
            DepartmentDailyStatRepository departmentDailyStatRepository,
            UsageStatRepository usageStatRepository) {
        this.dailyAggregateRepository = dailyAggregateRepository;
        this.feedbackRepository = feedbackRepository;
        this.popularQuestionRepository = popularQuestionRepository;
        this.documentPopularityRepository = documentPopularityRepository;
        this.departmentDailyStatRepository = departmentDailyStatRepository;
        this.usageStatRepository = usageStatRepository;
    }

    public AnalyticsSummaryResponse getSummary(AnalyticsRequest request) {
        LocalDate from = request.fromDate() != null ? request.fromDate() : LocalDate.now().minusDays(30);
        LocalDate to = request.toDate() != null ? request.toDate() : LocalDate.now();
        Long totalQuestions = dailyAggregateRepository.sumTotalQuestions(from, to);
        Long totalLikes = dailyAggregateRepository.sumTotalLikes(from, to);
        Long totalDislikes = dailyAggregateRepository.sumTotalDislikes(from, to);
        long likes = totalLikes != null ? totalLikes : 0;
        long dislikes = totalDislikes != null ? totalDislikes : 0;
        long totalFeedbacks = likes + dislikes;
        BigDecimal satisfactionRate = BigDecimal.ZERO;
        if (totalFeedbacks > 0) {
            satisfactionRate = BigDecimal.valueOf(likes).divide(BigDecimal.valueOf(totalFeedbacks), 4, RoundingMode.HALF_UP);
        }
        return new AnalyticsSummaryResponse(
                totalQuestions != null ? totalQuestions : 0, totalFeedbacks, likes, dislikes,
                satisfactionRate, null, List.of(), from, to
        );
    }

    public List<PopularQuestionResponse> getTopQuestions(int limit, LocalDate from, LocalDate to) {
        Pageable pageable = PageRequest.of(0, limit);
        return popularQuestionRepository.findTop10ByOrderByAskCountDesc(pageable).stream()
                .map(PopularQuestionResponse::fromEntity).toList();
    }

    public List<DocumentPopularityResponse> getTopDocuments(int limit) {
        Pageable pageable = PageRequest.of(0, limit);
        return documentPopularityRepository.findTop10ByOrderByTotalCitationsDesc(pageable).stream()
                .map(DocumentPopularityResponse::fromEntity).toList();
    }

    public DepartmentStatsResponse getDepartmentStats(UUID departmentId, LocalDate date) {
        return departmentDailyStatRepository.findByDateAndDepartmentId(date, departmentId)
                .map(deptStat -> {
                    BigDecimal rate = BigDecimal.ZERO;
                    long total = deptStat.getLikes() + deptStat.getDislikes();
                    if (total > 0) {
                        rate = BigDecimal.valueOf(deptStat.getLikes()).divide(BigDecimal.valueOf(total), 4, RoundingMode.HALF_UP);
                    }
                    return new DepartmentStatsResponse(deptStat.getDepartmentId(), null, deptStat.getTotalQuestions(),
                            deptStat.getUniqueUsers(), deptStat.getLikes(), deptStat.getDislikes(), rate);
                })
                .orElse(new DepartmentStatsResponse(departmentId, null, 0, 0, 0, 0, BigDecimal.ZERO));
    }

    public List<TrendResponse> getTrends(int days) {
        LocalDate to = LocalDate.now();
        LocalDate from = to.minusDays(days);
        return dailyAggregateRepository.findByDateBetweenOrderByDateDesc(from, to).stream()
                .map(agg -> new TrendResponse(agg.getDate(), agg.getTotalQuestions(),
                        agg.getTotalLikes() + agg.getTotalDislikes(), agg.getAvgResponseTimeMs(),
                        agg.getUniqueActiveUsers(), agg.getTotalLikes(), agg.getTotalDislikes(), List.of()))
                .toList();
    }

    public Map<String, Object> getDocumentViewStats(int days) {
        LocalDate to = LocalDate.now();
        LocalDate from = to.minusDays(days);
        Instant fromInstant = from.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant toInstant = to.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);

        Long viewCount = usageStatRepository.countByCreatedAtBetween(fromInstant, toInstant);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("periodDays", days);
        result.put("periodFrom", from.toString());
        result.put("periodTo", to.toString());
        result.put("viewCount", viewCount != null ? viewCount : 0);
        return result;
    }
}
