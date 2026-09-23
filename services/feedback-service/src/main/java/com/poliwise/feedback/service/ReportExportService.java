package com.poliwise.feedback.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.poliwise.feedback.dto.request.ReportExportRequest;
import com.poliwise.feedback.dto.response.ReportDownload;
import com.poliwise.feedback.dto.response.ReportExportResponse;
import com.poliwise.feedback.entity.*;
import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.enums.ExportStatus;
import com.poliwise.feedback.enums.FeedbackType;
import com.poliwise.feedback.exception.ReportNotFoundException;
import com.poliwise.feedback.exception.UnauthorizedFeedbackAccessException;
import com.poliwise.feedback.feign.UserServiceClient;
import com.poliwise.feedback.feign.UserServiceReportClient;
import com.poliwise.feedback.feign.dto.DepartmentListResponse;
import com.poliwise.feedback.feign.dto.UserStatsResponse;
import com.poliwise.feedback.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import com.poliwise.feedback.config.RabbitMQConfig;
import io.minio.MinioClient;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.PutObjectArgs;
import io.minio.GetObjectArgs;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
@Transactional
public class ReportExportService {

    private static final Logger log = LoggerFactory.getLogger(ReportExportService.class);
    private static final DateTimeFormatter DT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final byte[] UTF8_BOM = new byte[]{(byte) 0xEF, (byte) 0xBB, (byte) 0xBF};

    private final ReportExportRepository reportExportRepository;
    private final AnalyticsService analyticsService;
    private final DailyAggregateRepository dailyAggregateRepository;
    private final FeedbackRepository feedbackRepository;
    private final PopularQuestionRepository popularQuestionRepository;
    private final DocumentPopularityRepository documentPopularityRepository;
    private final DepartmentDailyStatRepository departmentDailyStatRepository;
    private final UnansweredQuestionRepository unansweredQuestionRepository;
    private final UserServiceClient userServiceClient;
    private final UserServiceReportClient userServiceReportClient;
    private final ObjectMapper objectMapper;
    private final RabbitTemplate rabbitTemplate;
    private final MinioClient minioClient;

    @Value("${poliwise.cleanup.report-expiry-days:7}")
    private int reportExpiryDays;

    @Value("${MINIO_REPORT_BUCKET:poliwise-reports}")
    private String reportBucket;

    public ReportExportService(
            ReportExportRepository reportExportRepository,
            AnalyticsService analyticsService,
            DailyAggregateRepository dailyAggregateRepository,
            FeedbackRepository feedbackRepository,
            PopularQuestionRepository popularQuestionRepository,
            DocumentPopularityRepository documentPopularityRepository,
            DepartmentDailyStatRepository departmentDailyStatRepository,
            UnansweredQuestionRepository unansweredQuestionRepository,
            UserServiceClient userServiceClient,
            UserServiceReportClient userServiceReportClient,
            RabbitTemplate rabbitTemplate,
            MinioClient minioClient) {
        this.reportExportRepository = reportExportRepository;
        this.analyticsService = analyticsService;
        this.dailyAggregateRepository = dailyAggregateRepository;
        this.feedbackRepository = feedbackRepository;
        this.popularQuestionRepository = popularQuestionRepository;
        this.documentPopularityRepository = documentPopularityRepository;
        this.departmentDailyStatRepository = departmentDailyStatRepository;
        this.unansweredQuestionRepository = unansweredQuestionRepository;
        this.userServiceClient = userServiceClient;
        this.userServiceReportClient = userServiceReportClient;
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
                .setTimeZone(TimeZone.getTimeZone(ZoneOffset.UTC));
        this.rabbitTemplate = rabbitTemplate;
        this.minioClient = minioClient;
    }

    public ReportExportResponse createReport(UUID requestedBy, ReportExportRequest request) {
        ReportExport report = ReportExport.builder()
                .reportType(request.reportType()).title(request.title())
                .format(request.format()).departmentId(request.departmentId())
                .status(ExportStatus.PENDING).requestedBy(requestedBy)
                .build();
        if (request.dateFrom() != null) report.setDateFrom(request.dateFrom());
        if (request.dateTo() != null) report.setDateTo(request.dateTo());
        ReportExport saved = reportExportRepository.save(report);

        Map<String, Object> message = new HashMap<>();
        message.put("reportId", saved.getId().toString());
        Runnable publish = () -> rabbitTemplate.convertAndSend(
                RabbitMQConfig.EXCHANGE_NAME,
                RabbitMQConfig.ROUTING_REPORT_EXPORT,
                message
        );
        if (TransactionSynchronizationManager.isActualTransactionActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    publish.run();
                }
            });
        } else {
            publish.run();
        }

        return ReportExportResponse.fromEntity(saved);
    }

    @Transactional(readOnly = true)
    public ReportExportResponse getReportStatus(UUID id) {
        return reportExportRepository.findById(id)
                .map(ReportExportResponse::fromEntity)
                .orElseThrow(() -> new ReportNotFoundException(id));
    }

    @Transactional(readOnly = true)
    public ReportDownload openReport(UUID id, UUID userId, boolean isAdmin) {
        ReportExport report = reportExportRepository.findById(id)
                .orElseThrow(() -> new ReportNotFoundException(id));
        if (!isAdmin && !report.getRequestedBy().equals(userId)) {
            throw new UnauthorizedFeedbackAccessException();
        }
        if (report.getStatus() != ExportStatus.COMPLETED) {
            throw new IllegalStateException("Report not ready: " + report.getStatus());
        }
        try {
            InputStream inputStream = minioClient.getObject(
                GetObjectArgs.builder()
                        .bucket(reportBucket)
                        .object(report.getFileKey())
                        .build());
            long contentLength = report.getFileSizeBytes() != null ? report.getFileSizeBytes() : -1L;
            return new ReportDownload(inputStream, report.getFormat(), contentLength);
        } catch (Exception e) {
            log.error("Failed to download report from MinIO: {}", id, e);
            throw new RuntimeException("Failed to download report data", e);
        }
    }

    public void generateReport(UUID id) {
        ReportExport report = reportExportRepository.findById(id).orElse(null);
        if (report == null) return;
        if (report.getStatus() == ExportStatus.COMPLETED) {
            log.info("Skipping already completed report export: {}", id);
            return;
        }
        report.setStatus(ExportStatus.PROCESSING);
        reportExportRepository.save(report);
        try {
            byte[] data = generateReportData(report);
            String fileKey = "reports/" + id + "." + report.getFormat().name().toLowerCase();
            ensureReportBucketExists();

            try (InputStream is = new ByteArrayInputStream(data)) {
                minioClient.putObject(
                        PutObjectArgs.builder()
                                .bucket(reportBucket)
                                .object(fileKey)
                                .stream(is, data.length, -1)
                                .contentType(report.getFormat() == ExportFormat.JSON ? "application/json" : "text/csv")
                                .build()
                );
            }

            report.setFileSizeBytes(data.length);
            report.setFileKey(fileKey);
            report.setStatus(ExportStatus.COMPLETED);
            report.setCompletedAt(Instant.now());
            report.setExpiresAt(Instant.now().plus(reportExpiryDays, java.time.temporal.ChronoUnit.DAYS));
        } catch (Exception e) {
            log.error("Report generation failed: {}", id, e);
            throw new IllegalStateException("Report generation failed", e);
        }
        reportExportRepository.save(report);
    }

    public void deleteReport(UUID id, UUID userId, boolean isAdmin) {
        ReportExport report = reportExportRepository.findById(id)
                .orElseThrow(() -> new ReportNotFoundException(id));
        if (!isAdmin && !report.getRequestedBy().equals(userId)) {
            throw new UnauthorizedFeedbackAccessException();
        }
        reportExportRepository.delete(report);
    }

    // ========================================================================
    // Data generation per report type
    // ========================================================================

    private byte[] generateReportData(ReportExport report) {
        LocalDate dateFrom = report.getDateFrom();
        LocalDate dateTo = report.getDateTo() != null ? report.getDateTo() : LocalDate.now();
        if (dateFrom == null) dateFrom = dateTo.minusDays(30);

        Map<String, Object> data = switch (report.getReportType()) {
            case USER_REPORT -> buildUserReport();
            case DEPARTMENT_REPORT -> buildDepartmentReport();
        };

        ExportFormat format = report.getFormat();
        String content;
        if (format == ExportFormat.JSON) {
            try { content = toJson(data, report); }
            catch (java.io.IOException e) { content = toCsv(data, report.getReportType().name(), report); }
        } else {
            content = toCsv(data, report.getReportType().name(), report);
        }
        byte[] body = content.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if (format != ExportFormat.JSON) {
            byte[] withBom = new byte[UTF8_BOM.length + body.length];
            System.arraycopy(UTF8_BOM, 0, withBom, 0, UTF8_BOM.length);
            System.arraycopy(body, 0, withBom, UTF8_BOM.length, body.length);
            return withBom;
        }
        return body;
    }

    // ------------------------------------------------------------------------
    // USAGE_SUMMARY — daily aggregate metrics over date range
    // ------------------------------------------------------------------------
    private Map<String, Object> buildUsageSummary(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        Long totalQuestions = dailyAggregateRepository.sumTotalQuestions(dateFrom, dateTo);
        Long totalLikes = dailyAggregateRepository.sumTotalLikes(dateFrom, dateTo);
        Long totalDislikes = dailyAggregateRepository.sumTotalDislikes(dateFrom, dateTo);
        long likes = totalLikes != null ? totalLikes : 0;
        long dislikes = totalDislikes != null ? totalDislikes : 0;
        long totalFeedbacks = likes + dislikes;

        BigDecimal satisfactionRate = BigDecimal.ZERO;
        if (totalFeedbacks > 0) {
            satisfactionRate = BigDecimal.valueOf(likes)
                    .divide(BigDecimal.valueOf(totalFeedbacks), 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100)).setScale(2, RoundingMode.HALF_UP);
        }

        List<DailyAggregate> daily = dailyAggregateRepository.findByDateBetweenOrderByDateDesc(dateFrom, dateTo);

        long totalRequests = daily.stream().mapToLong(d -> d.getTotalRequests() != null ? d.getTotalRequests() : 0).sum();
        long totalErrors = daily.stream().mapToLong(d -> d.getTotalErrors() != null ? d.getTotalErrors() : 0).sum();
        long newUsers = daily.stream().mapToLong(d -> d.getNewUsers() != null ? d.getNewUsers() : 0).sum();
        long docsUploaded = daily.stream().mapToLong(d -> d.getDocumentsUploaded() != null ? d.getDocumentsUploaded() : 0).sum();
        long docsPublished = daily.stream().mapToLong(d -> d.getDocumentsPublished() != null ? d.getDocumentsPublished() : 0).sum();
        long totalTokens = daily.stream().mapToLong(d -> d.getTotalTokensUsed() != null ? d.getTotalTokensUsed() : 0L).sum();
        double avgResponseTime = daily.stream()
                .filter(d -> d.getAvgResponseTimeMs() != null)
                .mapToInt(DailyAggregate::getAvgResponseTimeMs)
                .average().orElse(0);

        List<Map<String, Object>> dailyRows = daily.stream().map(d -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", d.getDate());
            row.put("totalQuestions", d.getTotalQuestions() != null ? d.getTotalQuestions() : 0);
            row.put("totalConversations", d.getTotalConversations() != null ? d.getTotalConversations() : 0);
            row.put("uniqueUsersAsked", d.getUniqueUsersAsked() != null ? d.getUniqueUsersAsked() : 0);
            row.put("likes", d.getTotalLikes() != null ? d.getTotalLikes() : 0);
            row.put("dislikes", d.getTotalDislikes() != null ? d.getTotalDislikes() : 0);
            row.put("totalRequests", d.getTotalRequests() != null ? d.getTotalRequests() : 0);
            row.put("totalErrors", d.getTotalErrors() != null ? d.getTotalErrors() : 0);
            row.put("avgResponseTimeMs", d.getAvgResponseTimeMs() != null ? d.getAvgResponseTimeMs() : 0);
            row.put("uniqueActiveUsers", d.getUniqueActiveUsers() != null ? d.getUniqueActiveUsers() : 0);
            row.put("newUsers", d.getNewUsers() != null ? d.getNewUsers() : 0);
            row.put("documentsUploaded", d.getDocumentsUploaded() != null ? d.getDocumentsUploaded() : 0);
            row.put("documentsPublished", d.getDocumentsPublished() != null ? d.getDocumentsPublished() : 0);
            row.put("totalTokensUsed", d.getTotalTokensUsed() != null ? d.getTotalTokensUsed() : 0L);
            row.put("avgTokensPerQuestion", d.getAvgTokensPerQuestion() != null ? d.getAvgTokensPerQuestion() : 0);
            return row;
        }).toList();

        meta.put("totalQuestions", totalQuestions != null ? totalQuestions : 0);
        meta.put("totalFeedbacks", totalFeedbacks);
        meta.put("totalLikes", likes);
        meta.put("totalDislikes", dislikes);
        meta.put("satisfactionRatePercent", satisfactionRate);
        meta.put("totalRequests", totalRequests);
        meta.put("totalErrors", totalErrors);
        meta.put("avgResponseTimeMs", Math.round(avgResponseTime));
        meta.put("newUsers", newUsers);
        meta.put("documentsUploaded", docsUploaded);
        meta.put("documentsPublished", docsPublished);
        meta.put("totalTokensUsed", totalTokens);
        meta.put("dailyBreakdown", dailyRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // QUESTION_ANALYTICS — top popular questions
    // ------------------------------------------------------------------------
    private Map<String, Object> buildQuestionAnalytics(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        Instant fromInst = dateFrom.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant toInst = dateTo.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);

        Long totalAsked = popularQuestionRepository.sumAskCountBetween(fromInst, toInst);
        List<PopularQuestion> topQuestions = popularQuestionRepository
                .findTop10ByOrderByAskCountDesc(PageRequest.of(0, 50));

        List<Map<String, Object>> questionRows = topQuestions.stream().map(q -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("questionSample", q.getQuestionSample());
            row.put("askCount", q.getAskCount() != null ? q.getAskCount() : 0);
            row.put("uniqueUsersCount", q.getUniqueUsersCount() != null ? q.getUniqueUsersCount() : 0);
            row.put("totalLikes", q.getTotalLikes() != null ? q.getTotalLikes() : 0);
            row.put("totalDislikes", q.getTotalDislikes() != null ? q.getTotalDislikes() : 0);
            row.put("detectedCategory", q.getDetectedCategory() != null ? q.getDetectedCategory() : "N/A");
            row.put("firstAskedAt", q.getFirstAskedAt() != null ? DT.format(q.getFirstAskedAt()) : "");
            row.put("lastAskedAt", q.getLastAskedAt() != null ? DT.format(q.getLastAskedAt()) : "");
            return row;
        }).toList();

        meta.put("totalQuestionsAsked", totalAsked != null ? totalAsked : 0);
        meta.put("uniqueQuestionsTracked", topQuestions.size());
        meta.put("topQuestions", questionRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // FEEDBACK_ANALYSIS — feedback type breakdown and trends
    // ------------------------------------------------------------------------
    private Map<String, Object> buildFeedbackAnalysis(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        Instant fromInst = dateFrom.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant toInst = dateTo.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);

        long totalCount = feedbackRepository.countByCreatedAtBetween(fromInst, toInst);

        List<Object[]> typeBreakdown = feedbackRepository.countByTypeGrouped(fromInst, toInst);
        Map<String, Long> byType = new LinkedHashMap<>();
        for (Object[] row : typeBreakdown) {
            FeedbackType ft = (FeedbackType) row[0];
            Long cnt = (Long) row[1];
            byType.put(ft != null ? ft.name() : "UNKNOWN", cnt);
        }

        List<Feedback> inRange = new ArrayList<>();
        int page = 0;
        Page<Feedback> feedbackPage;
        do {
            feedbackPage = feedbackRepository.findByCreatedAtBetween(fromInst, toInst, PageRequest.of(page, 500));
            inRange.addAll(feedbackPage.getContent());
            page++;
        } while (feedbackPage.hasNext());

        long likes = inRange.stream().filter(f -> f.getType() == FeedbackType.LIKE).count();
        long dislikes = inRange.stream().filter(f -> f.getType() == FeedbackType.DISLIKE).count();

        List<Map<String, Object>> sampleRows = inRange.stream()
                .map(f -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("feedbackId", f.getId());
                    row.put("userId", f.getUserId());
                    row.put("messageId", f.getMessageId());
                    row.put("conversationId", f.getConversationId());
                    row.put("type", f.getType() != null ? f.getType().name() : "");
                    row.put("comment", f.getComment() != null ? f.getComment() : "");
                    row.put("questionText", truncate(f.getQuestionText(), 200));
                    row.put("answerText", truncate(f.getAnswerText(), 200));
                    row.put("userRole", f.getUserRole() != null ? f.getUserRole() : "");
                    row.put("createdAt", f.getCreatedAt() != null ? DT.format(f.getCreatedAt()) : "");
                    return row;
                }).toList();

        BigDecimal satisfactionRate = BigDecimal.ZERO;
        if (likes + dislikes > 0) {
            satisfactionRate = BigDecimal.valueOf(likes)
                    .divide(BigDecimal.valueOf(likes + dislikes), 4, RoundingMode.HALF_UP)
                    .multiply(BigDecimal.valueOf(100)).setScale(2, RoundingMode.HALF_UP);
        }

        meta.put("totalFeedbackCount", totalCount);
        meta.put("likes", likes);
        meta.put("dislikes", dislikes);
        meta.put("satisfactionRatePercent", satisfactionRate);
        meta.put("breakdownByType", byType);
        meta.put("sampleFeedbacks", sampleRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // USER_ENGAGEMENT — user activity from DailyAggregate
    // ------------------------------------------------------------------------
    private Map<String, Object> buildUserEngagement(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        List<DailyAggregate> daily = dailyAggregateRepository.findByDateBetweenOrderByDateDesc(dateFrom, dateTo);

        long totalUniqueUsers = daily.stream()
                .mapToLong(d -> d.getUniqueActiveUsers() != null ? d.getUniqueActiveUsers() : 0)
                .distinct().sum();
        long totalNewUsers = daily.stream()
                .mapToLong(d -> d.getNewUsers() != null ? d.getNewUsers() : 0).sum();
        long totalQuestions = daily.stream()
                .mapToLong(d -> d.getTotalQuestions() != null ? d.getTotalQuestions() : 0).sum();

        // Group by role if available in Feedback
        Instant fromInst = dateFrom.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant toInst = dateTo.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);

        List<Feedback> feedbacks = new ArrayList<>();
        int page = 0;
        Page<Feedback> feedbackPage;
        do {
            feedbackPage = feedbackRepository.findByCreatedAtBetween(fromInst, toInst, PageRequest.of(page, 500));
            feedbacks.addAll(feedbackPage.getContent());
            page++;
        } while (feedbackPage.hasNext());

        Map<String, Long> byRole = feedbacks.stream()
                .filter(f -> f.getUserRole() != null)
                .collect(Collectors.groupingBy(Feedback::getUserRole, Collectors.counting()));

        List<Map<String, Object>> dailyRows = daily.stream().map(d -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("date", d.getDate());
            row.put("uniqueActiveUsers", d.getUniqueActiveUsers() != null ? d.getUniqueActiveUsers() : 0);
            row.put("newUsers", d.getNewUsers() != null ? d.getNewUsers() : 0);
            row.put("totalQuestions", d.getTotalQuestions() != null ? d.getTotalQuestions() : 0);
            row.put("totalConversations", d.getTotalConversations() != null ? d.getTotalConversations() : 0);
            row.put("uniqueUsersAsked", d.getUniqueUsersAsked() != null ? d.getUniqueUsersAsked() : 0);
            row.put("totalLikes", d.getTotalLikes() != null ? d.getTotalLikes() : 0);
            row.put("totalDislikes", d.getTotalDislikes() != null ? d.getTotalDislikes() : 0);
            row.put("avgResponseTimeMs", d.getAvgResponseTimeMs() != null ? d.getAvgResponseTimeMs() : 0);
            return row;
        }).toList();

        meta.put("totalUniqueActiveUsers", totalUniqueUsers);
        meta.put("totalNewUsers", totalNewUsers);
        meta.put("totalQuestionsAsked", totalQuestions);
        meta.put("engagementByRole", byRole);
        meta.put("dailyBreakdown", dailyRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // DOCUMENT_POPULARITY — top cited documents
    // ------------------------------------------------------------------------
    private Map<String, Object> buildDocumentPopularity(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        List<DocumentPopularity> topDocs = documentPopularityRepository
                .findTop10ByOrderByTotalCitationsDesc(PageRequest.of(0, 50));

        long totalCitations = topDocs.stream()
                .mapToLong(d -> d.getTotalCitations() != null ? d.getTotalCitations() : 0).sum();

        List<Map<String, Object>> docRows = topDocs.stream().map(d -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("documentId", d.getDocumentId());
            row.put("totalCitations", d.getTotalCitations() != null ? d.getTotalCitations() : 0);
            row.put("uniqueQuestionsCited", d.getUniqueQuestionsCited() != null ? d.getUniqueQuestionsCited() : 0);
            row.put("citationsWithLikes", d.getCitationsWithLikes() != null ? d.getCitationsWithLikes() : 0);
            row.put("citationsWithDislikes", d.getCitationsWithDislikes() != null ? d.getCitationsWithDislikes() : 0);
            row.put("citationsLast7Days", d.getCitationsLast7Days() != null ? d.getCitationsLast7Days() : 0);
            row.put("citationsLast30Days", d.getCitationsLast30Days() != null ? d.getCitationsLast30Days() : 0);
            row.put("firstCitedAt", d.getFirstCitedAt() != null ? DT.format(d.getFirstCitedAt()) : "");
            row.put("lastCitedAt", d.getLastCitedAt() != null ? DT.format(d.getLastCitedAt()) : "");
            return row;
        }).toList();

        meta.put("totalDocumentsTracked", topDocs.size());
        meta.put("totalCitations", totalCitations);
        meta.put("topDocuments", docRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // UNANSWERED_QUESTIONS — questions that fell below similarity threshold
    // ------------------------------------------------------------------------
    private Map<String, Object> buildUnansweredQuestions(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        Instant fromInst = dateFrom.atStartOfDay().toInstant(ZoneOffset.UTC);
        Instant toInst = dateTo.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);

        Long totalUnanswered = unansweredQuestionRepository.countUnansweredBetween(fromInst, toInst);
        long totalResolved = unansweredQuestionRepository.countByResolved(true);

        List<UnansweredQuestion> allUnanswered = new ArrayList<>();
        int page = 0;
        Page<UnansweredQuestion> unansweredPage;
        do {
            unansweredPage = unansweredQuestionRepository.findByResolved(false, PageRequest.of(page, 500));
            allUnanswered.addAll(unansweredPage.getContent().stream()
                    .filter(q -> q.getCreatedAt() != null
                            && !q.getCreatedAt().isBefore(fromInst)
                            && q.getCreatedAt().isBefore(toInst))
                    .toList());
            page++;
        } while (unansweredPage.hasNext());

        Map<String, Long> byPriority = allUnanswered.stream()
                .filter(q -> q.getPriority() != null)
                .collect(Collectors.groupingBy(q -> q.getPriority().name(), Collectors.counting()));

        Map<String, Long> byCategory = allUnanswered.stream()
                .filter(q -> q.getCategory() != null)
                .collect(Collectors.groupingBy(UnansweredQuestion::getCategory, Collectors.counting()));

        List<Map<String, Object>> questionRows = allUnanswered.stream().map(q -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("questionId", q.getId());
            row.put("question", truncate(q.getQuestion(), 300));
            row.put("userId", q.getUserId());
            row.put("userRole", q.getUserRole() != null ? q.getUserRole() : "");
            row.put("category", q.getCategory() != null ? q.getCategory() : "");
            row.put("priority", q.getPriority() != null ? q.getPriority().name() : "NORMAL");
            row.put("resolved", q.getResolved() != null ? q.getResolved() : false);
            row.put("resolvedBy", q.getResolvedBy());
            row.put("resolvedAt", q.getResolvedAt() != null ? DT.format(q.getResolvedAt()) : "");
            row.put("resolutionNotes", q.getResolutionNotes() != null ? q.getResolutionNotes() : "");
            row.put("topSimilarityScore", q.getTopSimilarityScore() != null
                    ? q.getTopSimilarityScore().setScale(4, RoundingMode.HALF_UP) : "");
            row.put("createdAt", q.getCreatedAt() != null ? DT.format(q.getCreatedAt()) : "");
            return row;
        }).toList();

        meta.put("totalUnansweredInPeriod", totalUnanswered != null ? totalUnanswered : 0);
        meta.put("totalResolvedAllTime", totalResolved);
        meta.put("byPriority", byPriority);
        meta.put("byCategory", byCategory);
        meta.put("questions", questionRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // DEPARTMENT_BREAKDOWN — per-department daily stats
    // ------------------------------------------------------------------------
    private Map<String, Object> buildDepartmentBreakdown(LocalDate dateFrom, LocalDate dateTo, UUID departmentId) {
        Map<String, Object> meta = reportMeta(dateFrom, dateTo);

        List<DepartmentDailyStat> stats;
        if (departmentId != null) {
            stats = departmentDailyStatRepository.findByDepartmentIdOrderByDateDesc(departmentId)
                    .stream()
                    .filter(s -> s.getDate() != null
                            && !s.getDate().isBefore(dateFrom)
                            && !s.getDate().isAfter(dateTo))
                    .toList();
        } else {
            stats = departmentDailyStatRepository
                    .findByDateBetweenOrderByDateDesc(dateFrom, dateTo)
                    .stream()
                    .filter(s -> s.getDate() != null)
                    .toList();
        }

        // Group by department
        Map<UUID, List<DepartmentDailyStat>> byDept = stats.stream()
                .filter(s -> s.getDepartmentId() != null)
                .collect(Collectors.groupingBy(DepartmentDailyStat::getDepartmentId));

        List<Map<String, Object>> deptRows = byDept.entrySet().stream().map(entry -> {
            UUID deptId = entry.getKey();
            List<DepartmentDailyStat> deptStats = entry.getValue();
            long totalQuestions = deptStats.stream()
                    .mapToLong(s -> s.getTotalQuestions() != null ? s.getTotalQuestions() : 0).sum();
            long totalLikes = deptStats.stream()
                    .mapToLong(s -> s.getLikes() != null ? s.getLikes() : 0).sum();
            long totalDislikes = deptStats.stream()
                    .mapToLong(s -> s.getDislikes() != null ? s.getDislikes() : 0).sum();
            BigDecimal rate = BigDecimal.ZERO;
            if (totalLikes + totalDislikes > 0) {
                rate = BigDecimal.valueOf(totalLikes)
                        .divide(BigDecimal.valueOf(totalLikes + totalDislikes), 4, RoundingMode.HALF_UP)
                        .multiply(BigDecimal.valueOf(100)).setScale(2, RoundingMode.HALF_UP);
            }

            List<Map<String, Object>> dailyRows = deptStats.stream().map(s -> {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("date", s.getDate());
                row.put("totalQuestions", s.getTotalQuestions() != null ? s.getTotalQuestions() : 0);
                row.put("uniqueUsers", s.getUniqueUsers() != null ? s.getUniqueUsers() : 0);
                row.put("likes", s.getLikes() != null ? s.getLikes() : 0);
                row.put("dislikes", s.getDislikes() != null ? s.getDislikes() : 0);
                return row;
            }).toList();

            Map<String, Object> deptRow = new LinkedHashMap<>();
            deptRow.put("departmentId", deptId);
            deptRow.put("totalQuestionsInPeriod", totalQuestions);
            deptRow.put("totalLikes", totalLikes);
            deptRow.put("totalDislikes", totalDislikes);
            deptRow.put("satisfactionRatePercent", rate);
            deptRow.put("dailyBreakdown", dailyRows);
            return deptRow;
        }).toList();

        meta.put("departmentsIncluded", deptRows.size());
        meta.put("departments", deptRows);
        return meta;
    }

    // ------------------------------------------------------------------------
    // USER_REPORT — user statistics summary
    // ------------------------------------------------------------------------
    private Map<String, Object> buildUserReport() {
        Map<String, Object> meta = reportMeta(LocalDate.now().minusYears(10), LocalDate.now());
        meta.remove("periodFrom");
        meta.remove("periodTo");

        try {
            UserStatsResponse userStats = userServiceClient.getStats();
            meta.put("totalUsers", userStats.totalUsers());
            meta.put("activeUsers", userStats.activeUsers());
            meta.put("inactiveUsers", userStats.totalUsers() - userStats.activeUsers());
        } catch (Exception e) {
            log.warn("Failed to fetch user stats from user-service: {}", e.getMessage());
            meta.put("totalUsers", 0L);
            meta.put("activeUsers", 0L);
            meta.put("inactiveUsers", 0L);
        }

        return meta;
    }

    // ------------------------------------------------------------------------
    // DEPARTMENT_REPORT — department listing with member counts
    // ------------------------------------------------------------------------
    private Map<String, Object> buildDepartmentReport() {
        Map<String, Object> meta = reportMeta(LocalDate.now().minusYears(10), LocalDate.now());
        meta.remove("periodFrom");
        meta.remove("periodTo");

        List<Map<String, Object>> departmentRows = new ArrayList<>();

        try {
            // Fetch all departments (no pagination for report)
            List<DepartmentListResponse> allDepts = userServiceReportClient.getAllDepartments();
            meta.put("totalDepartments", allDepts.size());

            for (DepartmentListResponse dept : allDepts) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("departmentId", dept.id());
                row.put("name", dept.name());
                row.put("code", dept.code());
                row.put("description", dept.description() != null ? dept.description() : "");
                row.put("memberCount", dept.memberCount() != null ? dept.memberCount() : 0);
                row.put("isActive", dept.isActive() != null ? dept.isActive() : false);
                row.put("createdAt", dept.createdAt() != null ? DT.format(dept.createdAt().toInstant()) : "");
                row.put("updatedAt", dept.updatedAt() != null ? DT.format(dept.updatedAt().toInstant()) : "");
                departmentRows.add(row);
            }
        } catch (Exception e) {
            log.warn("Failed to fetch departments from user-service: {}", e.getMessage());
            meta.put("totalDepartments", 0);
        }

        meta.put("departments", departmentRows);
        return meta;
    }

    // ========================================================================
    // CSV / JSON serialization
    // ========================================================================

    private String toCsv(Map<String, Object> data, String reportType, ReportExport report) {
        StringBuilder sb = new StringBuilder();

        // Header section — report metadata
        sb.append("# BÁO CÁO: ").append(reportType).append("\n");
        sb.append("# Tiêu đề: ").append(escape(report.getTitle())).append("\n");
        sb.append("# Thời gian tạo: ").append(report.getCreatedAt() != null ? DT.format(report.getCreatedAt()) : "").append("\n");
        if (report.getDateFrom() != null) sb.append("# Từ ngày: ").append(report.getDateFrom()).append("\n");
        if (report.getDateTo() != null) sb.append("# Đến ngày: ").append(report.getDateTo()).append("\n");
        sb.append("#\n");

        flattenCsv(sb, data, "");
        return sb.toString();
    }

    private void flattenCsv(StringBuilder sb, Map<String, Object> data, String prefix) {
        for (Map.Entry<String, Object> entry : data.entrySet()) {
            String key = prefix.isEmpty() ? entry.getKey() : prefix + "." + entry.getKey();
            Object value = entry.getValue();

            if (value instanceof List<?> list) {
                if (list.isEmpty()) {
                    sb.append(escape(key)).append("\n");
                    continue;
                }
                Object first = list.get(0);
                if (first instanceof Map) {
                    // Table section — emit header row then data rows
                    @SuppressWarnings("unchecked")
                    Map<String, Object> firstRow = (Map<String, Object>) first;
                    List<String> cols = new ArrayList<>(firstRow.keySet());
                    sb.append("# ===== ").append(escape(key)).append(" =====\n");
                    sb.append("# ").append(String.join(", ", cols.stream().map(this::escape).toList())).append("\n");
                    for (Object item : list) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> row = (Map<String, Object>) item;
                        String rowStr = cols.stream()
                                .map(c -> escape(String.valueOf(row.getOrDefault(c, ""))))
                                .collect(Collectors.joining(","));
                        sb.append(rowStr).append("\n");
                    }
                    sb.append("\n");
                } else {
                    // Simple list
                    sb.append(escape(key)).append(": ").append(list.stream()
                            .map(v -> escape(String.valueOf(v)))
                            .collect(Collectors.joining("; "))).append("\n");
                }
            } else if (value instanceof Map<?, ?> map) {
                flattenCsv(sb, (Map<String, Object>) map, key);
            } else {
                sb.append(escape(key)).append(": ").append(escape(String.valueOf(value))).append("\n");
            }
        }
    }

    private String escape(String s) {
        if (s == null) return "";
        // Sanitize CSV Injection
        if (s.matches("^\\s*[=+\\-@].*")) {
            s = "'" + s;
        }
        if (s.contains(",") || s.contains("\"") || s.contains("\n") || s.contains("\r")) {
            return "\"" + s.replace("\"", "\"\"") + "\"";
        }
        return s;
    }

    private String toJson(Map<String, Object> data, ReportExport report) throws java.io.IOException {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("reportId", report.getId());
        root.put("reportType", report.getReportType().name());
        root.put("title", report.getTitle());
        root.put("createdAt", report.getCreatedAt() != null ? DT.format(report.getCreatedAt()) : null);
        root.put("periodFrom", report.getDateFrom() != null ? report.getDateFrom().toString() : null);
        root.put("periodTo", report.getDateTo() != null ? report.getDateTo().toString() : null);
        root.put("requestedBy", report.getRequestedBy());
        root.putAll(data);
        return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(root);
    }

    private Map<String, Object> reportMeta(LocalDate dateFrom, LocalDate dateTo) {
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("reportType", "");
        meta.put("generatedAt", DT.format(Instant.now()));
        meta.put("periodFrom", dateFrom.toString());
        meta.put("periodTo", dateTo.toString());
        return meta;
    }

    private String truncate(String s, int maxLen) {
        if (s == null) return "";
        return s.length() <= maxLen ? s : s.substring(0, maxLen) + "...";
    }

    // ========================================================================
    // Cleanup & user list
    // ========================================================================

    private void ensureReportBucketExists() throws Exception {
        boolean exists;
        try {
            exists = minioClient.bucketExists(BucketExistsArgs.builder().bucket(reportBucket).build());
        } catch (io.minio.errors.ErrorResponseException e) {
            if (!"NoSuchBucket".equals(e.errorResponse().code())) throw e;
            exists = false;
        }
        if (!exists) {
            try {
                minioClient.makeBucket(
                        MakeBucketArgs.builder().bucket(reportBucket).build()
                );
                log.info("Created MinIO bucket: {}", reportBucket);
            } catch (io.minio.errors.ErrorResponseException e) {
                String code = e.errorResponse().code();
                if (!"BucketAlreadyOwnedByYou".equals(code) && !"BucketAlreadyExists".equals(code)) throw e;
            }
        }
    }

    @Scheduled(cron = "0 0 1 * * *")
    @Transactional
    public void deleteExpiredReports() {
        List<ReportExport> expired = reportExportRepository.findExpiredReports(Instant.now());
        reportExportRepository.deleteAll(expired);
        if (!expired.isEmpty()) log.info("Deleted {} expired reports", expired.size());
    }

    @Transactional(readOnly = true)
    public Page<ReportExportResponse> getReportsByUser(UUID userId, Pageable pageable) {
        return reportExportRepository.findByRequestedBy(userId, pageable).map(ReportExportResponse::fromEntity);
    }
}
