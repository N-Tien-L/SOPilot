package com.poliwise.auth.exception;

import io.jsonwebtoken.JwtException;
import java.time.Instant;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(JwtException.class)
    public ResponseEntity<ErrorResponse> handleJwtException(JwtException ex) {
        log.warn("JWT exception: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new ErrorResponse(
                        HttpStatus.UNAUTHORIZED.value(),
                        "UNAUTHORIZED",
                        ex.getMessage(),
                        Instant.now()
                ));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ErrorResponse> handleResponseStatusException(ResponseStatusException ex) {
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        log.warn("ResponseStatusException: {} - {}", ex.getStatusCode(), ex.getReason());
        return ResponseEntity.status(status != null ? status : HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse(
                        ex.getStatusCode().value(),
                        status != null ? status.name() : "ERROR",
                        ex.getReason(),
                        Instant.now()
                ));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidationException(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
                .collect(java.util.stream.Collectors.toMap(
                        FieldError::getField,
                        error -> error.getDefaultMessage() != null ? error.getDefaultMessage() : "Invalid value",
                        (existing, replacement) -> existing
                ));

        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ValidationErrorResponse(
                        HttpStatus.BAD_REQUEST.value(),
                        "VALIDATION_ERROR",
                        "Input validation failed",
                        Instant.now(),
                        errors
                ));
    }

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<ErrorResponse> handleAuthenticationException(AuthenticationException ex) {
        log.warn("Authentication exception: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new ErrorResponse(
                        HttpStatus.UNAUTHORIZED.value(),
                        "UNAUTHORIZED",
                        "Authentication failed: " + ex.getMessage(),
                        Instant.now()
                ));
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ErrorResponse> handleAccessDeniedException(AccessDeniedException ex) {
        log.warn("Access denied: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(new ErrorResponse(
                        HttpStatus.FORBIDDEN.value(),
                        "FORBIDDEN",
                        "Access denied: " + ex.getMessage(),
                        Instant.now()
                ));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleIllegalArgumentException(IllegalArgumentException ex) {
        log.warn("IllegalArgumentException: {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ErrorResponse(
                        HttpStatus.BAD_REQUEST.value(),
                        "BAD_REQUEST",
                        ex.getMessage(),
                        Instant.now()
                ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGenericException(Exception ex) {
        log.error("Unhandled exception in auth-service: {} - {}", ex.getClass().getName(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(new ErrorResponse(
                        HttpStatus.INTERNAL_SERVER_ERROR.value(),
                        "INTERNAL_SERVER_ERROR",
                        "An unexpected error occurred: " + ex.getMessage(),
                        Instant.now()
                ));
    }

    public record ErrorResponse(
            int status,
            String error,
            String message,
            Instant timestamp
    ) {}

    public record ValidationErrorResponse(
            int status,
            String error,
            String message,
            Instant timestamp,
            Map<String, String> fieldErrors
    ) {}
}
