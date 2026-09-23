package com.poliwise.auth.dto.auth;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VerifyOtpResponse {
    private boolean valid;
    private boolean expired;
    private String message;
    private String resetToken;

    public static VerifyOtpResponse valid(String resetToken) {
        return VerifyOtpResponse.builder()
                .valid(true)
                .expired(false)
                .message("OTP hợp lệ")
                .resetToken(resetToken)
                .build();
    }

    public static VerifyOtpResponse invalid() {
        return VerifyOtpResponse.builder()
                .valid(false)
                .expired(false)
                .message("Mã OTP không hợp lệ")
                .build();
    }

    public static VerifyOtpResponse expired() {
        return VerifyOtpResponse.builder()
                .valid(false)
                .expired(true)
                .message("Mã OTP đã hết hạn")
                .build();
    }
}
