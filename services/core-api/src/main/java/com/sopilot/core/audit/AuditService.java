package com.sopilot.core.audit;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sopilot.core.common.Cursor;
import com.sopilot.core.common.TraceIdFilter;
import com.sopilot.core.common.UuidV7;
import com.sopilot.core.security.AuthPrincipal;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Append-only audit trail (FR-20, TECH §3.6). Callers invoke it inside the transaction of the change
 * it describes, with the RLS context already bound, so the entry commits or rolls back together with
 * the change. {@code details} must never hold tokens or document content.
 */
@Service
public class AuditService {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public AuditService(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    public void record(AuthPrincipal actor, String action, String targetType, UUID targetId,
                       Map<String, Object> details) {
        record(actor.workspaceId(), actor.userId(), action, targetType, targetId, details);
    }

    /** {@code actorId} is null for system-originated events. */
    public void record(UUID workspaceId, UUID actorId, String action, String targetType, UUID targetId,
                       Map<String, Object> details) {
        jdbc.update("INSERT INTO core.audit_logs (id, workspace_id, actor_id, action, target_type, target_id, "
                        + "details, trace_id) VALUES (?, ?, ?, ?, ?, ?, ?::jsonb, ?)",
                UuidV7.generate(), workspaceId, actorId, action, targetType, targetId,
                json(details == null ? Map.of() : details), TraceIdFilter.currentTraceId());
    }

    public Page list(AuthPrincipal principal, String action, UUID actorId, OffsetDateTime from, OffsetDateTime to,
                     Cursor cursor, int limit) {
        StringBuilder sql = new StringBuilder("SELECT id, actor_id, action, target_type, target_id, details::text, "
                + "trace_id, created_at FROM core.audit_logs WHERE workspace_id = ?");
        List<Object> args = new ArrayList<>(List.of(principal.workspaceId()));
        if (action != null && !action.isBlank()) {
            sql.append(" AND action = ?");
            args.add(action);
        }
        if (actorId != null) {
            sql.append(" AND actor_id = ?");
            args.add(actorId);
        }
        if (from != null) {
            sql.append(" AND created_at >= ?");
            args.add(from);
        }
        if (to != null) {
            sql.append(" AND created_at <= ?");
            args.add(to);
        }
        if (cursor != null) {
            sql.append(" AND (created_at, id) < (?, ?)");
            args.add(cursor.createdAt());
            args.add(cursor.id());
        }
        sql.append(" ORDER BY created_at DESC, id DESC LIMIT ?");
        args.add(limit + 1);
        List<Entry> rows = new ArrayList<>(jdbc.query(sql.toString(), (rs, i) -> new Entry(
                rs.getObject("id", UUID.class), rs.getObject("actor_id", UUID.class), rs.getString("action"),
                rs.getString("target_type"), rs.getObject("target_id", UUID.class), rs.getString("details"),
                rs.getString("trace_id"), rs.getObject("created_at", OffsetDateTime.class)), args.toArray()));
        boolean more = rows.size() > limit;
        if (more) {
            rows.remove(rows.size() - 1);
        }
        String next = more ? new Cursor(rows.get(rows.size() - 1).createdAt(), rows.get(rows.size() - 1).id()).encode()
                : null;
        return new Page(rows, next, more);
    }

    private String json(Map<String, Object> details) {
        try {
            return mapper.writeValueAsString(details);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Audit details are not serializable");
        }
    }

    /** {@code details} is the raw JSON text; the controller exposes it as an object. */
    public record Entry(UUID id, UUID actorId, String action, String targetType, UUID targetId, String details,
                        String traceId, OffsetDateTime createdAt) {
    }

    public record Page(List<Entry> entries, String nextCursor, boolean hasMore) {
    }
}
