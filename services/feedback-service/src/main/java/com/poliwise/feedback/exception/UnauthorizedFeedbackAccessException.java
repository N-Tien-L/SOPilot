package com.poliwise.feedback.exception;

public class UnauthorizedFeedbackAccessException extends RuntimeException {
    public UnauthorizedFeedbackAccessException() {
        super("You do not have permission to access this feedback");
    }
}
