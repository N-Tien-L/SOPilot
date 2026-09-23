package com.poliwise.feedback.scheduler;

import com.poliwise.feedback.entity.ReportExport;
import com.poliwise.feedback.entity.UnansweredQuestion;
import com.poliwise.feedback.repository.AuditLogRepository;
import com.poliwise.feedback.repository.ReportExportRepository;
import com.poliwise.feedback.repository.UnansweredQuestionRepository;
import com.poliwise.feedback.service.AuditLogService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Component
public class CleanupScheduler {

    private static final Logger log = LoggerFactory.getLogger(CleanupScheduler.class);

    private final AuditLogRepository auditLogRepository;
    private final ReportExportRepository reportExportRepository;
    private final UnansweredQuestionRepository unansweredQuestionRepository;
    private final AuditLogService auditLogService;

    @Value("${poliwise.cleanup.audit-retention-days:90}")
    private int auditRetentionDays;

    @Value("${poliwise.cleanup.report-expiry-days:7}")
    private int reportExpiryDays;

    public CleanupScheduler(AuditLogRepository auditLogRepository,
                           ReportExportRepository reportExportRepository,
                           UnansweredQuestionRepository unansweredQuestionRepository,
                           AuditLogService auditLogService) {
        this.auditLogRepository = auditLogRepository;
        this.reportExportRepository = reportExportRepository;
        this.unansweredQuestionRepository = unansweredQuestionRepository;
        this.auditLogService = auditLogService;
    }

    @Scheduled(cron = "0 0 1 * * *")
    @Transactional
    public void cleanupOldData() {
        cleanupAuditLogs();
        cleanupExpiredReports();
        cleanupOldResolvedQuestions();
    }

    private void cleanupAuditLogs() {
        try {
            long cleaned = auditLogService.cleanupOldLogs();
            log.info("Audit log cleanup completed: {} records removed", cleaned);
        } catch (Exception e) {
            log.error("Failed to cleanup audit logs", e);
        }
    }

    private void cleanupExpiredReports() {
        try {
            List<ReportExport> expired = reportExportRepository.findExpiredReports(Instant.now());
            if (!expired.isEmpty()) {
                reportExportRepository.deleteAll(expired);
                log.info("Deleted {} expired report exports", expired.size());
            }
        } catch (Exception e) {
            log.error("Failed to cleanup expired reports", e);
        }
    }

    private void cleanupOldResolvedQuestions() {
        try {
            Instant cutoff = Instant.now().minus(180, ChronoUnit.DAYS);
            List<UnansweredQuestion> oldResolved = unansweredQuestionRepository.findResolvedBefore(cutoff);
            if (!oldResolved.isEmpty()) {
                unansweredQuestionRepository.deleteAll(oldResolved);
                log.info("Deleted {} old resolved unanswered questions", oldResolved.size());
            }
        } catch (Exception e) {
            log.error("Failed to cleanup old resolved questions", e);
        }
    }
}
