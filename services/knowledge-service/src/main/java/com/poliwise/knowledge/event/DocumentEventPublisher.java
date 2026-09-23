package com.poliwise.knowledge.event;

import com.poliwise.knowledge.config.RabbitMQConfig;
import com.poliwise.knowledge.dto.event.DocumentDeletedEvent;
import com.poliwise.knowledge.dto.event.DocumentUploadedEvent;
import com.poliwise.knowledge.dto.event.DocumentVersionCreatedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class DocumentEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(DocumentEventPublisher.class);

    private final RabbitTemplate rabbitTemplate;

    public DocumentEventPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishDocumentUploaded(DocumentUploadedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.KNOWLEDGE_EXCHANGE,
                    RabbitMQConfig.DOCUMENT_ROUTING_KEY_UPLOADED,
                    Map.of(
                            "routingKey", RabbitMQConfig.DOCUMENT_ROUTING_KEY_UPLOADED,
                            "documentId", event.documentId(),
                            "documentName", event.fileName(),
                            "uploadedBy", event.uploadedBy(),
                            "fileSizeBytes", event.fileSizeBytes(),
                            "fileKey", event.fileKey()
                    )
            );
            log.info("Published DocumentUploadedEvent: documentId={}, fileName={}",
                    event.documentId(), event.fileName());
        } catch (Exception e) {
            log.error("Failed to publish DocumentUploadedEvent: {}", e.getMessage(), e);
        }
    }

    public void publishDocumentDeleted(DocumentDeletedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.KNOWLEDGE_EXCHANGE,
                    RabbitMQConfig.DOCUMENT_ROUTING_KEY_DELETED,
                    Map.of(
                            "routingKey", RabbitMQConfig.DOCUMENT_ROUTING_KEY_DELETED,
                            "documentId", event.documentId(),
                            "documentName", event.documentName(),
                            "deletedBy", event.deletedBy()
                    )
            );
            log.info("Published DocumentDeletedEvent: documentId={}", event.documentId());
        } catch (Exception e) {
            log.error("Failed to publish DocumentDeletedEvent: {}", e.getMessage(), e);
        }
    }

    public void publishDocumentVersionCreated(DocumentVersionCreatedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.KNOWLEDGE_EXCHANGE,
                    RabbitMQConfig.DOCUMENT_ROUTING_KEY_VERSION_CREATED,
                    Map.of(
                            "routingKey", RabbitMQConfig.DOCUMENT_ROUTING_KEY_VERSION_CREATED,
                            "documentId", event.documentId(),
                            "documentName", event.documentName(),
                            "newVersionNumber", event.newVersionNumber(),
                            "changelog", event.changelog(),
                            "createdBy", event.createdBy()
                    )
            );
            log.info("Published DocumentVersionCreatedEvent: documentId={}, version={}",
                    event.documentId(), event.newVersionNumber());
        } catch (Exception e) {
            log.error("Failed to publish DocumentVersionCreatedEvent: {}", e.getMessage(), e);
        }
    }

    /**
     * Publish ingestion.requested event to trigger the Python ingestion pipeline.
     * The Python consumer expects payload with: job_id, document_id,
     * document_version_id, file_key, bucket_name, metadata.
     */
    public void publishIngestionRequested(Map<String, Object> payload) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.KNOWLEDGE_EXCHANGE,
                    RabbitMQConfig.INGESTION_ROUTING_KEY_REQUESTED,
                    Map.of("payload", payload)
            );
            log.info("Published ingestion.requested: documentId={}, jobId={}",
                    payload.get("document_id"), payload.get("job_id"));
        } catch (Exception e) {
            log.error("Failed to publish ingestion.requested: {}", e.getMessage(), e);
        }
    }
}