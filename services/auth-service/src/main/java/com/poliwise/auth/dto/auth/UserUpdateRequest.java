package com.poliwise.auth.dto.auth;

import jakarta.validation.constraints.Size;
import java.util.UUID;

public record UserUpdateRequest(
        @Size(max = 255, message = "Ho va ten khong duoc vuot qua 255 ky tu")
        String fullName,

        String role,

        UUID departmentId,

        String status
) {}
