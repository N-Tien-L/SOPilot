package com.poliwise.metadata.exception;

import java.util.UUID;

public class ResourceNotFoundException extends RuntimeException {
    private final String resourceType;
    private final UUID resourceId;

    public ResourceNotFoundException(String resourceType, UUID resourceId) {
        super(resourceType + " not found with id: " + resourceId);
        this.resourceType = resourceType;
        this.resourceId = resourceId;
    }

    public ResourceNotFoundException(String message) {
        super(message);
        this.resourceType = null;
        this.resourceId = null;
    }

    public String getResourceType() { return resourceType; }
    public UUID getResourceId() { return resourceId; }
}
