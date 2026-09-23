package com.poliwise.knowledge.controller;

import com.poliwise.knowledge.dto.*;
import com.poliwise.knowledge.entity.Document;
import com.poliwise.knowledge.enums.ChunkingStrategy;
import com.poliwise.knowledge.enums.EmbeddingModel;
import com.poliwise.knowledge.enums.FileType;
import com.poliwise.knowledge.service.DocumentManagementService;
import com.poliwise.knowledge.service.MetadataContextService;
import com.poliwise.knowledge.service.MetadataSuggestionService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentManagementService documentManagementService;
    private final MetadataContextService metadataContextService;
    private final MetadataSuggestionService metadataSuggestionService;

    // ===== 1. Upload Document =====
    @PostMapping(path = {"", "/upload"}, consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentResponse> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "changelog", required = false, defaultValue = "") String changelog,
            @RequestParam(value = "language", required = false, defaultValue = "vi") String language,
            HttpServletRequest httpRequest) {

        UUID uploadedBy = getCurrentUserId(httpRequest);

        UploadDocumentRequest request = new UploadDocumentRequest(
                file.getOriginalFilename(),
                detectFileType(file.getOriginalFilename()),
                file.getSize(),
                file.getContentType(),
                ChunkingStrategy.SENTENCE,
                512,
                50,
                EmbeddingModel.MULTILINGUAL_E5_LARGE,
                language
        );

        Document document = documentManagementService.upload(
                file, request, uploadedBy,
                getClientIp(httpRequest),
                httpRequest.getHeader("User-Agent")
        );

        // Phase 1: Get metadata suggestion
        MetadataSuggestionResponse suggestion = getMetadataSuggestion(document);

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(toResponse(document, suggestion));
    }

    // ===== 2. Upload New Version =====
    @PostMapping(value = "/{documentId}/versions", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DocumentVersionResponse> uploadNewVersion(
            @PathVariable UUID documentId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "changelog", required = false, defaultValue = "") String changelog,
            @RequestParam(value = "language", required = false) String language,
            HttpServletRequest httpRequest) {

        UUID uploadedBy = getCurrentUserId(httpRequest);

        Document document = documentManagementService.uploadNewVersion(
                documentId, file, changelog, uploadedBy,
                getClientIp(httpRequest),
                httpRequest.getHeader("User-Agent")
        );

        // Get the latest version
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);

        // Return the latest version response
        DocumentVersionResponse latestVersion = detail.versions().isEmpty() ? null :
                detail.versions().stream()
                        .filter(v -> v.versionNumber().equals(document.getCurrentVersion()))
                        .findFirst()
                        .orElse(null);

        if (latestVersion != null) {
            return ResponseEntity.ok(latestVersion);
        }

        // Fallback: create version response from document
        DocumentVersionResponse response = new DocumentVersionResponse(
                UUID.randomUUID(),
                documentId,
                document.getCurrentVersion(),
                document.getFileKey(),
                document.getFileSizeBytes(),
                changelog,
                uploadedBy,
                document.getUpdatedAt()
        );
        return ResponseEntity.ok(response);
    }

    // ===== Stats (internal service) =====
    @GetMapping("/stats")
    public ResponseEntity<DocumentStatsResponse> getStats() {
        return ResponseEntity.ok(documentManagementService.getStats());
    }

    // ===== 3. List Documents (Search + Filter + Pagination) =====
    @GetMapping
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<PagedDocumentResponse> list(
            @RequestParam(required = false) Integer page,
            @RequestParam(required = false) Integer size,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String fileType,
            @RequestParam(required = false) UUID uploadedBy,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) UUID categoryId,
            @RequestParam(required = false) String sortBy,
            @RequestParam(required = false, defaultValue = "desc") String sortOrder,
            HttpServletRequest httpRequest) {

        FileType parsedFileType = null;
        if (fileType != null && !fileType.isBlank()) {
            try {
                parsedFileType = FileType.valueOf(fileType.toUpperCase());
            } catch (IllegalArgumentException ignored) {}
        }

        java.time.LocalDate start = null;
        java.time.LocalDate end = null;
        try {
            if (startDate != null && !startDate.isBlank()) start = java.time.LocalDate.parse(startDate);
            if (endDate != null && !endDate.isBlank()) end = java.time.LocalDate.parse(endDate);
        } catch (Exception ignored) {}

        DocumentSearchRequest searchRequest = new DocumentSearchRequest(
                page, size, search, parsedFileType, uploadedBy,
                start, end, status, categoryId, null, sortBy, sortOrder
        );

        Page<Document> documents = documentManagementService.searchDocuments(searchRequest);

        // Filter documents by access rules
        List<UUID> documentIds = documents.getContent().stream()
                .map(Document::getId)
                .toList();

        java.util.Set<UUID> accessibleIds = documentManagementService.filterAccessibleDocuments(documentIds);

        List<DocumentListItem> items = documents.getContent().stream()
                .filter(doc -> accessibleIds.contains(doc.getId()))
                .map(this::toListItem)
                .collect(Collectors.toList());

        // Adjust total count to reflect accessible documents only
        long accessibleTotal = documents.getTotalElements() > documents.getContent().size()
                ? documents.getTotalElements() // Approximate - actual count may be lower
                : items.size();

        PagedDocumentResponse response = new PagedDocumentResponse(
                items,
                documents.getNumber() + 1,
                documents.getSize(),
                accessibleTotal,
                documents.getTotalPages()
        );

        return ResponseEntity.ok(response);
    }

    // ===== 4. Get Document Detail =====
    @GetMapping("/{documentId}")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<DocumentDetailResponse> getDetail(
            @PathVariable UUID documentId,
            HttpServletRequest httpRequest) {
        // Check access before returning detail
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        return ResponseEntity.ok(detail);
    }

    // ===== 5. Download Document =====
    @GetMapping("/{documentId}/download")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<StreamingResponseBody> download(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        StreamingResponseBody stream = documentManagementService.downloadDocument(documentId);

        String filename = detail.originalFilename() != null ? detail.originalFilename() : "document";
        String contentType = detail.mimeType() != null ? detail.mimeType() : "application/octet-stream";

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, encodeFilename(filename))
                .contentType(MediaType.parseMediaType(contentType))
                .contentLength(detail.fileSizeBytes() != null ? detail.fileSizeBytes() : 0)
                .body(stream);
    }

    // ===== 6. Get Download URL (Signed URL) =====
    @GetMapping("/{documentId}/url")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<DownloadUrlResponse> getDownloadUrl(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        String url = documentManagementService.getDownloadUrl(documentId);
        return ResponseEntity.ok(new DownloadUrlResponse(url));
    }

    // ===== 6b. Preview Document (returns binary for iframe embedding) =====
    @GetMapping("/{documentId}/preview")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<byte[]> getPreview(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        byte[] content = documentManagementService.getDocumentBytes(documentId);

        String contentType = detail.mimeType() != null ? detail.mimeType() : "application/octet-stream";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, contentType)
                .header(HttpHeaders.CACHE_CONTROL, "private, max-age=3600")
                .body(content);
    }

    // ===== 6c. Preview Specific Version =====
    @GetMapping("/{documentId}/versions/{versionNumber}/preview")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<byte[]> getVersionPreview(
            @PathVariable UUID documentId,
            @PathVariable Integer versionNumber,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        detail.versions().stream()
                .filter(v -> v.versionNumber().equals(versionNumber))
                .findFirst()
                .orElseThrow(() -> new com.poliwise.knowledge.exception.ResourceNotFoundException("Version not found: " + versionNumber));
        byte[] content = documentManagementService.getDocumentVersionBytes(documentId, versionNumber);

        String contentType = detail.mimeType() != null ? detail.mimeType() : "application/octet-stream";
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, contentType)
                .header(HttpHeaders.CACHE_CONTROL, "private, max-age=3600")
                .body(content);
    }

    // ===== 7. Download Specific Version =====
    @GetMapping("/{documentId}/versions/{versionNumber}/download")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<StreamingResponseBody> downloadVersion(
            @PathVariable UUID documentId,
            @PathVariable Integer versionNumber,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        DocumentVersionResponse version = detail.versions().stream()
                .filter(v -> v.versionNumber().equals(versionNumber))
                .findFirst()
                .orElseThrow(() -> new com.poliwise.knowledge.exception.ResourceNotFoundException("Version not found: " + versionNumber));

        StreamingResponseBody stream = documentManagementService.downloadVersion(documentId, versionNumber);

        String filename = detail.originalFilename() != null ? detail.originalFilename() : "document";
        String contentType = detail.mimeType() != null ? detail.mimeType() : "application/octet-stream";

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, encodeFilename("v" + versionNumber + "-" + filename))
                .contentType(MediaType.parseMediaType(contentType))
                .contentLength(version.fileSizeBytes() != null ? version.fileSizeBytes() : 0)
                .body(stream);
    }

    // ===== 7b. Get Extracted Text Content =====
    @GetMapping("/{documentId}/content")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<String> getDocumentContent(
            @PathVariable UUID documentId,
            @RequestParam(required = false) Integer version,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        String content = documentManagementService.getExtractedText(documentId, version);
        return ResponseEntity.ok(content);
    }

    // ===== 8. Cancel Upload (STAGING only) =====
    @DeleteMapping("/{documentId}/cancel")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> cancelUpload(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        UUID cancelledBy = getCurrentUserId(httpRequest);
        documentManagementService.cancelUpload(documentId, cancelledBy,
                getClientIp(httpRequest), httpRequest.getHeader("User-Agent"));
        return ResponseEntity.noContent().build();
    }

    // ===== 9. Soft Delete =====
    @DeleteMapping("/{documentId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> softDelete(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        UUID deletedBy = getCurrentUserId(httpRequest);
        documentManagementService.softDelete(documentId, deletedBy,
                getClientIp(httpRequest), httpRequest.getHeader("User-Agent"));
        return ResponseEntity.noContent().build();
    }

    // ===== 10. Get Version History =====
    @GetMapping("/{documentId}/versions")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<List<DocumentVersionResponse>> getVersions(
            @PathVariable UUID documentId,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        DocumentDetailResponse detail = documentManagementService.getDocumentDetail(documentId);
        return ResponseEntity.ok(detail.versions());
    }

    @GetMapping("/{documentId}/versions/{versionNumber}/content")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<Map<String, String>> getContent(
            @PathVariable UUID documentId,
            @PathVariable Integer versionNumber,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);
        String content = documentManagementService.getExtractedText(documentId, versionNumber);
        return ResponseEntity.ok(Map.of("content", content != null ? content : ""));
    }

    // ===== 11. Get Audit Logs =====
    @GetMapping("/{documentId}/audit-logs")
    @PreAuthorize("hasAnyRole('USER', 'MANAGER', 'ADMIN')")
    public ResponseEntity<PagedAuditLogResponse> getAuditLogs(
            @PathVariable UUID documentId,
            @RequestParam(required = false) UUID actorId,
            @RequestParam(required = false) String action,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false, defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "20") int size,
            HttpServletRequest httpRequest) {
        documentManagementService.checkDocumentAccessOrThrow(documentId);

        java.time.LocalDate start = null;
        java.time.LocalDate end = null;
        try {
            if (startDate != null && !startDate.isBlank()) start = java.time.LocalDate.parse(startDate);
            if (endDate != null && !endDate.isBlank()) end = java.time.LocalDate.parse(endDate);
        } catch (Exception ignored) {}

        Page<DocumentAuditLogResponse> logs = documentManagementService.getAuditLogs(
                documentId, actorId, action, start, end, page, size);

        return ResponseEntity.ok(new PagedAuditLogResponse(
                logs.getContent(),
                logs.getNumber() + 1,
                logs.getSize(),
                logs.getTotalElements(),
                logs.getTotalPages()
        ));
    }

    // ===== 12. Trigger Processing =====
    @PostMapping("/{documentId}/process")
    // @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> process(@PathVariable UUID documentId, HttpServletRequest httpRequest) {
        UUID processedBy = getCurrentUserId(httpRequest);
        documentManagementService.triggerIngestion(documentId, processedBy);
        return ResponseEntity.accepted().build();
    }

    // ===== 13. Confirm Metadata =====
    @PostMapping("/{documentId}/confirm")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ConfirmResultResponse> confirm(
            @PathVariable UUID documentId,
            @Valid @RequestBody DocumentConfirmRequest request,
            HttpServletRequest httpRequest) {
        UUID confirmedBy = getCurrentUserId(httpRequest);

        // Use sync confirm flow with ingestion polling
        ConfirmResultResponse result = documentManagementService.confirmMetadataSync(documentId, request, confirmedBy);
        return ResponseEntity.ok(result);
    }

    // ===== Pre-confirm duplicate check =====
    @GetMapping("/check-duplicate")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DuplicateCheckResponse> checkDuplicate(
            @RequestParam("checksum") String fileChecksum) {
        DuplicateCheckResponse result = documentManagementService.checkDuplicate(fileChecksum);
        return ResponseEntity.ok(result);
    }

    // ===== Helper Methods =====

    private DocumentResponse toResponse(Document d, MetadataSuggestionResponse suggestion) {
        if (d == null) return null;
        return new DocumentResponse(
                d.getId(),
                d.getOriginalFilename(),
                d.getFileType(),
                d.getFileSizeBytes(),
                d.getMimeType(),
                d.getStatus(),
                d.getCurrentVersion(),
                d.getPageCount(),
                d.getWordCount(),
                d.getLanguage(),
                d.getOcrRequired(),
                d.getChunkingStrategy(),
                d.getChunkSize(),
                d.getChunkOverlap(),
                d.getEmbeddingModel(),
                d.getUploadedBy(),
                d.getCreatedAt(),
                d.getUpdatedAt(),
                suggestion != null ? suggestion.language() : null,
                suggestion != null ? suggestion.categorySlug() : null,
                suggestion != null ? suggestion.title() : null,
                suggestion != null ? suggestion.description() : null,
                suggestion != null ? suggestion.tags() : List.of(),
                suggestion != null ? suggestion.isPolicy() : null
        );
    }

    private DocumentListItem toListItem(Document d) {
        return new DocumentListItem(
                d.getId(),
                d.getOriginalFilename(),
                d.getFileType() != null ? d.getFileType().toString() : null,
                d.getFileSizeBytes(),
                d.getStatus() != null ? d.getStatus().toString() : null,
                d.getCurrentVersion(),
                d.getLanguage(),
                d.getUploadedBy(),
                d.getCreatedAt(),
                d.getUpdatedAt()
        );
    }

    private MetadataSuggestionResponse getMetadataSuggestion(Document document) {
        try {
            List<String> categorySlugs = metadataContextService.fetchActiveCategorySlugs();
            List<String> topTags = metadataContextService.fetchTopTagNames(20);

            MetadataSuggestionRequest suggestRequest = new MetadataSuggestionRequest(
                    document.getFileKey(),
                    document.getBucketName(),
                    categorySlugs,
                    topTags
            );

            return metadataSuggestionService.suggest(suggestRequest);
        } catch (Exception e) {
            return null;
        }
    }

    private FileType detectFileType(String filename) {
        if (filename == null) return FileType.PDF;
        String lower = filename.toLowerCase();
        if (lower.endsWith(".pdf")) return FileType.PDF;
        if (lower.endsWith(".docx")) return FileType.DOCX;
        if (lower.endsWith(".xlsx")) return FileType.XLSX;
        if (lower.endsWith(".doc")) return FileType.DOC;
        if (lower.endsWith(".xls")) return FileType.XLS;
        if (lower.endsWith(".txt")) return FileType.TXT;
        if (lower.endsWith(".md")) return FileType.MD;
        if (lower.endsWith(".png")) return FileType.PNG;
        if (lower.endsWith(".jpg")) return FileType.JPG;
        if (lower.endsWith(".jpeg")) return FileType.JPEG;
        return FileType.UNKNOWN;
    }

    private UUID getCurrentUserId(HttpServletRequest request) {
        var auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof com.poliwise.knowledge.security.JwtAuthenticationToken jwtToken) {
            return jwtToken.getUserId();
        }
        throw new org.springframework.security.access.AccessDeniedException("User not authenticated");
    }

    /**
     * Encode filename for Content-Disposition header using RFC 5987 (UTF-8 extended).
     * Provides both ASCII fallback and RFC 5987 encoded version for cross-browser compatibility.
     */
    private String encodeFilename(String filename) {
        try {
            // ASCII fallback (replace non-printable/problematic chars)
            StringBuilder ascii = new StringBuilder();
            for (char c : filename.toCharArray()) {
                if (c >= 0x20 && c <= 0x7E && c != '"') {
                    ascii.append(c);
                } else {
                    ascii.append('_');
                }
            }
            // RFC 5987 encoding: filename*=UTF-8''<percent-encoded>
            String encoded = new String(filename.getBytes(java.nio.charset.StandardCharsets.UTF_8), java.nio.charset.StandardCharsets.US_ASCII);
            StringBuilder percentEncoded = new StringBuilder();
            for (char ch : encoded.toCharArray()) {
                if (ch >= 'A' && ch <= 'Z' || ch >= 'a' && ch <= 'z' || ch >= '0' && ch <= '9'
                        || ch == '-' || ch == '_' || ch == '.' || ch == '~') {
                    percentEncoded.append(ch);
                } else {
                    percentEncoded.append(String.format("%%%02X", (int) ch));
                }
            }
            return "attachment; filename=\"" + ascii + "\"; filename*=UTF-8''" + percentEncoded;
        } catch (Exception e) {
            return "attachment; filename=\"document\"";
        }
    }

    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isBlank()) {
            return xForwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}

// ===== Additional Response Records =====

record PagedDocumentResponse(
        List<DocumentListItem> data,
        int page,
        int limit,
        long total,
        int totalPages
) {}

record DocumentListItem(
        UUID id,
        String originalFilename,
        String fileType,
        Long fileSizeBytes,
        String status,
        Integer currentVersion,
        String language,
        UUID uploadedBy,
        java.time.OffsetDateTime createdAt,
        java.time.OffsetDateTime updatedAt
) {}

record PagedAuditLogResponse(
        List<DocumentAuditLogResponse> data,
        int page,
        int limit,
        long total,
        int totalPages
) {}

record DownloadUrlResponse(String url) {}
