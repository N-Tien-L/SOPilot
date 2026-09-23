package com.poliwise.user.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(UserNotFoundException ex) {
        return build(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", ex.getMessage());
    }

    @ExceptionHandler(UserAlreadyExistsException.class)
    public ResponseEntity<ErrorResponse> handleConflict(UserAlreadyExistsException ex) {
        return build(HttpStatus.CONFLICT, "USER_ALREADY_EXISTS", ex.getMessage());
    }

    @ExceptionHandler(UserDeactivatedException.class)
    public ResponseEntity<ErrorResponse> handleDeactivated(UserDeactivatedException ex) {
        return build(HttpStatus.FORBIDDEN, "ACCOUNT_DEACTIVATED", ex.getMessage());
    }

    @ExceptionHandler(InvalidStatusTransitionException.class)
    public ResponseEntity<ErrorResponse> handleInvalidTransition(InvalidStatusTransitionException ex) {
        return build(HttpStatus.BAD_REQUEST, "INVALID_STATUS_TRANSITION", ex.getMessage());
    }

    @ExceptionHandler(DepartmentNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleDepartmentNotFound(DepartmentNotFoundException ex) {
        return build(HttpStatus.NOT_FOUND, "DEPARTMENT_NOT_FOUND", ex.getMessage());
    }

    @ExceptionHandler(InvalidDepartmentOperationException.class)
    public ResponseEntity<ErrorResponse> handleInvalidDepartmentOp(InvalidDepartmentOperationException ex) {
        return build(HttpStatus.BAD_REQUEST, "INVALID_DEPARTMENT_OPERATION", ex.getMessage());
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ErrorResponse> handleAccessDenied(AccessDeniedException ex) {
        return build(HttpStatus.FORBIDDEN, "ACCESS_DENIED", ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
                .collect(java.util.stream.Collectors.toMap(
                        FieldError::getField,
                        error -> error.getDefaultMessage() != null ? error.getDefaultMessage() : "Invalid value",
                        (a, b) -> a
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

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleBadRequest(IllegalArgumentException ex) {
        return build(HttpStatus.BAD_REQUEST, "BAD_REQUEST", ex.getMessage());
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    public ResponseEntity<ErrorResponse> handleMissingHeader(MissingRequestHeaderException ex) {
        return build(HttpStatus.BAD_REQUEST, "MISSING_HEADER",
                "Required header '" + ex.getHeaderName() + "' is missing");
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneric(Exception ex) {
        log.error("Unexpected error", ex);
        return build(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_SERVER_ERROR", "An unexpected error occurred");
    }

    private ResponseEntity<ErrorResponse> build(HttpStatus status, String code, String message) {
        return ResponseEntity.status(status)
                .body(new ErrorResponse(status.value(), code, message, Instant.now()));
    }

    public record ErrorResponse(
            int status,
            String code,
            String message,
            Instant timestamp
    ) {}

    public record ValidationErrorResponse(
            int status,
            String code,
            String message,
            Instant timestamp,
            Map<String, String> fieldErrors
    ) {}
}
