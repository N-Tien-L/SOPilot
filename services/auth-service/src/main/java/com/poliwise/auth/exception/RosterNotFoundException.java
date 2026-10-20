package com.poliwise.auth.exception;

/**
 * Thrown when an employee attempting Google JIT login is not found
 * in the pre-provisioned employee roster (core.employee_roster).
 */
public class RosterNotFoundException extends RuntimeException {
    public RosterNotFoundException(String message) {
        super(message);
    }
}
