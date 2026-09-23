package com.poliwise.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.UUID;

/**
 * DTO tạo mới phòng ban.
 */
public record CreateDepartmentRequest(
        @NotBlank(message = "Tên phòng ban là bắt buộc")
        @Size(max = 100, message = "Tên phòng ban không được vượt quá 100 ký tự")
        String name,

        @NotBlank(message = "Mã phòng ban là bắt buộc")
        @Size(max = 20, message = "Mã phòng ban không được vượt quá 20 ký tự")
        String code,

        String description,

        UUID parentId
) {}
