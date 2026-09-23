package com.poliwise.knowledge.service;

import com.poliwise.knowledge.dto.PolicyComparisonResponse;
import com.poliwise.knowledge.dto.PolicyComparisonResponse.DiffSection;
import com.poliwise.knowledge.entity.Document;
import com.poliwise.knowledge.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class PolicyComparisonService {

    private static final Logger log = LoggerFactory.getLogger(PolicyComparisonService.class);

    private final DocumentRepository documentRepository;
    private final DocumentParsingService parsingService;
    private final StorageService storageService;

    public PolicyComparisonService(
            DocumentRepository documentRepository,
            DocumentParsingService parsingService,
            StorageService storageService) {
        this.documentRepository = documentRepository;
        this.parsingService = parsingService;
        this.storageService = storageService;
    }

    public PolicyComparisonResponse compare(UUID doc1Id, UUID doc2Id) {
        Document doc1 = documentRepository.findById(doc1Id)
                .orElseThrow(() -> new RuntimeException("Document not found: " + doc1Id));
        Document doc2 = documentRepository.findById(doc2Id)
                .orElseThrow(() -> new RuntimeException("Document not found: " + doc2Id));

        String text1 = getDocumentText(doc1);
        String text2 = getDocumentText(doc2);

        List<DiffSection> added = new ArrayList<>();
        List<DiffSection> removed = new ArrayList<>();
        List<DiffSection> modified = new ArrayList<>();

        // Simple line-by-line diff
        String[] lines1 = text1.split("\\n");
        String[] lines2 = text2.split("\\n");

        Set<String> set1 = Arrays.stream(lines1).map(String::trim).filter(s -> !s.isEmpty()).collect(Collectors.toSet());
        Set<String> set2 = Arrays.stream(lines2).map(String::trim).filter(s -> !s.isEmpty()).collect(Collectors.toSet());

        // Find removed (in doc1 but not in doc2)
        for (String line : set1) {
            if (!set2.contains(line)) {
                removed.add(new DiffSection("Removed section", line, null, "REMOVED"));
            }
        }

        // Find added (in doc2 but not in doc1)
        for (String line : set2) {
            if (!set1.contains(line)) {
                added.add(new DiffSection("Added section", null, line, "ADDED"));
            }
        }

        int totalChanges = added.size() + removed.size() + modified.size();

        log.info("Policy comparison: doc1={}, doc2={}, added={}, removed={}, modified={}",
                doc1Id, doc2Id, added.size(), removed.size(), modified.size());

        return new PolicyComparisonResponse(
                doc1Id.toString(),
                doc2Id.toString(),
                doc1.getOriginalFilename(),
                doc2.getOriginalFilename(),
                added,
                removed,
                modified,
                totalChanges
        );
    }

    private String getDocumentText(Document document) {
        // Use cached text if available
        if (document.getExtractedText() != null && !document.getExtractedText().isBlank()) {
            return document.getExtractedText();
        }

        // Otherwise parse from storage
        try {
            var stream = storageService.downloadFile(document.getFileKey());
            var result = parsingService.parse(stream, document.getFileType(), document.getOriginalFilename());
            return result.text();
        } catch (Exception e) {
            log.error("Failed to get document text: {}", e.getMessage());
            return "";
        }
    }
}