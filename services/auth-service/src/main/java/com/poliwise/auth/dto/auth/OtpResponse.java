package com.poliwise.auth.dto.auth;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OtpResponse {
    private boolean success;
    private String message;

    public static OtpResponse success(String message) {
        return OtpResponse.builder()
                .success(true)
                .message(message)
                .build();
    }

    public static OtpResponse error(String message) {
        return OtpResponse.builder()
                .success(false)
                .message(message)
                .build();
    }
}
