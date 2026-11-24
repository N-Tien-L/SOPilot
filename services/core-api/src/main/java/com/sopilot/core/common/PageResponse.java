package com.sopilot.core.common;

import java.util.List;

/** Cursor-paged list {@code {"data": [...], "page": {"cursor", "hasMore"}, "traceId"}} (TECH §5.0). */
public record PageResponse<T>(List<T> data, Page page, String traceId) {

    public record Page(String cursor, boolean hasMore) {
    }

    public static <T> PageResponse<T> of(List<T> data, String nextCursor, boolean hasMore) {
        return new PageResponse<>(data, new Page(nextCursor, hasMore), TraceIdFilter.currentTraceId());
    }
}
