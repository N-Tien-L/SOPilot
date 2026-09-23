package com.poliwise.knowledge.repository;

import com.poliwise.knowledge.entity.Document;
import com.poliwise.knowledge.enums.FileType;
import com.poliwise.knowledge.enums.ProcessingStatus;
import org.springframework.data.jpa.domain.Specification;

import java.util.ArrayList;
import java.util.List;

public class DocumentSpecifications {

    public static Specification<Document> hasDeletedAtNull() {
        return (root, query, cb) -> cb.isNull(root.get("deletedAt"));
    }

    public static Specification<Document> hasStatus(ProcessingStatus status) {
        return (root, query, cb) -> cb.equal(root.get("status"), status);
    }

    public static Specification<Document> hasStatusIn(List<ProcessingStatus> statuses) {
        return (root, query, cb) -> root.get("status").in(statuses);
    }

    public static Specification<Document> hasFileType(String fileType) {
        return (root, query, cb) -> {
            if (fileType == null || fileType.isBlank()) return null;
            try {
                FileType enumValue = FileType.valueOf(fileType.toUpperCase());
                return cb.equal(root.get("fileType"), enumValue);
            } catch (IllegalArgumentException e) {
                return cb.conjunction();
            }
        };
    }

    public static Specification<Document> hasUploadedBy(String uploadedBy) {
        return (root, query, cb) -> cb.equal(root.get("uploadedBy"), uploadedBy);
    }

    public static Specification<Document> searchByFilename(String keyword) {
        return (root, query, cb) -> {
            if (keyword == null || keyword.isBlank()) return null;
            return cb.like(cb.lower(root.get("originalFilename")), "%" + keyword.toLowerCase() + "%");
        };
    }

    public static Specification<Document> createdBetween(java.time.LocalDate startDate, java.time.LocalDate endDate) {
        return (root, query, cb) -> {
            if (startDate == null && endDate == null) return null;
            if (startDate != null && endDate != null) {
                return cb.between(
                        root.get("createdAt"),
                        startDate.atStartOfDay().atZone(java.time.ZoneOffset.UTC).toOffsetDateTime(),
                        endDate.plusDays(1).atStartOfDay().atZone(java.time.ZoneOffset.UTC).toOffsetDateTime()
                );
            }
            if (startDate != null) {
                return cb.greaterThanOrEqualTo(
                        root.get("createdAt"),
                        startDate.atStartOfDay().atZone(java.time.ZoneOffset.UTC).toOffsetDateTime()
                );
            }
            return cb.lessThan(
                    root.get("createdAt"),
                    endDate.plusDays(1).atStartOfDay().atZone(java.time.ZoneOffset.UTC).toOffsetDateTime()
            );
        };
    }

    public static Specification<Document> notDeleted() {
        return hasDeletedAtNull();
    }

    public static Specification<Document> isActive() {
        return hasStatusIn(List.of(
                ProcessingStatus.STAGING,
                ProcessingStatus.UPLOADED,
                ProcessingStatus.PARSED,
                ProcessingStatus.CHUNKED,
                ProcessingStatus.EMBEDDED,
                ProcessingStatus.INDEXED,
                ProcessingStatus.READY
        ));
    }

    public static Specification<Document> buildSpecification(
            String search,
            String fileType,
            String uploadedBy,
            java.time.LocalDate startDate,
            java.time.LocalDate endDate,
            String status
    ) {
        List<Specification<Document>> specs = new ArrayList<>();
        specs.add(notDeleted());

        if (search != null && !search.isBlank()) {
            specs.add(searchByFilename(search));
        }
        if (fileType != null && !fileType.isBlank()) {
            specs.add(hasFileType(fileType));
        }
        if (uploadedBy != null && !uploadedBy.isBlank()) {
            specs.add(hasUploadedBy(uploadedBy));
        }
        if (startDate != null || endDate != null) {
            specs.add(createdBetween(startDate, endDate));
        }
        if (status != null && !status.isBlank()) {
            try {
                specs.add(hasStatus(ProcessingStatus.valueOf(status.toUpperCase())));
            } catch (IllegalArgumentException ignored) {}
        }

        Specification<Document> result = specs.isEmpty()
                ? Specification.where(null)
                : specs.get(0);
        for (int i = 1; i < specs.size(); i++) {
            result = result.and(specs.get(i));
        }
        return result;
    }
}
