package com.poliwise.feedback.service;

import com.poliwise.feedback.enums.ExportStatus;
import com.poliwise.feedback.repository.ReportExportRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class ReportExportFailureService {

    private static final String SAFE_ERROR = "Report generation failed after three attempts.";

    private final ReportExportRepository reportExportRepository;

    public ReportExportFailureService(ReportExportRepository reportExportRepository) {
        this.reportExportRepository = reportExportRepository;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markTerminalFailure(UUID reportId) {
        reportExportRepository.findById(reportId).ifPresent(report -> {
            report.setStatus(ExportStatus.FAILED);
            report.setErrorMessage(SAFE_ERROR);
            reportExportRepository.save(report);
        });
    }
}
