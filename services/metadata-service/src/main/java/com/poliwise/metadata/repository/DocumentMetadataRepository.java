package com.poliwise.metadata.repository;

import com.poliwise.metadata.entity.DocumentMetadata;
import com.poliwise.metadata.enums.DocumentStatus;
import jakarta.persistence.LockModeType;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface DocumentMetadataRepository extends JpaRepository<DocumentMetadata, UUID>,
                JpaSpecificationExecutor<DocumentMetadata> {

        Optional<DocumentMetadata> findByDocumentId(UUID documentId);

        Optional<DocumentMetadata> findByDocumentIdAndDeletedAtIsNull(UUID documentId);

        Page<DocumentMetadata> findByStatusInAndDeletedAtIsNullOrderByUpdatedAtDesc(
                        Collection<DocumentStatus> statuses, Pageable pageable);

        Page<DocumentMetadata> findByCategoryIdAndDeletedAtIsNullOrderByUpdatedAtDesc(
                        UUID categoryId, Pageable pageable);

        @Query("""
                        select dm
                        from DocumentMetadata dm
                        where dm.deletedAt is null
                          and dm.expiryDate is not null
                          and dm.expiryDate <= :date
                        """)
        List<DocumentMetadata> findExpiredDocuments(@Param("date") LocalDate date);

        @Lock(LockModeType.PESSIMISTIC_WRITE)
        @Query("select dm from DocumentMetadata dm where dm.id = :id and dm.deletedAt is null")
        Optional<DocumentMetadata> findByIdForUpdate(@Param("id") UUID id);

        @Query("select dm from DocumentMetadata dm where dm.id = :id and dm.deletedAt is null")
        Optional<DocumentMetadata> findByIdAndDeletedAtIsNull(@Param("id") UUID id);

        List<DocumentMetadata> findByStatus(DocumentStatus status);

        List<DocumentMetadata> findByCategoryId(UUID categoryId);
}
