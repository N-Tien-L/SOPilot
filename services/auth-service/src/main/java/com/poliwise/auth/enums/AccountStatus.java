package com.poliwise.auth.enums;

import lombok.Getter;

@Getter
public enum AccountStatus {
    /** Tài khoản đang hoạt động bình thường và có thể đăng nhập */
    ACTIVE,

    /** Tài khoản bị vô hiệu hóa (user hoặc admin tạm tắt) */
    DEACTIVATED,

    /** Tài khoản bị thu hồi quyền truy cập vĩnh viễn (ví dụ vi phạm chính sách) */
    REVOKED
}
