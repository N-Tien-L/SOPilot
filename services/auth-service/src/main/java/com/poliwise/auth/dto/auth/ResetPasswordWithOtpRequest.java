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
public class ResetPasswordWithOtpRequest {

    @NotBlank(message = "Email là bắt buộc")
    private String email;

    @NotBlank(message = "Mã OTP là bắt buộc")
    private String otp;

    private String resetToken;

    @NotBlank(message = "Mật khẩu mới là bắt buộc")
    @Size(min = 8, message = "Mật khẩu phải có ít nhất 8 ký tự")
    private String newPassword;

    @NotBlank(message = "Xác nhận mật khẩu là bắt buộc")
    private String confirmPassword;
}
