package com.sopilot.core.audit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.Cursor;
import com.sopilot.core.common.PageResponse;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tenancy.TenantTx;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** {@code GET /api/v1/audit-logs}: the workspace audit trail, OWNER only (FR-20, TECH §5.7). */
@RestController
@RequestMapping("/api/v1/audit-logs")
public class AuditController {

    private final AuditService audit;
    private final TenantTx tenant;
    private final ObjectMapper mapper;

    public AuditController(AuditService audit, TenantTx tenant, ObjectMapper mapper) {
        this.audit = audit;
        this.tenant = tenant;
        this.mapper = mapper;
    }

    @GetMapping
    public PageResponse<AuditEntryView> list(
            AuthPrincipal principal,
            @RequestParam(required = false) String action,
            @RequestParam(required = false) UUID actorId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime to,
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        principal.requireOwner();
        AuditService.Page page = tenant.run(principal, () ->
                audit.list(principal, action, actorId, from, to, Cursor.decode(cursor), Cursor.limit(limit)));
        List<AuditEntryView> data = page.entries().stream().map(this::view).toList();
        return PageResponse.of(data, page.nextCursor(), page.hasMore());
    }

    private AuditEntryView view(AuditService.Entry e) {
        try {
            JsonNode details = mapper.readTree(e.details());
            return new AuditEntryView(e.id(), e.actorId(), e.action(), e.targetType(), e.targetId(), details,
                    e.traceId(), e.createdAt());
        } catch (Exception ex) {
            throw new IllegalStateException("Stored audit details are not valid JSON");
        }
    }

    public record AuditEntryView(UUID id, UUID actorId, String action, String targetType, UUID targetId,
                                 JsonNode details, String traceId, OffsetDateTime createdAt) {
    }
}
