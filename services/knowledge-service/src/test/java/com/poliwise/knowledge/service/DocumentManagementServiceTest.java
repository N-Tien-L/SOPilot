package com.poliwise.knowledge.service;

import com.poliwise.knowledge.client.IngestionServiceClient;
import com.poliwise.knowledge.client.MetadataServiceClient;
import com.poliwise.knowledge.dto.*;
import com.poliwise.knowledge.entity.Document;
import com.poliwise.knowledge.entity.DocumentVersion;
import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;
import com.poliwise.knowledge.enums.ProcessingStatus;
import com.poliwise.knowledge.event.DocumentEventPublisher;
import com.poliwise.knowledge.exception.DuplicateDocumentException;
import com.poliwise.knowledge.repository.DocumentAuditLogRepository;
import com.poliwise.knowledge.repository.DocumentRepository;
import com.poliwise.knowledge.repository.DocumentVersionRepository;
import com.poliwise.knowledge.repository.ProcessingJobRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.OffsetDateTime;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class DocumentManagementServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private DocumentVersionRepository versionRepository;

    @Mock
    private DocumentAuditLogRepository auditLogRepository;

    @Mock
    private StorageService storageService;

    @Mock
    private DocumentEventPublisher eventPublisher;

    @Mock
    private com.fasterxml.jackson.databind.ObjectMapper objectMapper;

    @Mock
    private MetadataServiceClient metadataServiceClient;

    @Mock
    private DocumentParsingService parsingService;

    @Mock
    private IngestionServiceClient ingestionServiceClient;

    @Mock
    private ProcessingJobRepository jobRepository;

    private DocumentManagementService service;

    @BeforeEach
    void setUp() {
        service = new DocumentManagementService(
                documentRepository,
                versionRepository,
                auditLogRepository,
                storageService,
                eventPublisher,
                objectMapper,
                metadataServiceClient,
                parsingService,
                ingestionServiceClient,
                jobRepository
        );
    }

    // ========== checkDuplicate Tests ==========

    @Test
    @DisplayName("checkDuplicate returns not duplicate when checksum is null")
    void checkDuplicate_nullChecksum_returnsNotDuplicate() {
        DuplicateCheckResponse result = service.checkDuplicate(null);
        assertFalse(result.isDuplicate());
        assertNull(result.action());
        assertNull(result.existingDocument());
    }

    @Test
    @DisplayName("checkDuplicate returns not duplicate when checksum is blank")
    void checkDuplicate_blankChecksum_returnsNotDuplicate() {
        DuplicateCheckResponse result = service.checkDuplicate("  ");
        assertFalse(result.isDuplicate());
    }

    @Test
    @DisplayName("checkDuplicate returns duplicate when found via ingestion-service")
    void checkDuplicate_foundViaIngestionService_returnsDuplicate() {
        String checksum = "abc123def456";
        UUID docId = UUID.randomUUID();

        DocumentDuplicateInfo docInfo = new DocumentDuplicateInfo(
                docId, "test.pdf", 1024L, OffsetDateTime.now(), "Test Doc", null, "READY", checksum
        );
        DuplicateCheckResponse expectedResponse = new DuplicateCheckResponse(
                true, "BLOCK", docInfo, null, "file_checksum"
        );

        when(ingestionServiceClient.checkDuplicateByChecksum(checksum)).thenReturn(expectedResponse);

        DuplicateCheckResponse result = service.checkDuplicate(checksum);

        assertTrue(result.isDuplicate());
        assertEquals("BLOCK", result.action());
        assertNotNull(result.existingDocument());
        assertEquals(docId, result.existingDocument().documentId());
        assertEquals("file_checksum", result.detectionMethod());
    }

    @Test
    @DisplayName("checkDuplicate returns not duplicate when not found in ingestion-service but found locally")
    void checkDuplicate_notInIngestionService_fallsBackToLocal() {
        String checksum = "local-checksum";
        UUID docId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();

        Document doc = Document.builder()
                .id(docId)
                .originalFilename("test.pdf")
                .fileSizeBytes(1024L)
                .status(ProcessingStatus.READY)
                .createdAt(OffsetDateTime.now())
                .build();

        DocumentVersion version = DocumentVersion.builder()
                .id(versionId)
                .documentId(docId)
                .versionNumber(1)
                .fileChecksum(checksum)
                .build();

        when(ingestionServiceClient.checkDuplicateByChecksum(checksum))
                .thenReturn(DuplicateCheckResponse.notDuplicate());
        when(versionRepository.findFirstByFileChecksum(checksum)).thenReturn(Optional.of(version));
        when(documentRepository.findById(docId)).thenReturn(Optional.of(doc));
        when(metadataServiceClient.getDocumentTitle(docId)).thenReturn("Test Doc");
        when(metadataServiceClient.getDocumentCategorySlug(docId)).thenReturn(null);

        DuplicateCheckResponse result = service.checkDuplicate(checksum);

        assertTrue(result.isDuplicate());
        assertEquals("BLOCK", result.action());
        assertEquals("file_checksum", result.detectionMethod());
        assertNotNull(result.existingDocument());
    }

    @Test
    @DisplayName("checkDuplicate returns not duplicate when no match found")
    void checkDuplicate_noMatch_returnsNotDuplicate() {
        String checksum = "unique-checksum";

        when(ingestionServiceClient.checkDuplicateByChecksum(checksum))
                .thenReturn(DuplicateCheckResponse.notDuplicate());
        when(versionRepository.findFirstByFileChecksum(checksum)).thenReturn(Optional.empty());

        DuplicateCheckResponse result = service.checkDuplicate(checksum);

        assertFalse(result.isDuplicate());
        assertNull(result.action());
    }

    @Test
    @DisplayName("checkDuplicate handles ingestion-service exception gracefully")
    void checkDuplicate_ingestionServiceException_fallsBackToLocal() {
        String checksum = "fallback-checksum";
        UUID docId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();

        Document doc = Document.builder()
                .id(docId)
                .originalFilename("test.pdf")
                .fileSizeBytes(1024L)
                .status(ProcessingStatus.READY)
                .createdAt(OffsetDateTime.now())
                .build();

        DocumentVersion version = DocumentVersion.builder()
                .id(versionId)
                .documentId(docId)
                .versionNumber(1)
                .fileChecksum(checksum)
                .build();

        when(ingestionServiceClient.checkDuplicateByChecksum(checksum))
                .thenThrow(new RuntimeException("Service unavailable"));
        when(versionRepository.findFirstByFileChecksum(checksum)).thenReturn(Optional.of(version));
        when(documentRepository.findById(docId)).thenReturn(Optional.of(doc));
        when(metadataServiceClient.getDocumentTitle(docId)).thenReturn("Test Doc");
        when(metadataServiceClient.getDocumentCategorySlug(docId)).thenReturn(null);

        DuplicateCheckResponse result = service.checkDuplicate(checksum);

        assertTrue(result.isDuplicate());
    }
}
