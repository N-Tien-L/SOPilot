package com.poliwise.metadata.repository;

import com.poliwise.metadata.entity.DocumentTag;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface DocumentTagRepository
        extends JpaRepository<DocumentTag, UUID>, JpaSpecificationExecutor<DocumentTag> {

    List<DocumentTag> findByDocumentMetadataId(UUID documentMetadataId);

    List<DocumentTag> findByTag_Id(UUID tagId);

    Optional<DocumentTag> findByDocumentMetadataIdAndTag_Id(UUID documentMetadataId, UUID tagId);

    boolean existsByDocumentMetadataIdAndTag_Id(UUID documentMetadataId, UUID tagId);

    long deleteByDocumentMetadataIdAndTag_Id(UUID documentMetadataId, UUID tagId);

    long deleteByDocumentMetadataId(UUID documentMetadataId);
}
