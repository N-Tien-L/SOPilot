package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChangePasswordRequest(
        @NotBlank(message = "Mật khẩu cũ là bắt buộc")
        String oldPassword,

        @NotBlank(message = "Mật khẩu mới là bắt buộc")
        @Size(min = 8, max = 128, message = "Mật khẩu mới phải từ 8 đến 128 ký tự")
        String newPassword,

        @NotBlank(message = "Xác nhận mật khẩu là bắt buộc")
        String confirmPassword
) {}
