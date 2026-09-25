package com.poliwise.user.exception;

public class RosterAlreadyClaimedException extends RuntimeException {
    public RosterAlreadyClaimedException(String message) {
        super(message);
    }
}
