package com.poliwise.auth.enums;

import lombok.Getter;

@Getter
public enum LoginStatus {
    /** Đăng nhập thành công */
    SUCCESS,

    /** Sai email hoặc mật khẩu */
    FAILED_CREDENTIALS,

    /** Tài khoản đã bị vô hiệu hóa (deactivated) */
    FAILED_DEACTIVATED,

    /** Tài khoản đã bị thu hồi quyền truy cập (revoked) */
    FAILED_REVOKED,

    /** Tài khoản bị khóa (locked do đăng nhập sai nhiều lần hoặc admin khóa) */
    FAILED_LOCKED
}
