package com.poliwise.knowledge.exception;

import com.poliwise.knowledge.dto.DocumentDuplicateInfo;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.CONFLICT)
public class DuplicateDocumentException extends RuntimeException {
    private final DocumentDuplicateInfo existingDocument;
    private final String detectionMethod;

    public DuplicateDocumentException(String message, DocumentDuplicateInfo existingDocument, String method) {
        super(message);
        this.existingDocument = existingDocument;
        this.detectionMethod = method;
    }

    public DocumentDuplicateInfo getExistingDocument() {
        return existingDocument;
    }

    public String getDetectionMethod() {
        return detectionMethod;
    }
}
