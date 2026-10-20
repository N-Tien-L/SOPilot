package com.poliwise.auth.exception;

import io.jsonwebtoken.JwtException;

/** Expected rejection after persisting expiration/replay revocation. */
public class RefreshTokenRejectedException extends JwtException {
    public RefreshTokenRejectedException(String message) {
        super(message);
    }
}
