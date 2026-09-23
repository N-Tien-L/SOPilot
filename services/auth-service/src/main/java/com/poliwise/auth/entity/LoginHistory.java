package com.poliwise.auth.entity;

import com.poliwise.auth.enums.LoginStatus;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "login_history", schema = "core")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "user_id")
    private UUID userId;

    @Column(nullable = false)
    private String username;

    @Column(name = "ip_address")
    private String ipAddress;

    /**
     * Thông tin trình duyệt / client Ví dụ: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120
     */
    @Column(name = "user_agent", columnDefinition = "TEXT")
    private String userAgent;

    /**
     * Loại thiết bị Ví dụ: - Desktop - Mobile - Tablet
     */
    @Column(name = "device_type")
    private String deviceType;

    /**
     * Vị trí địa lý (nếu xác định được từ IP) Ví dụ: Vietnam, Ho Chi Minh
     */
    private String location;

    /**
     * Trạng thái đăng nhập SUCCESS hoặc FAILED
     */
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "status", nullable = false)
    private LoginStatus status;

    /**
     * Lý do thất bại nếu login không thành công Ví dụ: - WRONG_PASSWORD - USER_NOT_FOUND -
     * ACCOUNT_LOCKED
     */
    @Column(name = "failure_reason", columnDefinition = "TEXT")
    private String failureReason;

    /**
     * Thời điểm login Dùng Instant để chuẩn UTC
     */
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

}
