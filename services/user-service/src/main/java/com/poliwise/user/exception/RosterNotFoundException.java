package com.poliwise.user.exception;

public class RosterNotFoundException extends RuntimeException {
    public RosterNotFoundException(String message) {
        super(message);
    }
}
