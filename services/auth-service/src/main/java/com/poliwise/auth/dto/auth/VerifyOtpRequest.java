package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VerifyOtpRequest {

    @NotBlank(message = "Email là bắt buộc")
    private String email;

    @NotBlank(message = "Mã OTP là bắt buộc")
    @Size(min = 6, max = 6, message = "Mã OTP phải có 6 số")
    private String otp;
}
