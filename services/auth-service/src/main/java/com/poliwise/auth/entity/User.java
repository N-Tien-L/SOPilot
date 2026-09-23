package com.poliwise.auth.entity;

import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "users", schema = "core")
public class User {
    /**
     * ID duy nhất của người dùng. Sử dụng UUID để tránh đoán ID và phù hợp với hệ thống
     * distributed.
     */
    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    /**
     * Username dùng để đăng nhập. Thường là unique trong hệ thống.
     */
    @Column(name = "username", nullable = false, length = 100)
    private String username;

    /**
     * Email của người dùng. Có thể được dùng cho login hoặc khôi phục mật khẩu.
     */
    @Column(name = "email", nullable = false, length = 255)
    private String email;

    /**
     * Hash của mật khẩu (BCrypt / Argon2). Tuyệt đối không lưu mật khẩu dạng plaintext.
     */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    /**
     * Vai trò của người dùng trong hệ thống. Quy định quyền truy cập (authorization).
     */
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "role", nullable = false)
    private UserRole role;

    /**
     * Trạng thái tài khoản. Cho biết tài khoản có được phép đăng nhập hay không.
     */
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "status", nullable = false)
    private AccountStatus status;

    /**
     * ID phòng ban hoặc đơn vị của người dùng. Có thể dùng cho phân quyền theo tổ chức.
     */
    @Column(name = "department_id")
    private UUID departmentId;

    /**
     * Số lần đăng nhập thất bại liên tiếp. Dùng để phát hiện brute-force login.
     */
    @Column(name = "failed_login_attempts")
    private Integer failedLoginAttempts;

    /**
     * Thời điểm tài khoản bị khóa tạm thời. Sau thời gian này người dùng có thể thử đăng nhập lại.
     */
    @Column(name = "locked_until")
    private OffsetDateTime lockedUntil;

    /**
     * Thời điểm người dùng đổi mật khẩu lần cuối. Dùng để áp dụng policy đổi mật khẩu định kỳ.
     */
    @Column(name = "password_changed_at")
    private OffsetDateTime passwordChangedAt;

    /**
     * Cờ yêu cầu người dùng đổi mật khẩu ở lần đăng nhập tiếp theo. Ví dụ sau khi admin reset
     * password.
     */
    @Column(name = "must_change_password")
    private Boolean mustChangePassword;

    /**
     * ID của người tạo tài khoản. Có thể là admin hoặc hệ thống.
     */
    @Column(name = "created_by")
    private UUID createdBy;

    /**
     * Thời điểm tài khoản được tạo.
     */
    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    /**
     * Thời điểm cập nhật thông tin gần nhất.
     */
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    /**
     * Thời điểm tài khoản bị vô hiệu hóa. Chỉ có giá trị khi status = DEACTIVATED.
     */
    @Column(name = "deactivated_at")
    private OffsetDateTime deactivatedAt;

    /**
     * Thời điểm tài khoản bị thu hồi quyền truy cập. Chỉ có giá trị khi status = REVOKED.
     */
    @Column(name = "revoked_at")
    private OffsetDateTime revokedAt;

    /**
     * So lan vi pham chinh sach cua nguoi dung. Duoc tang khi Layer 1 chan query.
     * Nguong: 3 -> warn, 5 -> deactivate, 10 -> revoke.
     */
    @Column(name = "strike_count")
    private Integer strikeCount;

    /**
     * Thoi diem vi pham gan nhat. Cap nhat moi khi co vi pham moi.
     */
    @Column(name = "last_violation_at")
    private OffsetDateTime lastViolationAt;
}
