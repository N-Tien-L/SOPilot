package com.poliwise.feedback.exception;

public class ReportNotFoundException extends RuntimeException {
    public ReportNotFoundException(Object id) {
        super("Report not found: " + id);
    }
}
