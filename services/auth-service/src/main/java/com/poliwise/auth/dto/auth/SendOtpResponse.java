package com.poliwise.auth.dto.auth;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SendOtpResponse {
    private boolean success;
    private String message;
    private int expiresIn;

    public static SendOtpResponse success(int expiresIn) {
        return SendOtpResponse.builder()
                .success(true)
                .message("Mã OTP đã được gửi đến email của bạn")
                .expiresIn(expiresIn)
                .build();
    }
}
