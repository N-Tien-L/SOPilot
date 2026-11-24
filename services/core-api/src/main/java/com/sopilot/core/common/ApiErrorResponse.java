package com.sopilot.core.common;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.util.Map;

/**
 * Error envelope {@code {"error": {"code", "message", "details"}, "traceId"}} (TECH §5.0).
 * {@code message} is always a fixed user-facing sentence, never an exception message (A8).
 */
public record ApiErrorResponse(Body error, String traceId) {

    @JsonInclude(JsonInclude.Include.NON_EMPTY)
    public record Body(String code, String message, Map<String, Object> details) {
    }

    public static ApiErrorResponse of(String code, String message, Map<String, Object> details) {
        return new ApiErrorResponse(new Body(code, message, details), TraceIdFilter.currentTraceId());
    }
}
