package com.poliwise.metadata.controller;

import com.poliwise.metadata.dto.DocumentMetadataResponse;
import com.poliwise.metadata.event.DocumentEventConsumer;
import com.poliwise.metadata.service.DocumentMetadataService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/metadata/events")
public class EventConsumerController {

    private final DocumentMetadataService metadataService;

    public EventConsumerController(DocumentMetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @PostMapping("/document-uploaded")
    public ResponseEntity<Void> handleDocumentUploaded(
            @RequestParam UUID documentId,
            @RequestParam String fileName,
            @RequestParam String fileType,
            @RequestParam(required = false) Long fileSizeBytes,
            @RequestParam(required = false) String fileKey,
            @RequestParam(required = false) UUID uploadedBy) {

        // This endpoint receives document uploaded events from knowledge-service
        // In a real scenario, this would be handled by a RabbitMQ listener
        return ResponseEntity.ok().build();
    }

    @PostMapping("/document-deleted")
    public ResponseEntity<Void> handleDocumentDeleted(
            @RequestParam UUID documentId,
            @RequestParam(required = false) UUID deletedBy) {

        // This endpoint receives document deleted events from knowledge-service
        return ResponseEntity.ok().build();
    }
}