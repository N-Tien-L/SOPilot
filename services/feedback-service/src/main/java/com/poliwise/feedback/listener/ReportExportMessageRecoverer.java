package com.poliwise.feedback.listener;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.poliwise.feedback.service.ReportExportFailureService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.AmqpRejectAndDontRequeueException;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.retry.MessageRecoverer;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

@Component
public class ReportExportMessageRecoverer implements MessageRecoverer {

    private static final Logger log = LoggerFactory.getLogger(ReportExportMessageRecoverer.class);
    private static final String SAFE_ERROR = "Report generation failed after three attempts.";

    private final ReportExportFailureService failureService;
    private final ObjectMapper objectMapper;

    public ReportExportMessageRecoverer(
            ReportExportFailureService failureService,
            ObjectMapper objectMapper) {
        this.failureService = failureService;
        this.objectMapper = objectMapper;
    }

    @Override
    public void recover(Message message, Throwable cause) {
        UUID reportId = extractReportId(message);
        if (reportId != null) {
            failureService.markTerminalFailure(reportId);
        }
        log.error("Report export exhausted all retry attempts: {}", reportId, cause);
        throw new AmqpRejectAndDontRequeueException(SAFE_ERROR, cause);
    }

    private UUID extractReportId(Message message) {
        try {
            Map<String, Object> payload = objectMapper.readValue(
                    message.getBody(),
                    new TypeReference<>() { }
            );
            Object value = payload.get("reportId");
            return value != null ? UUID.fromString(value.toString()) : null;
        } catch (Exception e) {
            log.error("Could not extract reportId from failed report export message", e);
            return null;
        }
    }
}
