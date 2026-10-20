package com.poliwise.auth.exception;

/**
 * Thrown when an employee identity in the pre-provisioned roster
 * has been marked as DEACTIVATED by HR/Admin.
 */
public class RosterDeactivatedException extends RuntimeException {
    public RosterDeactivatedException(String message) {
        super(message);
    }
}
