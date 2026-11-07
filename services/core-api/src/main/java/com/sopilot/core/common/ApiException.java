package com.sopilot.core.common;

import org.springframework.http.HttpStatus;

import java.util.Map;

/**
 * Business error with a stable code and a fixed, client-safe message.
 * Never build {@code clientMessage} from another exception's message (A8).
 */
public class ApiException extends RuntimeException {

    private final HttpStatus status;
    private final String code;
    private final String clientMessage;
    private final transient Map<String, Object> details;

    public ApiException(HttpStatus status, String code, String clientMessage) {
        this(status, code, clientMessage, Map.of());
    }

    public ApiException(HttpStatus status, String code, String clientMessage, Map<String, Object> details) {
        super(code);
        this.status = status;
        this.code = code;
        this.clientMessage = clientMessage;
        this.details = details;
    }

    public HttpStatus status() {
        return status;
    }

    public String code() {
        return code;
    }

    public String clientMessage() {
        return clientMessage;
    }

    public Map<String, Object> details() {
        return details;
    }
}
