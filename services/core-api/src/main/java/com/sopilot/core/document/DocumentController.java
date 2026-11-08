package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.common.Cursor;
import com.sopilot.core.common.PageResponse;
import com.sopilot.core.document.DocumentService.DocumentPage;
import com.sopilot.core.document.DocumentService.DownloadUrl;
import com.sopilot.core.document.DocumentService.UploadResult;
import com.sopilot.core.security.AuthPrincipal;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Documents of the caller's workspace (TECH §5.5). Workspace and role come from the access token only. */
@RestController
@RequestMapping("/api/v1/documents")
public class DocumentController {

    private static final Set<String> STATUSES = Set.of("UPLOADED", "PROCESSING", "READY", "FAILED");

    private final DocumentService service;

    public DocumentController(DocumentService service) {
        this.service = service;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<DocumentView>> upload(AuthPrincipal principal,
                                                            @RequestParam("file") MultipartFile file,
                                                            @RequestParam(required = false) String visibility) {
        UploadResult result = service.upload(principal, file.getOriginalFilename(), bytes(file), visibility);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.of(result.document()));
    }

    @PostMapping(path = "/{id}/versions", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<DocumentView>> uploadVersion(AuthPrincipal principal, @PathVariable UUID id,
                                                                   @RequestParam("file") MultipartFile file) {
        UploadResult result = service.uploadVersion(principal, id, file.getOriginalFilename(), bytes(file));
        return ResponseEntity.status(result.created() ? HttpStatus.CREATED : HttpStatus.OK)
                .body(ApiResponse.of(result.document()));
    }

    @PostMapping("/{id}/retry")
    public ApiResponse<DocumentView> retry(AuthPrincipal principal, @PathVariable UUID id) {
        return ApiResponse.of(service.retry(principal, id));
    }

    @GetMapping
    public PageResponse<DocumentView> list(AuthPrincipal principal,
                                           @RequestParam(required = false) String status,
                                           @RequestParam(required = false) String q,
                                           @RequestParam(required = false) String cursor,
                                           @RequestParam(required = false) Integer limit) {
        if (status != null && !STATUSES.contains(status)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "Status filter is invalid.");
        }
        DocumentPage page = service.list(principal, status, q, Cursor.decode(cursor), Cursor.limit(limit));
        return PageResponse.of(page.items(), page.nextCursor(), page.hasMore());
    }

    @GetMapping("/{id}")
    public ApiResponse<DocumentView> get(AuthPrincipal principal, @PathVariable UUID id) {
        return ApiResponse.of(service.get(principal, id));
    }

    @PatchMapping("/{id}")
    public ApiResponse<DocumentView> update(AuthPrincipal principal, @PathVariable UUID id,
                                            @RequestBody Map<String, Object> patch) {
        return ApiResponse.of(service.update(principal, id, patch));
    }

    @GetMapping("/{id}/download-url")
    public ApiResponse<DownloadUrl> downloadUrl(AuthPrincipal principal, @PathVariable UUID id) {
        return ApiResponse.of(service.downloadUrl(principal, id));
    }

    @GetMapping("/{id}/versions")
    public ApiResponse<List<DocumentView.VersionHistory>> versions(AuthPrincipal principal, @PathVariable UUID id) {
        return ApiResponse.of(service.versions(principal, id));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(AuthPrincipal principal, @PathVariable UUID id) {
        service.delete(principal, id);
        return ResponseEntity.noContent().build();
    }

    private static byte[] bytes(MultipartFile file) {
        if (file.getSize() > UploadValidator.MAX_BYTES) {
            throw UploadValidator.tooLarge();
        }
        try {
            return file.getBytes();
        } catch (IOException e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "The file could not be read.");
        }
    }
}
