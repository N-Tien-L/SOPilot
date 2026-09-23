package com.poliwise.knowledge.repository;

import com.poliwise.knowledge.entity.DocumentVersionDeletion;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface DocumentVersionDeletionRepository extends JpaRepository<DocumentVersionDeletion, UUID> {

    Optional<DocumentVersionDeletion> findByDocumentIdAndVersionNumber(UUID documentId, Integer versionNumber);

    boolean existsByDocumentIdAndVersionNumber(UUID documentId, Integer versionNumber);
}
