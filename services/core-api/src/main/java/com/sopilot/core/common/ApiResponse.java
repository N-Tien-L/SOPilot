package com.sopilot.core.common;

/** Success envelope {@code {"data": ..., "traceId": "..."}} (TECH-V2-core-api §5.0). */
public record ApiResponse<T>(T data, String traceId) {

    public static <T> ApiResponse<T> of(T data) {
        return new ApiResponse<>(data, TraceIdFilter.currentTraceId());
    }
}
