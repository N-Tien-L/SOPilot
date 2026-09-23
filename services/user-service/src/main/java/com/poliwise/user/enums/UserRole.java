package com.poliwise.user.enums;

import lombok.Getter;

@Getter
public enum UserRole {
    /** Người dùng thông thường của hệ thống */
    USER,

    /** Người quản lý, có quyền quản lý một số tài nguyên */
    MANAGER,

    /** Quản trị viên hệ thống với toàn bộ quyền */
    ADMIN
}
