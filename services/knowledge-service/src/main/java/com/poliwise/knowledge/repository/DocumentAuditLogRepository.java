package com.poliwise.knowledge.repository;

import com.poliwise.knowledge.entity.DocumentAuditLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

@Repository
public interface DocumentAuditLogRepository extends JpaRepository<DocumentAuditLog, UUID> {

    Page<DocumentAuditLog> findByDocumentIdOrderByCreatedAtDesc(UUID documentId, Pageable pageable);

    Page<DocumentAuditLog> findByActorIdOrderByCreatedAtDesc(UUID actorId, Pageable pageable);

    Page<DocumentAuditLog> findByActionOrderByCreatedAtDesc(String action, Pageable pageable);

    @Query("""
            SELECT a FROM DocumentAuditLog a
            WHERE a.createdAt BETWEEN :startDate AND :endDate
            ORDER BY a.createdAt DESC
            """)
    Page<DocumentAuditLog> findByDateRange(
            @Param("startDate") OffsetDateTime startDate,
            @Param("endDate") OffsetDateTime endDate,
            Pageable pageable);

    @Query("""
            SELECT a FROM DocumentAuditLog a
            WHERE (:documentId IS NULL OR a.documentId = :documentId)
              AND (:actorId IS NULL OR a.actorId = :actorId)
              AND (:action IS NULL OR a.action = :action)
              AND (:startDate IS NULL OR a.createdAt >= :startDate)
              AND (:endDate IS NULL OR a.createdAt <= :endDate)
            ORDER BY a.createdAt DESC
            """)
    Page<DocumentAuditLog> searchAuditLogs(
            @Param("documentId") UUID documentId,
            @Param("actorId") UUID actorId,
            @Param("action") String action,
            @Param("startDate") OffsetDateTime startDate,
            @Param("endDate") OffsetDateTime endDate,
            Pageable pageable);

    List<DocumentAuditLog> findByDocumentIdOrderByCreatedAtDesc(UUID documentId);
}
