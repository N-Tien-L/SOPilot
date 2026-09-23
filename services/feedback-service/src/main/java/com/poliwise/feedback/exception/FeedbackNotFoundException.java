package com.poliwise.feedback.exception;

public class FeedbackNotFoundException extends RuntimeException {
    public FeedbackNotFoundException(Object id) {
        super("Feedback not found: " + id);
    }
}
