package com.sopilot.core.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Map;
import java.util.TreeMap;

/**
 * Maps every failure to the error envelope. Responses never carry {@code e.getMessage()} of an
 * internal exception (A8); unexpected errors are logged with the trace id and returned as a
 * fixed {@code 500 INTERNAL_ERROR}.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ApiErrorResponse> handleApi(ApiException e) {
        return ResponseEntity.status(e.status()).body(ApiErrorResponse.of(e.code(), e.clientMessage(), e.details()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiErrorResponse> handleValidation(MethodArgumentNotValidException e) {
        // Field names only: rejected values may contain tokens or personal data.
        Map<String, Object> fields = new TreeMap<>();
        e.getBindingResult().getFieldErrors().forEach(f -> fields.putIfAbsent(f.getField(), "invalid"));
        return ResponseEntity.badRequest().body(ApiErrorResponse.of(
                "VALIDATION_FAILED", "Request is invalid.", Map.of("fields", fields)));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiErrorResponse> handleUnreadable(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(ApiErrorResponse.of(
                "VALIDATION_FAILED", "Request body is missing or malformed.", Map.of()));
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public ResponseEntity<ApiErrorResponse> handleMediaType(HttpMediaTypeNotSupportedException e) {
        return ResponseEntity.status(HttpStatus.UNSUPPORTED_MEDIA_TYPE).body(ApiErrorResponse.of(
                "UNSUPPORTED_MEDIA_TYPE", "Content type is not supported.", Map.of()));
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<ApiErrorResponse> handleMethod(HttpRequestMethodNotSupportedException e) {
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED).body(ApiErrorResponse.of(
                "METHOD_NOT_ALLOWED", "Method is not allowed.", Map.of()));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiErrorResponse> handleNotFound(NoResourceFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(ApiErrorResponse.of(
                "NOT_FOUND", "Resource not found.", Map.of()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleUnexpected(Exception e) {
        log.error("Unhandled {}", e.getClass().getName(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(ApiErrorResponse.of(
                "INTERNAL_ERROR", "An unexpected error occurred.", Map.of()));
    }
}
