package com.poliwise.feedback.service;

import com.poliwise.feedback.entity.ReportExport;
import com.poliwise.feedback.enums.ExportStatus;
import com.poliwise.feedback.repository.ReportExportRepository;
import org.junit.jupiter.api.Test;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ReportExportFailureServiceTest {

    @Test
    void terminalFailureUsesSafeMessage() {
        ReportExportRepository repository = mock(ReportExportRepository.class);
        ReportExportFailureService service = new ReportExportFailureService(repository);
        UUID reportId = UUID.randomUUID();
        ReportExport report = ReportExport.builder().id(reportId).status(ExportStatus.PROCESSING).build();
        when(repository.findById(reportId)).thenReturn(Optional.of(report));

        service.markTerminalFailure(reportId);

        assertThat(report.getStatus()).isEqualTo(ExportStatus.FAILED);
        assertThat(report.getErrorMessage()).isEqualTo("Report generation failed after three attempts.");
        verify(repository).save(report);
    }
}
