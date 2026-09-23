package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.ReportExport;
import com.poliwise.feedback.enums.ExportStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface ReportExportRepository extends JpaRepository<ReportExport, UUID> {

    Page<ReportExport> findByRequestedBy(UUID requestedBy, Pageable pageable);

    List<ReportExport> findByStatus(ExportStatus status);

    @Query("SELECT r FROM ReportExport r WHERE r.expiresAt IS NOT NULL AND r.expiresAt < :now")
    List<ReportExport> findExpiredReports(@Param("now") Instant now);

    long countByRequestedByAndStatus(UUID requestedBy, ExportStatus status);
}
