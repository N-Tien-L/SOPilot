package com.poliwise.feedback.service;

import com.poliwise.feedback.dto.response.*;
import com.poliwise.feedback.entity.DailyAggregate;
import com.poliwise.feedback.entity.PopularQuestion;
import com.poliwise.feedback.entity.UnansweredQuestion;
import com.poliwise.feedback.enums.UnansweredStatus;
import com.poliwise.feedback.feign.KnowledgeServiceClient;
import com.poliwise.feedback.feign.UserServiceClient;
import com.poliwise.feedback.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class DashboardService {

    private static final Logger log = LoggerFactory.getLogger(DashboardService.class);

    private final DailyAggregateRepository dailyAggregateRepository;
    private final FeedbackRepository feedbackRepository;
    private final UnansweredQuestionRepository unansweredQuestionRepository;
    private final PopularQuestionRepository popularQuestionRepository;
    private final DocumentPopularityRepository documentPopularityRepository;
    private final UsageStatRepository usageStatRepository;
    private final UserServiceClient userServiceClient;
    private final KnowledgeServiceClient knowledgeServiceClient;

    public DashboardService(
            DailyAggregateRepository dailyAggregateRepository,
            FeedbackRepository feedbackRepository,
            UnansweredQuestionRepository unansweredQuestionRepository,
            PopularQuestionRepository popularQuestionRepository,
            DocumentPopularityRepository documentPopularityRepository,
            UsageStatRepository usageStatRepository,
            UserServiceClient userServiceClient,
            KnowledgeServiceClient knowledgeServiceClient) {
        this.dailyAggregateRepository = dailyAggregateRepository;
        this.feedbackRepository = feedbackRepository;
        this.unansweredQuestionRepository = unansweredQuestionRepository;
        this.popularQuestionRepository = popularQuestionRepository;
        this.documentPopularityRepository = documentPopularityRepository;
        this.usageStatRepository = usageStatRepository;
        this.userServiceClient = userServiceClient;
        this.knowledgeServiceClient = knowledgeServiceClient;
    }

    public DashboardOverviewResponse getOverview() {
        LocalDate today = LocalDate.now();
        LocalDate weekAgo = today.minusDays(7);
        Instant todayStart = today.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant todayEnd = today.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant weekStart = weekAgo.atStartOfDay().toInstant(ZoneOffset.UTC);

        DailyAggregate todayAgg = dailyAggregateRepository.findByDate(today).orElse(null);
        long todayQuestions = todayAgg != null ? todayAgg.getTotalQuestions() : 0;

        long weekQuestions = 0;
        for (LocalDate d = weekAgo; !d.isAfter(today); d = d.plusDays(1)) {
            DailyAggregate agg = dailyAggregateRepository.findByDate(d).orElse(null);
            if (agg != null) weekQuestions += agg.getTotalQuestions();
        }

        Long distinctUsers = usageStatRepository.countDistinctUsers(weekStart, todayEnd);
        long activeUsersToday = distinctUsers != null ? distinctUsers : 0;

        long totalLikes = feedbackRepository.countByType(com.poliwise.feedback.enums.FeedbackType.LIKE);
        long totalDislikes = feedbackRepository.countByType(com.poliwise.feedback.enums.FeedbackType.DISLIKE);
        BigDecimal satisfactionRate = BigDecimal.ZERO;
        if (totalLikes + totalDislikes > 0) {
            satisfactionRate = BigDecimal.valueOf(totalLikes)
                    .divide(BigDecimal.valueOf(totalLikes + totalDislikes), 4, RoundingMode.HALF_UP);
        }

        long unansweredCount = unansweredQuestionRepository.countByStatusIn(
                List.of(UnansweredStatus.PENDING, UnansweredStatus.REVIEWING));

        List<PopularQuestionResponse> topQuestions = popularQuestionRepository
                .findTop10ByOrderByAskCountDesc(PageRequest.of(0, 5))
                .stream().map(PopularQuestionResponse::fromEntity).toList();

        List<DocumentPopularityResponse> topDocuments = documentPopularityRepository
                .findTop10ByOrderByTotalCitationsDesc(PageRequest.of(0, 5))
                .stream().map(DocumentPopularityResponse::fromEntity).toList();

        long monthQuestions = 0;
        LocalDate monthAgo = today.minusDays(30);
        for (LocalDate d = monthAgo; !d.isAfter(today); d = d.plusDays(1)) {
            DailyAggregate agg = dailyAggregateRepository.findByDate(d).orElse(null);
            if (agg != null) monthQuestions += agg.getTotalQuestions();
        }

        long totalQuestions = monthQuestions;

        long totalUsers = 0, activeUsers = 0, totalDocuments = 0, activeDocuments = 0;
        try {
            var userStats = userServiceClient.getStats();
            totalUsers = userStats.totalUsers();
            activeUsers = userStats.activeUsers();
        } catch (Exception e) {
            log.warn("Failed to fetch user stats: {}", e.getMessage());
        }
        try {
            var docStats = knowledgeServiceClient.getStats();
            totalDocuments = docStats.totalDocuments();
            activeDocuments = docStats.activeDocuments();
        } catch (Exception e) {
            log.warn("Failed to fetch document stats: {}", e.getMessage());
        }

        return new DashboardOverviewResponse(todayQuestions, weekQuestions, monthQuestions, totalLikes + totalDislikes,
                satisfactionRate, activeUsersToday, totalUsers, activeUsers, totalDocuments, activeDocuments,
                unansweredCount, topQuestions, topDocuments);
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

    public Page<UnansweredQuestionResponse> getUnansweredQuestions(Pageable pageable, String status) {
        String normalizedStatus = status != null ? status.trim().toUpperCase(Locale.ROOT) : null;
        UnansweredStatus enumStatus = null;
        if (normalizedStatus != null && !normalizedStatus.isBlank()) {
            try {
                enumStatus = UnansweredStatus.valueOf(normalizedStatus);
            } catch (IllegalArgumentException e) {
                // Invalid status, will return empty or all
            }
        }
        Page<UnansweredQuestion> questions = enumStatus != null
                ? unansweredQuestionRepository.findByStatus(enumStatus, pageable)
                : unansweredQuestionRepository.findAll(pageable);
        return questions.map(this::toResponse);
    }

    @Transactional
    public UnansweredQuestionResponse resolveUnanswered(UUID id, UUID resolvedBy, String answer) {
        UnansweredQuestion question = unansweredQuestionRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Unanswered question not found: " + id));
        Instant now = Instant.now();
        question.setStatus(UnansweredStatus.ANSWERED);
        question.setResolved(true);
        question.setResolvedBy(resolvedBy);
        question.setResolvedAt(now);
        question.setResolutionNotes(answer);
        return toResponse(unansweredQuestionRepository.save(question));
    }

    @Transactional
    public UnansweredQuestionResponse rejectUnanswered(UUID id, UUID resolvedBy) {
        UnansweredQuestion question = unansweredQuestionRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Unanswered question not found: " + id));
        Instant now = Instant.now();
        question.setStatus(UnansweredStatus.REJECTED);
        question.setResolved(true);
        question.setResolvedBy(resolvedBy);
        question.setResolvedAt(now);
        return toResponse(unansweredQuestionRepository.save(question));
    }

    private UnansweredQuestionResponse toResponse(UnansweredQuestion uq) {
        return new UnansweredQuestionResponse(
                uq.getId(),
                uq.getQuestion(),
                uq.getUserId(),
                uq.getUserDepartmentId(),
                uq.getCategory(),
                uq.getPriority() != null ? uq.getPriority().name() : null,
                uq.getStatus() != null ? uq.getStatus().name() : (Boolean.TRUE.equals(uq.getResolved()) ? "ANSWERED" : "PENDING"),
                1L,
                uq.getResolved(),
                uq.getCreatedAt(),
                uq.getCreatedAt(),
                uq.getCreatedAt(),
                uq.getResolvedAt(),
                uq.getResolutionNotes()
        );
    }
}
