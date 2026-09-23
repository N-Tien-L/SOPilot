package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.UUID;

public record UserCreateRequest(
        @NotBlank(message = "Username la bat buoc")
        @Size(min = 3, max = 100, message = "Username phai tu 3 den 100 ky tu")
        String username,

        @NotBlank(message = "Email la bat buoc")
        @Email(message = "Email khong hop le")
        @Size(max = 255, message = "Email khong duoc vuot qua 255 ky tu")
        String email,

        @NotBlank(message = "Ho va ten la bat buoc")
        @Size(max = 255, message = "Ho va ten khong duoc vuot qua 255 ky tu")
        String fullName,

        @NotNull(message = "Vai tro la bat buoc")
        String role,

        UUID departmentId
) {}
