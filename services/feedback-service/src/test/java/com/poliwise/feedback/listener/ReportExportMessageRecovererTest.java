package com.poliwise.feedback.listener;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.poliwise.feedback.service.ReportExportFailureService;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.AmqpRejectAndDontRequeueException;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class ReportExportMessageRecovererTest {

    @Test
    void exhaustedRetriesMarkReportFailedAndRejectForDeadLettering() {
        ReportExportFailureService failureService = mock(ReportExportFailureService.class);
        ReportExportMessageRecoverer recoverer = new ReportExportMessageRecoverer(failureService, new ObjectMapper());
        UUID reportId = UUID.randomUUID();
        Message message = new Message(
                ("{\"reportId\":\"" + reportId + "\"}").getBytes(StandardCharsets.UTF_8),
                new MessageProperties()
        );

        assertThatThrownBy(() -> recoverer.recover(message, new IllegalStateException("storage error")))
                .isInstanceOf(AmqpRejectAndDontRequeueException.class);

        verify(failureService).markTerminalFailure(reportId);
    }
}
