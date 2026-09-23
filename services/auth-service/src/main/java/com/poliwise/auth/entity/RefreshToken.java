package com.poliwise.auth.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "refresh_tokens", schema = "core")
public class RefreshToken {
    /**
     * ID duy nhất của refresh token.
     */
    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    /**
     * ID của người dùng sở hữu token này.
     */
    @Column(name = "user_id", nullable = false)
    private UUID userId;

    /**
     * Hash của refresh token.
     *
     * Không lưu token dạng plaintext để tránh rò rỉ nếu database bị lộ.
     */
    @Column(name = "token_hash", nullable = false)
    private String tokenHash;

    /**
     * Thông tin thiết bị đăng nhập (ví dụ: iPhone, Chrome on Windows).
     */
    @Column(name = "device_info")
    private String deviceInfo;

    /**
     * Địa chỉ IP của client khi token được tạo.
     * Sử dụng columnDefinition = "inet" để match với database schema
     */
    @Column(name = "ip_address")
    private String ipAddress;

    /**
     * Chuỗi user-agent của client. Dùng để xác định trình duyệt hoặc ứng dụng.
     */
    @Column(name = "user_agent")
    private String userAgent;

    /**
     * Thời điểm refresh token hết hạn.
     */
    @Column(name = "expires_at", nullable = false)
    private OffsetDateTime expiresAt;

    /**
     * Cờ cho biết token đã bị thu hồi hay chưa.
     */
    @Column(name = "revoked")
    private Boolean revoked;

    /**
     * Thời điểm token bị thu hồi.
     */
    @Column(name = "revoked_at")
    private OffsetDateTime revokedAt;

    /**
     * Lý do thu hồi token.
     *
     * Ví dụ: - LOGOUT - SECURITY_POLICY - TOKEN_ROTATION
     */
    @Column(name = "revoked_reason")
    private String revokedReason;

    /**
     * ID của refresh token mới thay thế token này. Dùng cho cơ chế refresh token rotation.
     */
    @Column(name = "replaced_by")
    private UUID replacedBy;

    /**
     * Thời điểm refresh token được tạo.
     */
    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    /**
     * Tự động set thời gian tạo khi persist.
     */
    @PrePersist
    public void prePersist() {
        this.createdAt = OffsetDateTime.now();
    }
}
