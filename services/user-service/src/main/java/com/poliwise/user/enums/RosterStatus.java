package com.poliwise.user.enums;

import lombok.Getter;

@Getter
public enum RosterStatus {
    /** Nhân sự được HR nạp trước vào danh bạ, đang chờ kích hoạt tài khoản lần đầu qua Google */
    PENDING,

    /** Nhân sự đã đăng nhập Google thành công, đã claim định danh và có tài khoản hệ thống */
    CLAIMED,

    /** Định danh nhân sự đã bị HR vô hiệu hóa */
    DEACTIVATED
}
