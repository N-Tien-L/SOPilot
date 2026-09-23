package com.poliwise.feedback.listener;

import com.poliwise.feedback.service.ReportExportService;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;

class ReportExportListenerTest {

    @Test
    void generationFailureIsPropagatedToRabbitRetryInterceptor() {
        ReportExportService service = mock(ReportExportService.class);
        ReportExportListener listener = new ReportExportListener(service);
        UUID reportId = UUID.randomUUID();
        doThrow(new IllegalStateException("MinIO unavailable"))
                .when(service).generateReport(reportId);

        assertThatThrownBy(() -> listener.handleReportExportRequest(
                Map.of("reportId", reportId.toString())
        )).isInstanceOf(IllegalStateException.class);
    }
}
