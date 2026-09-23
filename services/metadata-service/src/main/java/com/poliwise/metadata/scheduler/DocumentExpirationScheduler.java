package com.poliwise.metadata.scheduler;

import com.poliwise.metadata.dto.DocumentMetadataResponse;
import com.poliwise.metadata.enums.DocumentStatus;
import com.poliwise.metadata.service.DocumentMetadataService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.List;

@Component
public class DocumentExpirationScheduler {

    private static final Logger log = LoggerFactory.getLogger(DocumentExpirationScheduler.class);

    private final DocumentMetadataService metadataService;

    public DocumentExpirationScheduler(DocumentMetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @Scheduled(cron = "${metadata.expiration.cron:0 0 1 * * ?}")
    public void processExpiredDocuments() {
        log.info("Starting document expiration check...");

        List<DocumentMetadataResponse> expired = metadataService.findExpired();

        for (var metadata : expired) {
            if (metadata.status() != DocumentStatus.EXPIRED) {
                log.info("Expiring document: id={}, title={}, expiryDate={}",
                        metadata.id(), metadata.title(), metadata.expiryDate());
                // Archive instead of deleting - metadata can be kept for audit
                try {
                    metadataService.archive(metadata.id(), metadata.updatedBy());
                    log.info("Document expired and archived: id={}", metadata.id());
                } catch (Exception e) {
                    log.error("Failed to expire document {}: {}", metadata.id(), e.getMessage());
                }
            }
        }

        log.info("Document expiration check completed. Processed {} documents.", expired.size());
    }
}