package com.poliwise.metadata.event;

import com.poliwise.metadata.config.RabbitMQConfig;
import com.poliwise.metadata.dto.event.DocumentDeletedEvent;
import com.poliwise.metadata.dto.event.DocumentUploadedEvent;
import com.poliwise.metadata.service.DocumentMetadataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Component
public class DocumentEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(DocumentEventConsumer.class);

    private final DocumentMetadataService metadataService;

    public DocumentEventConsumer(DocumentMetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @RabbitListener(queues = RabbitMQConfig.DOCUMENT_UPLOADED_QUEUE)
    public void handleDocumentUploaded(DocumentUploadedEvent event) {
        log.info("Received DocumentUploadedEvent: documentId={}, fileName={}",
                event.documentId(), event.fileName());
        // When a document is uploaded to knowledge-service,
        // we can optionally create metadata here or just log
        // Metadata creation is typically manual via API
    }

    @RabbitListener(queues = RabbitMQConfig.DOCUMENT_DELETED_QUEUE)
    public void handleDocumentDeleted(DocumentDeletedEvent event) {
        log.info("Received DocumentDeletedEvent: documentId={}", event.documentId());
        // Clean up metadata when document is deleted
        try {
            var metadata = metadataService.getByDocumentId(event.documentId());
            metadataService.softDelete(metadata.id());
        } catch (Exception e) {
            log.warn("Could not find metadata for deleted document: {}", event.documentId());
        }
    }
}