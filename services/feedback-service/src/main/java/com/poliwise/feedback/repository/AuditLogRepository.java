package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.AuditLog;
import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.ResourceType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.UUID;

@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, UUID>, JpaSpecificationExecutor<AuditLog> {

    Page<AuditLog> findByAction(AuditAction action, Pageable pageable);

    Page<AuditLog> findByUserId(UUID userId, Pageable pageable);

    Page<AuditLog> findByResourceTypeAndResourceId(ResourceType resourceType, UUID resourceId, Pageable pageable);

    Page<AuditLog> findByCreatedAtBetween(Instant from, Instant to, Pageable pageable);

    Page<AuditLog> findByUsernameContainingIgnoreCase(String keyword, Pageable pageable);

    @Query("SELECT COUNT(a) FROM AuditLog a WHERE a.createdAt < :before")
    long countByCreatedAtBefore(@Param("before") Instant before);

    void deleteByCreatedAtBefore(@Param("before") Instant before);

    long countByAction(AuditAction action);
}
