package com.poliwise.knowledge.repository;

import com.poliwise.knowledge.entity.DocumentVersion;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface DocumentVersionRepository
        extends JpaRepository<DocumentVersion, UUID>, JpaSpecificationExecutor<DocumentVersion> {

    @Query("select v from DocumentVersion v where v.documentId = :documentId and v.deletedAt is null order by v.versionNumber desc")
    List<DocumentVersion> findByDocumentIdOrderByVersionNumberDesc(@Param("documentId") UUID documentId);

    Optional<DocumentVersion> findFirstByDocumentIdAndDeletedAtIsNullOrderByVersionNumberDesc(UUID documentId);

    default Optional<DocumentVersion> findFirstByDocumentIdOrderByVersionNumberDesc(UUID documentId) {
        return findFirstByDocumentIdAndDeletedAtIsNullOrderByVersionNumberDesc(documentId);
    }

    boolean existsByDocumentIdAndVersionNumberAndDeletedAtIsNull(UUID documentId, Integer versionNumber);

    @Query("select v from DocumentVersion v where v.documentId = :documentId and v.versionNumber = :versionNumber and v.deletedAt is null")
    Optional<DocumentVersion> findByDocumentIdAndVersionNumber(@Param("documentId") UUID documentId,
                                                               @Param("versionNumber") Integer versionNumber);

    @Query("select v from DocumentVersion v where v.documentId = :documentId and v.versionNumber = :versionNumber and v.deletedAt is not null")
    Optional<DocumentVersion> findDeletedByDocumentIdAndVersionNumber(@Param("documentId") UUID documentId,
                                                                      @Param("versionNumber") Integer versionNumber);

    long countByDocumentIdAndDeletedAtIsNull(UUID documentId);

    @Query("""
        SELECT v FROM DocumentVersion v
        WHERE v.fileChecksum = :checksum
          AND v.deletedAt IS NULL
        ORDER BY v.createdAt DESC
        """)
    List<DocumentVersion> findByFileChecksum(@Param("checksum") String fileChecksum);

    default Optional<DocumentVersion> findFirstByFileChecksum(String checksum) {
        List<DocumentVersion> results = findByFileChecksum(checksum);
        return results.isEmpty() ? Optional.empty() : Optional.of(results.get(0));
    }
}
