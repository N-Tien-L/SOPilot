package com.poliwise.auth.dto.auth;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.UUID;

public record BulkUserCreateRequest(
        @NotNull(message = "Danh sách users là bắt buộc")
        @Size(min = 1, max = 100, message = "Số lượng users phải từ 1 đến 100")
        @Valid
        List<UserCreateItem> users
) {
    public record UserCreateItem(
            @NotBlank(message = "Username là bắt buộc")
            @Size(min = 3, max = 100, message = "Username phải từ 3 đến 100 ký tự")
            String username,

            @NotBlank(message = "Email là bắt buộc")
            @Email(message = "Email không hợp lệ")
            @Size(max = 255, message = "Email không được vượt quá 255 ký tự")
            String email,

            @NotBlank(message = "Họ và tên là bắt buộc")
            @Size(max = 255, message = "Họ và tên không được vượt quá 255 ký tự")
            String fullName,

            @NotNull(message = "Vai trò là bắt buộc")
            String role,

            UUID departmentId
    ) {}
}
