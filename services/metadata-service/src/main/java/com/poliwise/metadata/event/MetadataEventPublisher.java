package com.poliwise.metadata.event;

import com.poliwise.metadata.config.RabbitMQConfig;
import com.poliwise.metadata.dto.event.DocumentDeletedEvent;
import com.poliwise.metadata.dto.event.DocumentUploadedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class MetadataEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(MetadataEventPublisher.class);

    private final RabbitTemplate rabbitTemplate;

    public MetadataEventPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishDocumentUploaded(DocumentUploadedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.METADATA_EXCHANGE,
                    RabbitMQConfig.DOCUMENT_ROUTING_KEY_UPLOADED,
                    event
            );
            log.info("Published DocumentUploadedEvent: documentId={}", event.documentId());
        } catch (Exception e) {
            log.error("Failed to publish DocumentUploadedEvent: {}", e.getMessage(), e);
        }
    }

    public void publishDocumentDeleted(DocumentDeletedEvent event) {
        try {
            rabbitTemplate.convertAndSend(
                    RabbitMQConfig.METADATA_EXCHANGE,
                    RabbitMQConfig.DOCUMENT_ROUTING_KEY_DELETED,
                    event
            );
            log.info("Published DocumentDeletedEvent: documentId={}", event.documentId());
        } catch (Exception e) {
            log.error("Failed to publish DocumentDeletedEvent: {}", e.getMessage(), e);
        }
    }
}