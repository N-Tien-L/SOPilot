package com.poliwise.feedback.listener;

import com.poliwise.feedback.config.RabbitMQConfig;
import com.poliwise.feedback.service.ReportExportService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

@Component
public class ReportExportListener {

    private static final Logger log = LoggerFactory.getLogger(ReportExportListener.class);
    private final ReportExportService reportExportService;

    public ReportExportListener(ReportExportService reportExportService) {
        this.reportExportService = reportExportService;
    }

    @RabbitListener(
            queues = RabbitMQConfig.QUEUE_REPORT_EXPORT,
            containerFactory = "reportExportRabbitListenerContainerFactory"
    )
    public void handleReportExportRequest(Map<String, Object> message) {
        try {
            String reportIdStr = (String) message.get("reportId");
            if (reportIdStr == null) {
                log.error("Received report export request without reportId");
                return;
            }
            UUID reportId = UUID.fromString(reportIdStr);
            log.info("Processing report export request for report: {}", reportId);
            reportExportService.generateReport(reportId);
        } catch (Exception e) {
            log.error("Error processing report export request", e);
            throw e; // Will trigger retry/DLQ configured in RabbitMQ
        }
    }
}
