package com.poliwise.knowledge.controller;

import com.poliwise.knowledge.dto.PolicyComparisonResponse;
import com.poliwise.knowledge.client.MetadataServiceClient;
import com.poliwise.knowledge.service.PolicyComparisonService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/documents")
public class PolicyComparisonController {

    private final PolicyComparisonService comparisonService;
    private final MetadataServiceClient metadataServiceClient;

    public PolicyComparisonController(PolicyComparisonService comparisonService,
                                      MetadataServiceClient metadataServiceClient) {
        this.comparisonService = comparisonService;
        this.metadataServiceClient = metadataServiceClient;
    }

    @PostMapping("/compare")
    @PreAuthorize("hasRole('ADMIN') or hasRole('MANAGER')")
    public ResponseEntity<PolicyComparisonResponse> compare(
            @RequestParam UUID document1Id,
            @RequestParam UUID document2Id) {

        metadataServiceClient.assertCanReadDocument(document1Id);
        metadataServiceClient.assertCanReadDocument(document2Id);
        PolicyComparisonResponse result = comparisonService.compare(document1Id, document2Id);
        return ResponseEntity.ok(result);
    }
}
